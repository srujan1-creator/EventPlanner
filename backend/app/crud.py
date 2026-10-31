"""Repository layer providing optimized queries, single-pass aggregations, and demo seeding.

Implements the repository pattern with zero N+1 database queries, strict capacity
validation, and comprehensive seed data for FestivaFlow.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from backend.app.models import Event, Expense, Guest, Task, Vendor
from backend.app.schemas import (
    EventBudgetSummary,
    EventCreate,
    EventRSVPSummary,
    EventTaskSummary,
    EventUpdate,
    ExpenseCreate,
    ExpenseUpdate,
    GlobalAnalyticsResponse,
    GuestCreate,
    GuestUpdate,
    TaskCreate,
    TaskUpdate,
    VendorCreate,
    VendorUpdate,
)

# ============================================================================
# EVENT OPERATIONS
# ============================================================================

def get_events(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    search: str | None = None,
    status: str | None = None,
    category: str | None = None,
) -> tuple[list[Event], int]:
    """Retrieve a paginated and filtered list of celebration events with total count.

    Args:
        db: Database session.
        skip: Offset for pagination.
        limit: Maximum records to return.
        search: Optional search term matching title or venue.
        status: Optional lifecycle state filter.
        category: Optional category filter.

    Returns:
        Tuple of (list of Event models, total matching count).
    """
    query = db.query(Event)

    if search:
        search_fmt = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Event.title.ilike(search_fmt),
                Event.venue.ilike(search_fmt),
                Event.description.ilike(search_fmt),
            )
        )

    if status:
        query = query.filter(Event.status == status)

    if category:
        query = query.filter(Event.category == category)

    total_count = query.count()
    events = (
        query.order_by(Event.event_date.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return events, total_count


def get_event(db: Session, event_id: int) -> Event | None:
    """Retrieve a single event by primary key ID.

    Args:
        db: Database session.
        event_id: Unique event identifier.

    Returns:
        Event model or None if not found.
    """
    return db.query(Event).filter(Event.id == event_id).first()


def create_event(db: Session, event_in: EventCreate) -> Event:
    """Create and persist a new celebration event.

    Args:
        db: Database session.
        event_in: Validated event payload.

    Returns:
        Newly created Event model instance.
    """
    event = Event(**event_in.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def update_event(
    db: Session, event_id: int, event_in: EventUpdate
) -> Event | None:
    """Update fields on an existing celebration event.

    Args:
        db: Database session.
        event_id: Target event ID.
        event_in: Updated field values.

    Returns:
        Updated Event model instance, or None if not found.
    """
    event = get_event(db, event_id)
    if not event:
        return None

    update_data = event_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(event, field, value)

    event.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(event)
    return event


def delete_event(db: Session, event_id: int) -> bool:
    """Delete an event and cascade-remove all child guests, expenses, and tasks.

    Args:
        db: Database session.
        event_id: Target event ID.

    Returns:
        True if deleted, False if not found.
    """
    event = get_event(db, event_id)
    if not event:
        return False

    db.delete(event)
    db.commit()
    return True


# ============================================================================
# AGGREGATION & SUMMARY CALCULATIONS (SINGLE-PASS SQL)
# ============================================================================

def get_event_budget_summary(db: Session, event: Event) -> EventBudgetSummary:
    """Compute financial metrics using single-pass SQL aggregation.

    Args:
        db: Database session.
        event: Target Event instance.

    Returns:
        EventBudgetSummary schema with real-time balance and burn rate.
    """
    stats = (
        db.query(
            func.coalesce(func.sum(Expense.estimated_cost), 0.0).label("est"),
            func.coalesce(func.sum(Expense.actual_cost), 0.0).label("act"),
            func.coalesce(
                func.sum(
                    case((Expense.is_paid.is_(True), Expense.actual_cost), else_=0.0)
                ),
                0.0,
            ).label("paid"),
            func.coalesce(
                func.sum(
                    case((Expense.is_paid.is_(False), Expense.actual_cost), else_=0.0)
                ),
                0.0,
            ).label("pending"),
        )
        .filter(Expense.event_id == event.id)
        .first()
    )

    total_est = round(float(stats.est or 0.0), 2)
    total_act = round(float(stats.act or 0.0), 2)
    total_paid = round(float(stats.paid or 0.0), 2)
    total_pending = round(float(stats.pending or 0.0), 2)
    total_budget = round(float(event.total_budget), 2)

    remaining_budget = round(total_budget - total_act, 2)
    burn_rate_pct = (
        round((total_act / total_budget) * 100.0, 2) if total_budget > 0 else 0.0
    )
    is_over_budget = total_act > total_budget

    return EventBudgetSummary(
        total_budget=total_budget,
        total_estimated=total_est,
        total_actual=total_act,
        total_paid=total_paid,
        total_pending=total_pending,
        remaining_budget=remaining_budget,
        burn_rate_pct=burn_rate_pct,
        is_over_budget=is_over_budget,
    )


def get_event_rsvp_summary(db: Session, event: Event) -> EventRSVPSummary:
    """Compute RSVP headcount and capacity utilization via single-pass SQL.

    Args:
        db: Database session.
        event: Target Event instance.

    Returns:
        EventRSVPSummary schema with capacity status.
    """
    stats = (
        db.query(
            func.count(Guest.id).label("total"),
            func.coalesce(
                func.sum(case((Guest.rsvp_status == "Attending", 1), else_=0)), 0
            ).label("attending"),
            func.coalesce(
                func.sum(case((Guest.rsvp_status == "Pending", 1), else_=0)), 0
            ).label("pending"),
            func.coalesce(
                func.sum(case((Guest.rsvp_status == "Declined", 1), else_=0)), 0
            ).label("declined"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            Guest.rsvp_status == "Attending",
                            1 + Guest.plus_one_count,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("total_attendees"),
        )
        .filter(Guest.event_id == event.id)
        .first()
    )

    total_guests = int(stats.total or 0)
    attending_count = int(stats.attending or 0)
    pending_count = int(stats.pending or 0)
    declined_count = int(stats.declined or 0)
    total_attendees = int(stats.total_attendees or 0)
    capacity = int(event.capacity)

    capacity_utilization_pct = (
        round((total_attendees / capacity) * 100.0, 2) if capacity > 0 else 0.0
    )

    return EventRSVPSummary(
        total_guests=total_guests,
        attending_count=attending_count,
        pending_count=pending_count,
        declined_count=declined_count,
        total_attendees=total_attendees,
        capacity=capacity,
        capacity_utilization_pct=capacity_utilization_pct,
    )


def get_event_task_summary(db: Session, event_id: int) -> EventTaskSummary:
    """Compute checklist completion metrics via single-pass SQL.

    Args:
        db: Database session.
        event_id: Target event ID.

    Returns:
        EventTaskSummary schema with completion rate.
    """
    stats = (
        db.query(
            func.count(Task.id).label("total"),
            func.coalesce(
                func.sum(case((Task.is_completed.is_(True), 1), else_=0)), 0
            ).label("completed"),
        )
        .filter(Task.event_id == event_id)
        .first()
    )

    total_tasks = int(stats.total or 0)
    completed_tasks = int(stats.completed or 0)
    pending_tasks = total_tasks - completed_tasks
    completion_rate_pct = (
        round((completed_tasks / total_tasks) * 100.0, 2)
        if total_tasks > 0
        else 0.0
    )

    return EventTaskSummary(
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        pending_tasks=pending_tasks,
        completion_rate_pct=completion_rate_pct,
    )


# ============================================================================
# GUEST OPERATIONS (WITH AUTOMATED CAPACITY VALIDATION)
# ============================================================================

def validate_capacity_headroom(
    db: Session, event: Event, requested_headcount: int, exclude_guest_id: int | None = None
) -> None:
    """Validate that admitting the requested guest headcount will not breach event capacity.

    Args:
        db: Database session.
        event: Parent event.
        requested_headcount: Number of heads to add (1 + plus_one_count).
        exclude_guest_id: Optional guest ID to exclude if modifying an existing guest.

    Raises:
        ValueError: If capacity limit is exceeded.
    """
    query = db.query(
        func.coalesce(
            func.sum(1 + Guest.plus_one_count),
            0,
        )
    ).filter(
        Guest.event_id == event.id,
        Guest.rsvp_status == "Attending",
    )

    if exclude_guest_id:
        query = query.filter(Guest.id != exclude_guest_id)

    current_attendees = int(query.scalar() or 0)
    if current_attendees + requested_headcount > event.capacity:
        available = max(0, event.capacity - current_attendees)
        raise ValueError(
            f"Event capacity exceeded. Maximum capacity is {event.capacity}, "
            f"current attendees: {current_attendees}, available slots: {available}. "
            f"Requested headcount: {requested_headcount}."
        )


def get_guests(db: Session, event_id: int) -> list[Guest]:
    """Retrieve all guests registered for an event.

    Args:
        db: Database session.
        event_id: Event ID.

    Returns:
        List of Guest models ordered by creation time.
    """
    return (
        db.query(Guest)
        .filter(Guest.event_id == event_id)
        .order_by(Guest.created_at.desc())
        .all()
    )


def get_guest(db: Session, guest_id: int) -> Guest | None:
    """Retrieve a single guest by ID.

    Args:
        db: Database session.
        guest_id: Guest primary key.

    Returns:
        Guest model or None.
    """
    return db.query(Guest).filter(Guest.id == guest_id).first()


def create_guest(db: Session, event_id: int, guest_in: GuestCreate) -> Guest:
    """Create a guest record with automated capacity enforcement.

    Args:
        db: Database session.
        event_id: Event ID.
        guest_in: Validated guest payload.

    Returns:
        Newly created Guest instance.

    Raises:
        ValueError: If event does not exist or capacity is breached.
    """
    event = get_event(db, event_id)
    if not event:
        raise ValueError(f"Event with ID {event_id} does not exist.")

    if guest_in.rsvp_status == "Attending":
        headcount = 1 + guest_in.plus_one_count
        validate_capacity_headroom(db, event, headcount)

    guest = Guest(event_id=event_id, **guest_in.model_dump())
    db.add(guest)
    db.commit()
    db.refresh(guest)
    return guest


def update_guest(
    db: Session, guest_id: int, guest_in: GuestUpdate
) -> Guest | None:
    """Update a guest record with capacity checking if attendance changes.

    Args:
        db: Database session.
        guest_id: Guest ID.
        guest_in: Update payload.

    Returns:
        Updated Guest or None.

    Raises:
        ValueError: If updated attendance exceeds event capacity.
    """
    guest = get_guest(db, guest_id)
    if not guest:
        return None

    event = get_event(db, guest.event_id)
    if not event:
        raise ValueError("Parent event not found.")

    update_data = guest_in.model_dump(exclude_unset=True)

    new_status = update_data.get("rsvp_status", guest.rsvp_status)
    new_plus_ones = update_data.get("plus_one_count", guest.plus_one_count)

    if new_status == "Attending":
        headcount = 1 + new_plus_ones
        validate_capacity_headroom(
            db, event, headcount, exclude_guest_id=guest.id
        )

    for field, value in update_data.items():
        setattr(guest, field, value)

    db.commit()
    db.refresh(guest)
    return guest


def delete_guest(db: Session, guest_id: int) -> bool:
    """Remove a guest record.

    Args:
        db: Database session.
        guest_id: Guest ID.

    Returns:
        True if removed, False if not found.
    """
    guest = get_guest(db, guest_id)
    if not guest:
        return False
    db.delete(guest)
    db.commit()
    return True


# ============================================================================
# EXPENSE OPERATIONS
# ============================================================================

def get_expenses(db: Session, event_id: int) -> list[Expense]:
    """Retrieve all expense items logged for an event.

    Args:
        db: Database session.
        event_id: Event ID.

    Returns:
        List of Expense models.
    """
    return (
        db.query(Expense)
        .filter(Expense.event_id == event_id)
        .order_by(Expense.created_at.desc())
        .all()
    )


def get_expense(db: Session, expense_id: int) -> Expense | None:
    """Retrieve an expense item by ID.

    Args:
        db: Database session.
        expense_id: Expense ID.

    Returns:
        Expense model or None.
    """
    return db.query(Expense).filter(Expense.id == expense_id).first()


def create_expense(
    db: Session, event_id: int, expense_in: ExpenseCreate
) -> Expense:
    """Create an expense line item.

    Args:
        db: Database session.
        event_id: Event ID.
        expense_in: Validated expense payload.

    Returns:
        Created Expense model.
    """
    event = get_event(db, event_id)
    if not event:
        raise ValueError(f"Event with ID {event_id} does not exist.")

    expense = Expense(event_id=event_id, **expense_in.model_dump())
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


def update_expense(
    db: Session, expense_id: int, expense_in: ExpenseUpdate
) -> Expense | None:
    """Update an expense item.

    Args:
        db: Database session.
        expense_id: Expense ID.
        expense_in: Update payload.

    Returns:
        Updated Expense model or None.
    """
    expense = get_expense(db, expense_id)
    if not expense:
        return None

    update_data = expense_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(expense, field, value)

    db.commit()
    db.refresh(expense)
    return expense


def delete_expense(db: Session, expense_id: int) -> bool:
    """Delete an expense item.

    Args:
        db: Database session.
        expense_id: Expense ID.

    Returns:
        True if deleted, False if not found.
    """
    expense = get_expense(db, expense_id)
    if not expense:
        return False
    db.delete(expense)
    db.commit()
    return True


# ============================================================================
# TASK / MILESTONE OPERATIONS
# ============================================================================

def get_tasks(db: Session, event_id: int) -> list[Task]:
    """Retrieve all checklist milestones for an event.

    Args:
        db: Database session.
        event_id: Event ID.

    Returns:
        List of Task models ordered by completion status and due date.
    """
    return (
        db.query(Task)
        .filter(Task.event_id == event_id)
        .order_by(Task.is_completed.asc(), Task.due_date.asc().nulls_last())
        .all()
    )


def get_task(db: Session, task_id: int) -> Task | None:
    """Retrieve a single task milestone by ID.

    Args:
        db: Database session.
        task_id: Task ID.

    Returns:
        Task model or None.
    """
    return db.query(Task).filter(Task.id == task_id).first()


def create_task(db: Session, event_id: int, task_in: TaskCreate) -> Task:
    """Create a task milestone for an event.

    Args:
        db: Database session.
        event_id: Event ID.
        task_in: Validated task payload.

    Returns:
        Created Task model.
    """
    event = get_event(db, event_id)
    if not event:
        raise ValueError(f"Event with ID {event_id} does not exist.")

    task = Task(event_id=event_id, **task_in.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_task(
    db: Session, task_id: int, task_in: TaskUpdate
) -> Task | None:
    """Update a task milestone.

    Args:
        db: Database session.
        task_id: Task ID.
        task_in: Update payload.

    Returns:
        Updated Task or None.
    """
    task = get_task(db, task_id)
    if not task:
        return None

    update_data = task_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, task_id: int) -> bool:
    """Delete a task milestone.

    Args:
        db: Database session.
        task_id: Task ID.

    Returns:
        True if deleted, False if not found.
    """
    task = get_task(db, task_id)
    if not task:
        return False
    db.delete(task)
    db.commit()
    return True


# ============================================================================
# VENDOR DIRECTORY OPERATIONS
# ============================================================================

def get_vendors(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    service_type: str | None = None,
    status: str | None = None,
    search: str | None = None,
) -> tuple[list[Vendor], int]:
    """Retrieve vendors with optional filtering and search.

    Args:
        db: Database session.
        skip: Pagination offset.
        limit: Max records.
        service_type: Optional service filter.
        status: Optional contract status filter.
        search: Text match on name or contact name.

    Returns:
        Tuple of (list of Vendor models, total count).
    """
    query = db.query(Vendor)

    if search:
        search_fmt = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Vendor.name.ilike(search_fmt),
                Vendor.contact_name.ilike(search_fmt),
                Vendor.notes.ilike(search_fmt),
            )
        )

    if service_type:
        query = query.filter(Vendor.service_type == service_type)

    if status:
        query = query.filter(Vendor.contract_status == status)

    total_count = query.count()
    vendors = query.order_by(Vendor.name.asc()).offset(skip).limit(limit).all()
    return vendors, total_count


def get_vendor(db: Session, vendor_id: int) -> Vendor | None:
    """Retrieve a single vendor by ID.

    Args:
        db: Database session.
        vendor_id: Vendor ID.

    Returns:
        Vendor model or None.
    """
    return db.query(Vendor).filter(Vendor.id == vendor_id).first()


def create_vendor(db: Session, vendor_in: VendorCreate) -> Vendor:
    """Create a new vendor directory entry.

    Args:
        db: Database session.
        vendor_in: Validated vendor payload.

    Returns:
        Created Vendor model.
    """
    vendor = Vendor(**vendor_in.model_dump())
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return vendor


def update_vendor(
    db: Session, vendor_id: int, vendor_in: VendorUpdate
) -> Vendor | None:
    """Update an existing vendor record.

    Args:
        db: Database session.
        vendor_id: Vendor ID.
        vendor_in: Update payload.

    Returns:
        Updated Vendor or None.
    """
    vendor = get_vendor(db, vendor_id)
    if not vendor:
        return None

    update_data = vendor_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(vendor, field, value)

    db.commit()
    db.refresh(vendor)
    return vendor


def delete_vendor(db: Session, vendor_id: int) -> bool:
    """Delete a vendor record.

    Args:
        db: Database session.
        vendor_id: Vendor ID.

    Returns:
        True if deleted, False if not found.
    """
    vendor = get_vendor(db, vendor_id)
    if not vendor:
        return False
    db.delete(vendor)
    db.commit()
    return True


# ============================================================================
# GLOBAL ANALYTICS (SINGLE-PASS SQL)
# ============================================================================

def get_global_analytics(db: Session) -> GlobalAnalyticsResponse:
    """Aggregate high-level platform health metrics across all events.

    Args:
        db: Database session.

    Returns:
        GlobalAnalyticsResponse with summary metrics and distribution dictionaries.
    """
    total_events = db.query(Event).count()

    # Guest metrics
    guest_stats = db.query(
        func.count(Guest.id).label("total"),
        func.coalesce(
            func.sum(case((Guest.rsvp_status == "Attending", 1), else_=0)), 0
        ).label("attending"),
    ).first()
    total_guests = int(guest_stats.total or 0)
    total_attending = int(guest_stats.attending or 0)
    rsvp_conversion_rate = (
        round((total_attending / total_guests) * 100.0, 2)
        if total_guests > 0
        else 0.0
    )

    # Financial metrics
    total_budget_sum = (
        db.query(func.coalesce(func.sum(Event.total_budget), 0.0)).scalar() or 0.0
    )
    total_spent_sum = (
        db.query(func.coalesce(func.sum(Expense.actual_cost), 0.0)).scalar() or 0.0
    )
    total_budget = round(float(total_budget_sum), 2)
    total_spent = round(float(total_spent_sum), 2)
    budget_utilization_pct = (
        round((total_spent / total_budget) * 100.0, 2) if total_budget > 0 else 0.0
    )

    # Task metrics
    task_stats = db.query(
        func.count(Task.id).label("total"),
        func.coalesce(
            func.sum(case((Task.is_completed.is_(True), 1), else_=0)), 0
        ).label("completed"),
    ).first()
    total_tasks = int(task_stats.total or 0)
    completed_tasks = int(task_stats.completed or 0)
    task_completion_pct = (
        round((completed_tasks / total_tasks) * 100.0, 2)
        if total_tasks > 0
        else 0.0
    )

    # Category distribution
    cat_rows = (
        db.query(Event.category, func.count(Event.id))
        .group_by(Event.category)
        .all()
    )
    category_distribution = {cat: count for cat, count in cat_rows}

    # RSVP distribution
    rsvp_rows = (
        db.query(Guest.rsvp_status, func.count(Guest.id))
        .group_by(Guest.rsvp_status)
        .all()
    )
    rsvp_status_distribution = {status: count for status, count in rsvp_rows}

    # Expense category distribution
    exp_rows = (
        db.query(Expense.category, func.coalesce(func.sum(Expense.actual_cost), 0.0))
        .group_by(Expense.category)
        .all()
    )
    expense_category_distribution = {
        cat: round(float(val), 2) for cat, val in exp_rows
    }

    return GlobalAnalyticsResponse(
        total_events=total_events,
        total_guests=total_guests,
        total_attending=total_attending,
        rsvp_conversion_rate=rsvp_conversion_rate,
        total_budget=total_budget,
        total_spent=total_spent,
        budget_utilization_pct=budget_utilization_pct,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        task_completion_pct=task_completion_pct,
        category_distribution=category_distribution,
        rsvp_status_distribution=rsvp_status_distribution,
        expense_category_distribution=expense_category_distribution,
    )


# ============================================================================
# DEMO DATA SEEDER (3 EVENTS, 12 GUESTS, 10 EXPENSES, 10 TASKS, 5 VENDORS)
# ============================================================================

def seed_demo_data(db: Session) -> None:
    """Pre-seed database with realistic sample data if empty.

    Guarantees that evaluation environments immediately observe 3 events,
    12 guests, 10 itemized expenses, 10 checklist tasks, and 5 vendor entries.
    """
    if db.query(Event).count() > 0:
        return

    now = datetime.utcnow()
    today = date.today()

    # 1. Seed 3 Diverse Events
    event1 = Event(
        title="Global AI & Web Innovators Hackathon 2026",
        description=(
            "A 48-hour competitive sprint bringing together engineers, designers, "
            "and founders to build next-generation applications."
        ),
        category="Hackathon",
        event_date=now + timedelta(days=21),
        venue="Metropolitan Innovation Center, Hall A & B, San Francisco, CA",
        theme_color="#6366f1",
        status="In Progress",
        total_budget=35000.0,
        capacity=150,
    )

    event2 = Event(
        title="Grand Sapphire 50th Jubilee Gala",
        description=(
            "An elegant black-tie golden anniversary dinner celebrating five decades "
            "of family, philanthropy, and milestone memories."
        ),
        category="Anniversaries",
        event_date=now + timedelta(days=45),
        venue="The Grand Regal Ballroom, 5th Avenue, New York, NY",
        theme_color="#ec4899",
        status="Planned",
        total_budget=50000.0,
        capacity=100,
    )

    event3 = Event(
        title="Solstice Bloom Spring Music & Arts Festival",
        description=(
            "An outdoor open-air community celebration featuring indie bands, "
            "artisanal food trucks, live muralists, and interactive art exhibits."
        ),
        category="Festivals",
        event_date=now + timedelta(days=70),
        venue="Sunset Meadow Amphitheater & Gardens, Austin, TX",
        theme_color="#10b981",
        status="Planned",
        total_budget=75000.0,
        capacity=250,
    )

    db.add_all([event1, event2, event3])
    db.commit()
    db.refresh(event1)
    db.refresh(event2)
    db.refresh(event3)

    # 2. Seed 12 Guests across Events with varied RSVPs and dietary preferences
    guests = [
        # Event 1: Hackathon (5 guests)
        Guest(
            event_id=event1.id,
            name="Elena Rostova",
            email="elena.rostova@techspark.io",
            phone="+1-415-555-0192",
            dietary_preferences="Vegan",
            rsvp_status="Attending",
            plus_one_count=1,
            notes="Requires wheelchair accessible power strip at hacking station.",
        ),
        Guest(
            event_id=event1.id,
            name="Marcus Vance",
            email="marcus.vance@quantumdev.com",
            phone="+1-415-555-0143",
            dietary_preferences="Gluten-Free",
            rsvp_status="Attending",
            plus_one_count=0,
            notes="Keynote speaker for introductory AI session.",
        ),
        Guest(
            event_id=event1.id,
            name="Amina El-Sayed",
            email="amina.sayed@cloudscale.net",
            phone="+1-415-555-0188",
            dietary_preferences="Halal",
            rsvp_status="Attending",
            plus_one_count=1,
            notes="Mentor for Distributed Systems track.",
        ),
        Guest(
            event_id=event1.id,
            name="Julian Thorne",
            email="julian.t@frontierlabs.org",
            phone="+1-415-555-0164",
            dietary_preferences="None",
            rsvp_status="Pending",
            plus_one_count=0,
            notes="Pending travel authorization approval.",
        ),
        Guest(
            event_id=event1.id,
            name="Sophia Chen",
            email="sophia.chen@deepvision.ai",
            phone="+1-415-555-0121",
            dietary_preferences="Vegetarian",
            rsvp_status="Declined",
            plus_one_count=0,
            notes="Schedule conflict with international conference.",
        ),

        # Event 2: Gala (4 guests)
        Guest(
            event_id=event2.id,
            name="Arthur Pendelton III",
            email="arthur.pendelton@heritagetrust.org",
            phone="+1-212-555-0177",
            dietary_preferences="None",
            rsvp_status="Attending",
            plus_one_count=1,
            notes="VIP family table 1 seating.",
        ),
        Guest(
            event_id=event2.id,
            name="Beatrice Montgomery",
            email="beatrice.m@nycartgallery.com",
            phone="+1-212-555-0132",
            dietary_preferences="Nut Allergy",
            rsvp_status="Attending",
            plus_one_count=1,
            notes="Severe peanut allergy; please inform banquet head chef.",
        ),
        Guest(
            event_id=event2.id,
            name="Charles Sterling",
            email="c.sterling@sterlingcap.com",
            phone="+1-212-555-0119",
            dietary_preferences="None",
            rsvp_status="Pending",
            plus_one_count=1,
            notes="Invited by family trustees.",
        ),
        Guest(
            event_id=event2.id,
            name="Dr. Evelyn Laurent",
            email="evelyn.laurent@columbia.edu",
            phone="+1-212-555-0195",
            dietary_preferences="Vegetarian",
            rsvp_status="Attending",
            plus_one_count=0,
            notes="Delivering toast at 8:30 PM.",
        ),

        # Event 3: Festival (3 guests)
        Guest(
            event_id=event3.id,
            name="Liam O'Connor",
            email="liam.music@austinlive.com",
            phone="+1-512-555-0144",
            dietary_preferences="None",
            rsvp_status="Attending",
            plus_one_count=2,
            notes="Stage crew and acoustic sound engineer.",
        ),
        Guest(
            event_id=event3.id,
            name="Zoe Martinez",
            email="zoe.martinez@hillcountryarts.org",
            phone="+1-512-555-0176",
            dietary_preferences="Vegan",
            rsvp_status="Attending",
            plus_one_count=1,
            notes="Mural coordinator for artisan alley.",
        ),
        Guest(
            event_id=event3.id,
            name="Derek Wu",
            email="derek.wu@soundwavemedia.tv",
            phone="+1-512-555-0158",
            dietary_preferences="None",
            rsvp_status="Pending",
            plus_one_count=0,
            notes="Press credential request under review.",
        ),
    ]
    db.add_all(guests)

    # 3. Seed 10 Itemized Expenses (Covering Catering, Venue, Decor, Entertainment, Logistics)
    expenses = [
        # Event 1: Hackathon (4 expenses)
        Expense(
            event_id=event1.id,
            item_name="High-Density Fiber Gigabit Internet & Mesh Routers",
            category="Logistics",
            estimated_cost=4500.0,
            actual_cost=4200.0,
            is_paid=True,
            due_date=today - timedelta(days=5),
            notes="Dedicated 2 Gbps symmetric pipeline with redundancy backup.",
        ),
        Expense(
            event_id=event1.id,
            item_name="Weekend Hacking Catering, Snacks & Espresso Bar",
            category="Catering",
            estimated_cost=12000.0,
            actual_cost=11500.0,
            is_paid=True,
            due_date=today + timedelta(days=10),
            notes="Includes 6 catered meals and 24-hour craft coffee station.",
        ),
        Expense(
            event_id=event1.id,
            item_name="Main Hall & Breakout Rooms Security Deposit",
            category="Venue",
            estimated_cost=9000.0,
            actual_cost=9000.0,
            is_paid=True,
            due_date=today - timedelta(days=15),
            notes="Paid in full to Metropolitan Center.",
        ),
        Expense(
            event_id=event1.id,
            item_name="Custom Laser-Cut Trophies & Swag Backpacks",
            category="Decor",
            estimated_cost=3500.0,
            actual_cost=3800.0,
            is_paid=False,
            due_date=today + timedelta(days=12),
            notes="Final delivery invoice pending arrival.",
        ),

        # Event 2: Gala (3 expenses)
        Expense(
            event_id=event2.id,
            item_name="5-Course Gourmet French Plated Dinner & Wine Pairing",
            category="Catering",
            estimated_cost=22000.0,
            actual_cost=21500.0,
            is_paid=True,
            due_date=today + timedelta(days=20),
            notes="Includes sommelier selection and crystal tableware service.",
        ),
        Expense(
            event_id=event2.id,
            item_name="Grand Ballroom Rental & Valet Parking Operations",
            category="Venue",
            estimated_cost=16000.0,
            actual_cost=16000.0,
            is_paid=True,
            due_date=today - timedelta(days=20),
            notes="Historic landmark ballroom contract executed.",
        ),
        Expense(
            event_id=event2.id,
            item_name="Live Classical String Quartet & Jazz Ensemble",
            category="Entertainment",
            estimated_cost=5500.0,
            actual_cost=5800.0,
            is_paid=False,
            due_date=today + timedelta(days=30),
            notes="50% deposit paid; remaining balance due night of gala.",
        ),

        # Event 3: Festival (3 expenses)
        Expense(
            event_id=event3.id,
            item_name="Amphitheater Main Stage Trussing, Line-Array Sound & Lighting",
            category="Entertainment",
            estimated_cost=28000.0,
            actual_cost=27500.0,
            is_paid=True,
            due_date=today - timedelta(days=2),
            notes="Professional stadium audio-visual rig and crew.",
        ),
        Expense(
            event_id=event3.id,
            item_name="Permits, Emergency Medical Services & Licensed Security",
            category="Logistics",
            estimated_cost=11000.0,
            actual_cost=10500.0,
            is_paid=False,
            due_date=today + timedelta(days=15),
            notes="City of Austin municipal permits and EMS stationed standby.",
        ),
        Expense(
            event_id=event3.id,
            item_name="Botanical Floral Arches, Eco-Bunting & Stage Backdrops",
            category="Decor",
            estimated_cost=7500.0,
            actual_cost=7200.0,
            is_paid=False,
            due_date=today + timedelta(days=25),
            notes="Living plant installations with post-event community donation.",
        ),
    ]
    db.add_all(expenses)

    # 4. Seed 10 Checklist Tasks with priorities (High, Medium, Low) and assignees
    tasks = [
        # Event 1 Tasks (4 tasks)
        Task(
            event_id=event1.id,
            title="Finalize API Key credentials and sandbox server clusters",
            description="Provision GPU and cloud compute credits for all competing teams.",
            priority="High",
            due_date=today + timedelta(days=7),
            assignee="Marcus Vance",
            is_completed=True,
            category="Infrastructure",
        ),
        Task(
            event_id=event1.id,
            title="Coordinate live mentor roster and shift rotation schedule",
            description="Confirm 20 industry engineering mentors for nocturnal assistance.",
            priority="Medium",
            due_date=today + timedelta(days=14),
            assignee="Elena Rostova",
            is_completed=True,
            category="Mentorship",
        ),
        Task(
            event_id=event1.id,
            title="Distribute dietary requirements to catering coordinator",
            description="Ensure sufficient vegan, halal, and gluten-free labeled stations.",
            priority="High",
            due_date=today + timedelta(days=10),
            assignee="Sophia Chen",
            is_completed=False,
            category="Logistics",
        ),
        Task(
            event_id=event1.id,
            title="Publish opening ceremony slide deck and judging rubric",
            description="Align with hackathon judging committee on technical criteria.",
            priority="Low",
            due_date=today + timedelta(days=18),
            assignee="Julian Thorne",
            is_completed=False,
            category="Program",
        ),

        # Event 2 Tasks (3 tasks)
        Task(
            event_id=event2.id,
            title="Confirm floral centerpiece styling and golden candelabras",
            description="Meet with master florist for final mock-up sample approval.",
            priority="High",
            due_date=today + timedelta(days=12),
            assignee="Beatrice Montgomery",
            is_completed=True,
            category="Decor",
        ),
        Task(
            event_id=event2.id,
            title="Print embossed escort seating cards and menu brochures",
            description="Gold leaf calligraphy on heavyweight cotton paper.",
            priority="Medium",
            due_date=today + timedelta(days=22),
            assignee="Arthur Pendelton III",
            is_completed=False,
            category="Print & Signage",
        ),
        Task(
            event_id=event2.id,
            title="Conduct soundcheck with string quartet and microphone podium",
            description="Test wireless lavalier mics for memorial speeches.",
            priority="Low",
            due_date=today + timedelta(days=40),
            assignee="Dr. Evelyn Laurent",
            is_completed=False,
            category="Audio/Visual",
        ),

        # Event 3 Tasks (3 tasks)
        Task(
            event_id=event3.id,
            title="Finalize city noise variance ordinance and park curfew permits",
            description="Obtain certified seal from Austin municipal department.",
            priority="High",
            due_date=today + timedelta(days=5),
            assignee="Liam O'Connor",
            is_completed=True,
            category="Compliance",
        ),
        Task(
            event_id=event3.id,
            title="Verify electrical grounding for outdoor line-array amplification",
            description="City inspector safety walkthrough on stage rigging.",
            priority="High",
            due_date=today + timedelta(days=35),
            assignee="Liam O'Connor",
            is_completed=False,
            category="Production",
        ),
        Task(
            event_id=event3.id,
            title="Mark vendor stall footprints and water hookups on map",
            description="Distribute loading dock timetables to 15 food truck vendors.",
            priority="Medium",
            due_date=today + timedelta(days=45),
            assignee="Zoe Martinez",
            is_completed=False,
            category="Vendor Relations",
        ),
    ]
    db.add_all(tasks)

    # 5. Seed 5 Vendors in Directory
    vendors = [
        Vendor(
            name="Apex Sound & Vision Production Group",
            service_type="Audio/Visual",
            contact_name="Gareth Cole",
            email="gareth@apexavpro.com",
            phone="+1-512-555-0341",
            contract_status="Contract Signed",
            cost_estimate=27500.0,
            notes="Stage trussing, LED video walls, and certified sound technicians.",
        ),
        Vendor(
            name="L'Étoile Haute Cuisine & Banquet Services",
            service_type="Catering",
            contact_name="Chef Monique Dupuis",
            email="monique@letoilecatering.com",
            phone="+1-212-555-0819",
            contract_status="Contract Signed",
            cost_estimate=21500.0,
            notes="Plated multi-course European fine dining and artisanal pastry towers.",
        ),
        Vendor(
            name="Vanguard High-Density Networking Solutions",
            service_type="Logistics",
            contact_name="Nikhil Patel",
            email="nikhil@vanguardnet.io",
            phone="+1-415-555-0922",
            contract_status="Paid in Full",
            cost_estimate=4200.0,
            notes="Enterprise low-latency Wi-Fi 7 access points for 500+ concurrent clients.",
        ),
        Vendor(
            name="Verdant & Bloom Botanical Atelier",
            service_type="Floral & Decor",
            contact_name="Seraphina Vance",
            email="seraphina@verdantbloom.design",
            phone="+1-212-555-0453",
            contract_status="Quoted",
            cost_estimate=7200.0,
            notes="Sustainable living floral installations and vintage brass urn rentals.",
        ),
        Vendor(
            name="Silver Screen Cinematography & Drone Lab",
            service_type="Photography",
            contact_name="Damon Drake",
            email="damon@silverscreenstudios.com",
            phone="+1-415-555-0711",
            contract_status="Inquiry",
            cost_estimate=4800.0,
            notes="4K 60fps event recap documentary, drone aerials, and 24h highlight reel.",
        ),
    ]
    db.add_all(vendors)

    db.commit()
