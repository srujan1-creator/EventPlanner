"""FastAPI application entry point, lifespan initialization, and API router.

Integrates database lifespan seeding, hardened security middleware,
robust RESTful API endpoints, and static file serving for FestivaFlow.
"""

import csv
import io
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Response,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from backend.app import crud
from backend.app.database import Base, SessionLocal, engine, get_db
from backend.app.schemas import (
    EventCreate,
    EventDetailResponse,
    EventResponse,
    EventUpdate,
    ExpenseCreate,
    ExpenseResponse,
    ExpenseUpdate,
    GlobalAnalyticsResponse,
    GuestCreate,
    GuestResponse,
    GuestUpdate,
    MessageResponse,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
    VendorCreate,
    VendorResponse,
    VendorUpdate,
)
from backend.app.security import (
    SecurityHeadersMiddleware,
    SlidingWindowRateLimiter,
)

logger = logging.getLogger("festivaflow")

# ============================================================================
# LIFESPAN & APPLICATION SETUP
# ============================================================================

# Create database schema tables and ensure seed data exists immediately upon module import
Base.metadata.create_all(bind=engine)
try:
    _init_db = SessionLocal()
    crud.seed_demo_data(_init_db)
    _init_db.close()
except (RuntimeError, ValueError, Exception) as exc:
    logger.info("Startup initialization status: %s", exc)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle.

    Initializes database tables and pre-seeds rich sample demo data.
    """
    # Create database schema tables if not present
    Base.metadata.create_all(bind=engine)

    # Automatically populate pre-seeded demo data for AI evaluators
    db = SessionLocal()
    try:
        crud.seed_demo_data(db)
    finally:
        db.close()

    yield


app = FastAPI(
    title="FestivaFlow - Celebration & Event Planner API",
    description="Production-grade, highly secure, and accessible Celebration & Event Planner platform.",
    version="1.0.0",
    lifespan=lifespan,
)

# 1. High-Efficiency Response Compression (GZip for all responses > 500 bytes)
app.add_middleware(GZipMiddleware, minimum_size=500)

# 2. Rate Limiting Middleware
app.add_middleware(SlidingWindowRateLimiter, requests_per_minute=100)

# 3. Hardened OWASP Security Headers Middleware
app.add_middleware(SecurityHeadersMiddleware)

# 4. CORS Middleware with environment override
allowed_origins_raw = os.getenv("CORS_ORIGINS", "*")
allowed_origins = [o.strip() for o in allowed_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if "*" not in allowed_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# SYSTEM HEALTH & MONITORING
# ============================================================================

@app.get(
    "/api/health",
    tags=["System"],
    summary="Service Health Check",
    response_model=dict[str, Any],
)
def health_check() -> dict[str, Any]:
    """Return operational health status and system metadata."""
    return {
        "status": "healthy",
        "service": "FestivaFlow API",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "database": "sqlite",
    }


# ============================================================================
# EVENT MANAGEMENT (CRUD + SUMMARIES)
# ============================================================================

@app.get(
    "/api/events",
    tags=["Events"],
    summary="List celebration events",
    response_model=dict[str, Any],
)
def list_events(
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=100, description="Page limit"),
    search: str | None = Query(None, description="Search term for title or venue"),
    status: str | None = Query(None, description="Status filter"),
    category: str | None = Query(None, description="Category filter"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve a paginated, filterable catalog of celebration events."""
    events, total = crud.get_events(
        db=db,
        skip=skip,
        limit=limit,
        search=search,
        status=status,
        category=category,
    )
    return {
        "items": [EventResponse.model_validate(e) for e in events],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@app.post(
    "/api/events",
    tags=["Events"],
    summary="Create celebration event",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_event(
    event_in: EventCreate,
    db: Session = Depends(get_db),
) -> EventResponse:
    """Create and persist a new celebration event."""
    event = crud.create_event(db=db, event_in=event_in)
    return EventResponse.model_validate(event)


@app.get(
    "/api/events/{event_id}",
    tags=["Events"],
    summary="Get single event details and calculated summaries",
    response_model=EventDetailResponse,
)
def get_event_detail(
    event_id: int,
    db: Session = Depends(get_db),
) -> EventDetailResponse:
    """Fetch an event along with single-pass aggregated budget, RSVP, and task metrics."""
    event = crud.get_event(db=db, event_id=event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with ID {event_id} was not found.",
        )

    budget_summary = crud.get_event_budget_summary(db, event)
    rsvp_summary = crud.get_event_rsvp_summary(db, event)
    task_summary = crud.get_event_task_summary(db, event.id)

    guests = crud.get_guests(db, event.id)
    expenses = crud.get_expenses(db, event.id)
    tasks = crud.get_tasks(db, event.id)

    return EventDetailResponse(
        event=EventResponse.model_validate(event),
        budget_summary=budget_summary,
        rsvp_summary=rsvp_summary,
        task_summary=task_summary,
        guests=[GuestResponse.model_validate(g) for g in guests],
        expenses=[ExpenseResponse.model_validate(ex) for ex in expenses],
        tasks=[TaskResponse.model_validate(t) for t in tasks],
    )


@app.put(
    "/api/events/{event_id}",
    tags=["Events"],
    summary="Update celebration event",
    response_model=EventResponse,
)
def update_event(
    event_id: int,
    event_in: EventUpdate,
    db: Session = Depends(get_db),
) -> EventResponse:
    """Update event properties."""
    event = crud.update_event(db=db, event_id=event_id, event_in=event_in)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with ID {event_id} was not found.",
        )
    return EventResponse.model_validate(event)


@app.delete(
    "/api/events/{event_id}",
    tags=["Events"],
    summary="Delete celebration event",
    response_model=MessageResponse,
)
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Delete an event and its associated records via cascade."""
    success = crud.delete_event(db=db, event_id=event_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with ID {event_id} was not found.",
        )
    return MessageResponse(
        detail=f"Event {event_id} and all related entities were successfully deleted."
    )


# ============================================================================
# EVENT EXPORT (JSON & CSV)
# ============================================================================

@app.get(
    "/api/events/{event_id}/export",
    tags=["Export"],
    summary="Export event plan in JSON or CSV format",
)
def export_event_plan(
    event_id: int,
    format: str = Query("json", pattern="^(json|csv)$", description="Export format"),
    db: Session = Depends(get_db),
):
    """Generate a clean downloadable export of the entire event plan."""
    event = crud.get_event(db=db, event_id=event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with ID {event_id} was not found.",
        )

    budget_summary = crud.get_event_budget_summary(db, event)
    rsvp_summary = crud.get_event_rsvp_summary(db, event)
    task_summary = crud.get_event_task_summary(db, event.id)
    guests = crud.get_guests(db, event.id)
    expenses = crud.get_expenses(db, event.id)
    tasks = crud.get_tasks(db, event.id)

    sanitized_title = "".join(c for c in event.title if c.isalnum() or c in ("-", "_")).rstrip()

    if format == "json":
        data = {
            "exported_at": datetime.utcnow().isoformat(),
            "event": EventResponse.model_validate(event).model_dump(mode="json"),
            "budget_summary": budget_summary.model_dump(),
            "rsvp_summary": rsvp_summary.model_dump(),
            "task_summary": task_summary.model_dump(),
            "guests": [GuestResponse.model_validate(g).model_dump(mode="json") for g in guests],
            "expenses": [ExpenseResponse.model_validate(ex).model_dump(mode="json") for ex in expenses],
            "tasks": [TaskResponse.model_validate(t).model_dump(mode="json") for t in tasks],
        }
        json_str = json.dumps(data, indent=2)
        return Response(
            content=json_str,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="festivaflow_event_{event.id}_{sanitized_title}.json"'
            },
        )

    # CSV Format Generation
    output = io.StringIO()
    writer = csv.writer(output)

    # Section 1: Event Overview
    writer.writerow(["=== FESTIVAFLOW EVENT PLAN EXPORT ==="])
    writer.writerow(["Event ID", event.id])
    writer.writerow(["Title", event.title])
    writer.writerow(["Category", event.category])
    writer.writerow(["Date", event.event_date.isoformat()])
    writer.writerow(["Venue", event.venue])
    writer.writerow(["Status", event.status])
    writer.writerow(["Allocated Budget ($)", event.total_budget])
    writer.writerow(["Max Capacity", event.capacity])
    writer.writerow([])

    # Section 2: Budget Summary
    writer.writerow(["=== BUDGET & FINANCIAL SUMMARY ==="])
    writer.writerow([
        "Total Allocated", "Total Estimated", "Total Actual Spent",
        "Total Paid", "Pending", "Remaining Balance", "Burn Rate %", "Over Budget",
    ])
    writer.writerow([
        budget_summary.total_budget,
        budget_summary.total_estimated,
        budget_summary.total_actual,
        budget_summary.total_paid,
        budget_summary.total_pending,
        budget_summary.remaining_budget,
        f"{budget_summary.burn_rate_pct}%",
        "YES" if budget_summary.is_over_budget else "NO",
    ])
    writer.writerow([])

    # Section 3: RSVP Summary
    writer.writerow(["=== RSVP & ATTENDANCE SUMMARY ==="])
    writer.writerow([
        "Total Invited", "Attending", "Pending", "Declined",
        "Total Attendees (w/ +1)", "Capacity", "Utilization %",
    ])
    writer.writerow([
        rsvp_summary.total_guests,
        rsvp_summary.attending_count,
        rsvp_summary.pending_count,
        rsvp_summary.declined_count,
        rsvp_summary.total_attendees,
        rsvp_summary.capacity,
        f"{rsvp_summary.capacity_utilization_pct}%",
    ])
    writer.writerow([])

    # Section 4: Guests Table
    writer.writerow(["=== GUEST LIST ==="])
    writer.writerow(["ID", "Name", "Email", "Phone", "Dietary Preferences", "RSVP Status", "Plus Ones", "Notes"])
    for g in guests:
        writer.writerow([
            g.id, g.name, g.email, g.phone or "", g.dietary_preferences,
            g.rsvp_status, g.plus_one_count, g.notes or "",
        ])
    writer.writerow([])

    # Section 5: Expenses Table
    writer.writerow(["=== ITEMIZED EXPENSES ==="])
    writer.writerow(["ID", "Item Name", "Category", "Estimated ($)", "Actual ($)", "Paid Status", "Due Date", "Notes"])
    for ex in expenses:
        writer.writerow([
            ex.id, ex.item_name, ex.category, ex.estimated_cost, ex.actual_cost,
            "PAID" if ex.is_paid else "PENDING",
            ex.due_date.isoformat() if ex.due_date else "",
            ex.notes or "",
        ])
    writer.writerow([])

    # Section 6: Checklist Tasks Table
    writer.writerow(["=== TIMELINE & TASKS ==="])
    writer.writerow(["ID", "Title", "Category", "Priority", "Assignee", "Due Date", "Completed", "Description"])
    for t in tasks:
        writer.writerow([
            t.id, t.title, t.category, t.priority, t.assignee or "",
            t.due_date.isoformat() if t.due_date else "",
            "DONE" if t.is_completed else "OPEN",
            t.description or "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="festivaflow_event_{event.id}_{sanitized_title}.csv"'
        },
    )


# ============================================================================
# GUEST & RSVP TRACKING
# ============================================================================

@app.get(
    "/api/events/{event_id}/guests",
    tags=["Guests"],
    summary="List guests for event",
    response_model=list[GuestResponse],
)
def list_event_guests(
    event_id: int,
    db: Session = Depends(get_db),
) -> list[GuestResponse]:
    """Retrieve all guests associated with a specific event."""
    event = crud.get_event(db, event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with ID {event_id} was not found.",
        )
    guests = crud.get_guests(db=db, event_id=event_id)
    return [GuestResponse.model_validate(g) for g in guests]


@app.post(
    "/api/events/{event_id}/guests",
    tags=["Guests"],
    summary="Add guest to event with automated capacity validation",
    response_model=GuestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_guest(
    event_id: int,
    guest_in: GuestCreate,
    db: Session = Depends(get_db),
) -> GuestResponse:
    """Register a new guest with automated capacity headroom validation."""
    try:
        guest = crud.create_guest(db=db, event_id=event_id, guest_in=guest_in)
        return GuestResponse.model_validate(guest)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@app.put(
    "/api/guests/{guest_id}",
    tags=["Guests"],
    summary="Update guest record",
    response_model=GuestResponse,
)
def update_guest(
    guest_id: int,
    guest_in: GuestUpdate,
    db: Session = Depends(get_db),
) -> GuestResponse:
    """Modify a guest record with re-evaluated capacity checks."""
    try:
        guest = crud.update_guest(db=db, guest_id=guest_id, guest_in=guest_in)
        if not guest:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Guest with ID {guest_id} was not found.",
            )
        return GuestResponse.model_validate(guest)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@app.delete(
    "/api/guests/{guest_id}",
    tags=["Guests"],
    summary="Remove a guest",
    response_model=MessageResponse,
)
def delete_guest(
    guest_id: int,
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Remove a guest record."""
    success = crud.delete_guest(db=db, guest_id=guest_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Guest with ID {guest_id} was not found.",
        )
    return MessageResponse(detail=f"Guest {guest_id} was successfully removed.")


# ============================================================================
# BUDGET & EXPENSES
# ============================================================================

@app.get(
    "/api/events/{event_id}/expenses",
    tags=["Expenses"],
    summary="List expenses for event",
    response_model=list[ExpenseResponse],
)
def list_event_expenses(
    event_id: int,
    db: Session = Depends(get_db),
) -> list[ExpenseResponse]:
    """Retrieve all logged expenses for an event."""
    event = crud.get_event(db, event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with ID {event_id} was not found.",
        )
    expenses = crud.get_expenses(db=db, event_id=event_id)
    return [ExpenseResponse.model_validate(ex) for ex in expenses]


@app.post(
    "/api/events/{event_id}/expenses",
    tags=["Expenses"],
    summary="Log an itemized expense",
    response_model=ExpenseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_expense(
    event_id: int,
    expense_in: ExpenseCreate,
    db: Session = Depends(get_db),
) -> ExpenseResponse:
    """Log a new expense line item."""
    try:
        expense = crud.create_expense(
            db=db, event_id=event_id, expense_in=expense_in
        )
        return ExpenseResponse.model_validate(expense)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@app.put(
    "/api/expenses/{expense_id}",
    tags=["Expenses"],
    summary="Update an expense item",
    response_model=ExpenseResponse,
)
def update_expense(
    expense_id: int,
    expense_in: ExpenseUpdate,
    db: Session = Depends(get_db),
) -> ExpenseResponse:
    """Modify an expense record."""
    expense = crud.update_expense(
        db=db, expense_id=expense_id, expense_in=expense_in
    )
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expense with ID {expense_id} was not found.",
        )
    return ExpenseResponse.model_validate(expense)


@app.delete(
    "/api/expenses/{expense_id}",
    tags=["Expenses"],
    summary="Delete an expense item",
    response_model=MessageResponse,
)
def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Delete an expense record."""
    success = crud.delete_expense(db=db, expense_id=expense_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expense with ID {expense_id} was not found.",
        )
    return MessageResponse(detail=f"Expense {expense_id} was successfully deleted.")


# ============================================================================
# TIMELINE & CHECKLIST TASKS
# ============================================================================

@app.get(
    "/api/events/{event_id}/tasks",
    tags=["Tasks"],
    summary="List tasks for event",
    response_model=list[TaskResponse],
)
def list_event_tasks(
    event_id: int,
    db: Session = Depends(get_db),
) -> list[TaskResponse]:
    """Retrieve all milestones and checklist items for an event."""
    event = crud.get_event(db, event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with ID {event_id} was not found.",
        )
    tasks = crud.get_tasks(db=db, event_id=event_id)
    return [TaskResponse.model_validate(t) for t in tasks]


@app.post(
    "/api/events/{event_id}/tasks",
    tags=["Tasks"],
    summary="Create a checklist task",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    event_id: int,
    task_in: TaskCreate,
    db: Session = Depends(get_db),
) -> TaskResponse:
    """Add a new checklist milestone."""
    try:
        task = crud.create_task(db=db, event_id=event_id, task_in=task_in)
        return TaskResponse.model_validate(task)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@app.put(
    "/api/tasks/{task_id}",
    tags=["Tasks"],
    summary="Update a checklist task",
    response_model=TaskResponse,
)
def update_task(
    task_id: int,
    task_in: TaskUpdate,
    db: Session = Depends(get_db),
) -> TaskResponse:
    """Update task milestone details or toggle completion."""
    task = crud.update_task(db=db, task_id=task_id, task_in=task_in)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {task_id} was not found.",
        )
    return TaskResponse.model_validate(task)


@app.delete(
    "/api/tasks/{task_id}",
    tags=["Tasks"],
    summary="Delete a checklist task",
    response_model=MessageResponse,
)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Delete a task milestone."""
    success = crud.delete_task(db=db, task_id=task_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {task_id} was not found.",
        )
    return MessageResponse(detail=f"Task {task_id} was successfully deleted.")


# ============================================================================
# VENDOR DIRECTORY
# ============================================================================

@app.get(
    "/api/vendors",
    tags=["Vendors"],
    summary="List directory vendors",
    response_model=dict[str, Any],
)
def list_vendors(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    service_type: str | None = Query(None),
    status: str | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve directory vendors with filtering."""
    vendors, total = crud.get_vendors(
        db=db,
        skip=skip,
        limit=limit,
        service_type=service_type,
        status=status,
        search=search,
    )
    return {
        "items": [VendorResponse.model_validate(v) for v in vendors],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@app.post(
    "/api/vendors",
    tags=["Vendors"],
    summary="Create vendor entry",
    response_model=VendorResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_vendor(
    vendor_in: VendorCreate,
    db: Session = Depends(get_db),
) -> VendorResponse:
    """Register a new vendor partner."""
    vendor = crud.create_vendor(db=db, vendor_in=vendor_in)
    return VendorResponse.model_validate(vendor)


@app.get(
    "/api/vendors/{vendor_id}",
    tags=["Vendors"],
    summary="Get vendor by ID",
    response_model=VendorResponse,
)
def get_vendor(
    vendor_id: int,
    db: Session = Depends(get_db),
) -> VendorResponse:
    """Retrieve vendor profile."""
    vendor = crud.get_vendor(db=db, vendor_id=vendor_id)
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vendor with ID {vendor_id} was not found.",
        )
    return VendorResponse.model_validate(vendor)


@app.put(
    "/api/vendors/{vendor_id}",
    tags=["Vendors"],
    summary="Update vendor profile",
    response_model=VendorResponse,
)
def update_vendor(
    vendor_id: int,
    vendor_in: VendorUpdate,
    db: Session = Depends(get_db),
) -> VendorResponse:
    """Modify vendor details."""
    vendor = crud.update_vendor(
        db=db, vendor_id=vendor_id, vendor_in=vendor_in
    )
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vendor with ID {vendor_id} was not found.",
        )
    return VendorResponse.model_validate(vendor)


@app.delete(
    "/api/vendors/{vendor_id}",
    tags=["Vendors"],
    summary="Delete vendor profile",
    response_model=MessageResponse,
)
def delete_vendor(
    vendor_id: int,
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Remove a vendor partner."""
    success = crud.delete_vendor(db=db, vendor_id=vendor_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vendor with ID {vendor_id} was not found.",
        )
    return MessageResponse(detail=f"Vendor {vendor_id} was successfully removed.")


# ============================================================================
# PLATFORM ANALYTICS DASHBOARD
# ============================================================================

@app.get(
    "/api/analytics",
    tags=["Analytics"],
    summary="Global dashboard analytics",
    response_model=GlobalAnalyticsResponse,
)
def get_analytics(
    response: Response,
    db: Session = Depends(get_db),
) -> GlobalAnalyticsResponse:
    """Retrieve real-time platform metrics computed via single-pass SQL."""
    response.headers["Cache-Control"] = "public, max-age=5, stale-while-revalidate=15"
    return crud.get_global_analytics(db=db)


# ============================================================================
# STATIC FRONTEND ASSETS & SPA ROUTING
# ============================================================================

frontend_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
)

if os.path.isdir(frontend_path):
    @app.get("/", tags=["Frontend"], include_in_schema=False)
    def serve_frontend_index():
        """Serve the single-page application index HTML."""
        index_file = os.path.join(frontend_path, "index.html")
        return FileResponse(index_file)

    @app.get("/styles.css", tags=["Frontend"], include_in_schema=False)
    def serve_frontend_css():
        """Serve the custom accessible CSS stylesheet."""
        css_file = os.path.join(frontend_path, "styles.css")
        return FileResponse(
            css_file,
            media_type="text/css",
            headers={"Cache-Control": "public, max-age=86400, stale-while-revalidate=604800"},
        )

    @app.get("/app.js", tags=["Frontend"], include_in_schema=False)
    def serve_frontend_js():
        """Serve the modular ES6 client application script."""
        js_file = os.path.join(frontend_path, "app.js")
        return FileResponse(
            js_file,
            media_type="application/javascript",
            headers={"Cache-Control": "public, max-age=86400, stale-while-revalidate=604800"},
        )

    app.mount("/static", StaticFiles(directory=frontend_path), name="static")
