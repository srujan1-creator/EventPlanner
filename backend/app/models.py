"""SQLAlchemy ORM models defining the relational database schema for FestivaFlow.

Includes Event, Guest, Expense, Task, and Vendor entities with explicit SQLite
indexes for high-performance querying and referential integrity constraints.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from backend.app.database import Base


class Event(Base):
    """Represents a celebration or planned event entity.

    Attributes:
        id: Primary key unique identifier.
        title: Title/name of the celebration event.
        description: Extended description or agenda for the event.
        category: Event classification (e.g., Birthday, Wedding, Hackathon, Festival, Anniversary).
        event_date: Scheduled datetime for the celebration.
        venue: Physical or virtual location of the venue.
        theme_color: Hex color code representing event visual branding.
        status: Current lifecycle state (Planned, In Progress, Completed, Cancelled).
        total_budget: Total allocated financial budget in USD.
        capacity: Maximum allowable guests (including plus-ones).
        created_at: UTC timestamp when the record was created.
        updated_at: UTC timestamp when the record was last modified.
        guests: One-to-many relationship with associated Guest records.
        expenses: One-to-many relationship with associated Expense records.
        tasks: One-to-many relationship with associated Task milestones.
    """

    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(150), nullable=False, index=True)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False, index=True)
    event_date = Column(DateTime, nullable=False, index=True)
    venue = Column(String(200), nullable=False)
    theme_color = Column(String(20), nullable=False, default="#6366f1")
    status = Column(String(50), nullable=False, default="Planned", index=True)
    total_budget = Column(Float, nullable=False, default=0.0)
    capacity = Column(Integer, nullable=False, default=50)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships with cascade deletion
    guests = relationship(
        "Guest", back_populates="event", cascade="all, delete-orphan", passive_deletes=True
    )
    expenses = relationship(
        "Expense", back_populates="event", cascade="all, delete-orphan", passive_deletes=True
    )
    tasks = relationship(
        "Task", back_populates="event", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        Index("ix_events_category_status", "category", "status"),
        Index("ix_events_date_status", "event_date", "status"),
    )


class Guest(Base):
    """Represents an invited guest and their RSVP tracking details.

    Attributes:
        id: Primary key unique identifier.
        event_id: Foreign key referencing the parent Event.
        name: Full legal or display name of the guest.
        email: Contact email address for invitation tracking.
        phone: Optional contact phone number.
        dietary_preferences: Food restrictions (Vegan, Gluten-Free, Halal, etc.).
        rsvp_status: RSVP state (Attending, Pending, Declined).
        plus_one_count: Number of additional guests accompanying this attendee.
        notes: Special requirements or seating notes.
        created_at: UTC timestamp of creation.
        event: Parent Event relationship.
    """

    __tablename__ = "guests"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(
        Integer,
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(100), nullable=False)
    email = Column(String(120), nullable=False, index=True)
    phone = Column(String(30), nullable=True)
    dietary_preferences = Column(String(100), nullable=False, default="None")
    rsvp_status = Column(String(20), nullable=False, default="Pending", index=True)
    plus_one_count = Column(Integer, nullable=False, default=0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    event = relationship("Event", back_populates="guests")

    __table_args__ = (
        Index("ix_guests_event_rsvp", "event_id", "rsvp_status"),
    )


class Expense(Base):
    """Represents an itemized financial cost for an event.

    Attributes:
        id: Primary key unique identifier.
        event_id: Foreign key referencing the parent Event.
        item_name: Description of the expense line item.
        category: Expense classification (Catering, Venue, Decor, Entertainment, Logistics, Marketing, Other).
        estimated_cost: Projected financial expenditure.
        actual_cost: Incurred financial expenditure.
        is_paid: Payment settlement status flag.
        due_date: Payment deadline date.
        notes: Invoicing or payment vendor notes.
        created_at: UTC timestamp of creation.
        event: Parent Event relationship.
    """

    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(
        Integer,
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_name = Column(String(150), nullable=False)
    category = Column(String(50), nullable=False, index=True)
    estimated_cost = Column(Float, nullable=False, default=0.0)
    actual_cost = Column(Float, nullable=False, default=0.0)
    is_paid = Column(Boolean, nullable=False, default=False, index=True)
    due_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    event = relationship("Event", back_populates="expenses")

    __table_args__ = (
        Index("ix_expenses_event_category", "event_id", "category"),
        Index("ix_expenses_event_paid", "event_id", "is_paid"),
    )


class Task(Base):
    """Represents a scheduled milestone or checklist item for event execution.

    Attributes:
        id: Primary key unique identifier.
        event_id: Foreign key referencing the parent Event.
        title: Short title of the checklist action item.
        description: Detailed task instructions or specifications.
        priority: Urgency ranking (High, Medium, Low).
        due_date: Scheduled deadline date for completion.
        assignee: Name or role of the team member assigned.
        is_completed: Boolean flag marking task completion.
        category: Organizational grouping (e.g., Planning, Logistics, Marketing, Day-Of).
        created_at: UTC timestamp of creation.
        event: Parent Event relationship.
    """

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(
        Integer,
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(String(20), nullable=False, default="Medium", index=True)
    due_date = Column(Date, nullable=True)
    assignee = Column(String(100), nullable=True)
    is_completed = Column(Boolean, nullable=False, default=False, index=True)
    category = Column(String(50), nullable=False, default="General")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    event = relationship("Event", back_populates="tasks")

    __table_args__ = (
        Index("ix_tasks_event_completed", "event_id", "is_completed"),
        Index("ix_tasks_event_priority", "event_id", "priority"),
    )


class Vendor(Base):
    """Represents a third-party commercial partner or service provider.

    Attributes:
        id: Primary key unique identifier.
        name: Commercial business name of the vendor.
        service_type: Service category (e.g., Catering, Photography, Audio/Visual, Decor).
        contact_name: Primary point of contact representative.
        email: Professional email address for correspondence.
        phone: Telephone contact number.
        contract_status: Current procurement status (Inquiry, Quoted, Contract Signed, Paid in Full, Cancelled).
        cost_estimate: Projected or quoted cost.
        notes: Contractual terms, equipment requirements, or notes.
        created_at: UTC timestamp of creation.
    """

    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, index=True)
    service_type = Column(String(100), nullable=False, index=True)
    contact_name = Column(String(100), nullable=False)
    email = Column(String(120), nullable=False)
    phone = Column(String(30), nullable=True)
    contract_status = Column(
        String(50), nullable=False, default="Inquiry", index=True
    )
    cost_estimate = Column(Float, nullable=False, default=0.0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_vendors_service_status", "service_type", "contract_status"),
    )
