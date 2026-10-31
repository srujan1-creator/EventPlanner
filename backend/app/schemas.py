"""Pydantic v2 schemas for request validation, response serialization, and analytics.

Features field length constraints, regex validators, XSS input sanitization,
and comprehensive DTOs for FestivaFlow API endpoints.
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator
from backend.app.security import sanitize_text


class BaseSchema(BaseModel):
    """Base schema enabling ORM mode attribute mapping across all DTOs."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ============================================================================
# EVENT SCHEMAS
# ============================================================================

class EventBase(BaseSchema):
    """Core attributes for Event entities."""

    title: str = Field(..., min_length=2, max_length=150, description="Title of the event")
    description: Optional[str] = Field(None, max_length=2000, description="Detailed agenda or notes")
    category: str = Field(..., min_length=2, max_length=50, description="Event category")
    event_date: datetime = Field(..., description="Scheduled event datetime (ISO-8601)")
    venue: str = Field(..., min_length=2, max_length=200, description="Location or venue name")
    theme_color: str = Field(
        "#6366f1",
        pattern=r"^#(?:[0-9a-fA-F]{3}){1,2}$",
        description="Hex color code for event branding",
    )
    status: str = Field(
        "Planned",
        pattern=r"^(Planned|In Progress|Completed|Cancelled)$",
        description="Current state of the event",
    )
    total_budget: float = Field(0.0, ge=0.0, description="Allocated budget in USD (must be >= 0)")
    capacity: int = Field(50, ge=1, le=100000, description="Total maximum guest capacity")


class EventCreate(EventBase):
    """Payload schema for creating a new celebration event."""

    @field_validator("title", "description", "category", "venue", mode="before")
    @classmethod
    def sanitize_event_text(cls, value: Any) -> Any:
        """Sanitize text fields against XSS attacks."""
        if isinstance(value, str):
            return sanitize_text(value)
        return value


class EventUpdate(BaseSchema):
    """Payload schema for updating an existing celebration event."""

    title: Optional[str] = Field(None, min_length=2, max_length=150)
    description: Optional[str] = Field(None, max_length=2000)
    category: Optional[str] = Field(None, min_length=2, max_length=50)
    event_date: Optional[datetime] = None
    venue: Optional[str] = Field(None, min_length=2, max_length=200)
    theme_color: Optional[str] = Field(None, pattern=r"^#(?:[0-9a-fA-F]{3}){1,2}$")
    status: Optional[str] = Field(None, pattern=r"^(Planned|In Progress|Completed|Cancelled)$")
    total_budget: Optional[float] = Field(None, ge=0.0)
    capacity: Optional[int] = Field(None, ge=1, le=100000)

    @field_validator("title", "description", "category", "venue", mode="before")
    @classmethod
    def sanitize_update_text(cls, value: Any) -> Any:
        """Sanitize update string fields against XSS."""
        if isinstance(value, str):
            return sanitize_text(value)
        return value


class EventResponse(EventBase):
    """Response model for an event including system-generated timestamps."""

    id: int
    created_at: datetime
    updated_at: datetime


# ============================================================================
# GUEST SCHEMAS
# ============================================================================

class GuestBase(BaseSchema):
    """Core attributes for Guest entities."""

    name: str = Field(..., min_length=1, max_length=100, description="Guest full name")
    email: str = Field(
        ...,
        min_length=5,
        max_length=120,
        pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
        description="Guest email address",
    )
    phone: Optional[str] = Field(None, max_length=30, description="Optional contact number")
    dietary_preferences: str = Field(
        "None", max_length=100, description="Dietary restrictions or preferences"
    )
    rsvp_status: str = Field(
        "Pending",
        pattern=r"^(Attending|Pending|Declined)$",
        description="RSVP response status",
    )
    plus_one_count: int = Field(
        0, ge=0, le=10, description="Number of additional companions"
    )
    notes: Optional[str] = Field(None, max_length=500, description="Special notes or seating requests")


class GuestCreate(GuestBase):
    """Payload schema for registering a guest for an event."""

    @field_validator("name", "phone", "dietary_preferences", "notes", mode="before")
    @classmethod
    def sanitize_guest_text(cls, value: Any) -> Any:
        """Sanitize text fields against XSS."""
        if isinstance(value, str):
            return sanitize_text(value)
        return value


class GuestUpdate(BaseSchema):
    """Payload schema for modifying an existing guest record."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[str] = Field(
        None,
        min_length=5,
        max_length=120,
        pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
    )
    phone: Optional[str] = Field(None, max_length=30)
    dietary_preferences: Optional[str] = Field(None, max_length=100)
    rsvp_status: Optional[str] = Field(None, pattern=r"^(Attending|Pending|Declined)$")
    plus_one_count: Optional[int] = Field(None, ge=0, le=10)
    notes: Optional[str] = Field(None, max_length=500)

    @field_validator("name", "phone", "dietary_preferences", "notes", mode="before")
    @classmethod
    def sanitize_guest_update(cls, value: Any) -> Any:
        """Sanitize guest update text fields against XSS."""
        if isinstance(value, str):
            return sanitize_text(value)
        return value


class GuestResponse(GuestBase):
    """Response schema for a guest record."""

    id: int
    event_id: int
    created_at: datetime


# ============================================================================
# EXPENSE SCHEMAS
# ============================================================================

class ExpenseBase(BaseSchema):
    """Core attributes for Expense entities."""

    item_name: str = Field(..., min_length=1, max_length=150, description="Line item description")
    category: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Expense category (Catering, Venue, Decor, Entertainment, Logistics, Marketing, Other)",
    )
    estimated_cost: float = Field(0.0, ge=0.0, description="Projected cost in USD (must be >= 0)")
    actual_cost: float = Field(0.0, ge=0.0, description="Incurred actual cost in USD (must be >= 0)")
    is_paid: bool = Field(False, description="Settlement status")
    due_date: Optional[date] = Field(None, description="Payment deadline")
    notes: Optional[str] = Field(None, max_length=500, description="Vendor invoice or transaction notes")


class ExpenseCreate(ExpenseBase):
    """Payload schema for creating an expense item."""

    @field_validator("item_name", "category", "notes", mode="before")
    @classmethod
    def sanitize_expense_text(cls, value: Any) -> Any:
        """Sanitize expense text fields against XSS."""
        if isinstance(value, str):
            return sanitize_text(value)
        return value


class ExpenseUpdate(BaseSchema):
    """Payload schema for updating an existing expense item."""

    item_name: Optional[str] = Field(None, min_length=1, max_length=150)
    category: Optional[str] = Field(None, min_length=1, max_length=50)
    estimated_cost: Optional[float] = Field(None, ge=0.0)
    actual_cost: Optional[float] = Field(None, ge=0.0)
    is_paid: Optional[bool] = None
    due_date: Optional[date] = None
    notes: Optional[str] = Field(None, max_length=500)

    @field_validator("item_name", "category", "notes", mode="before")
    @classmethod
    def sanitize_expense_update(cls, value: Any) -> Any:
        """Sanitize expense update text against XSS."""
        if isinstance(value, str):
            return sanitize_text(value)
        return value


class ExpenseResponse(ExpenseBase):
    """Response model for an expense line item."""

    id: int
    event_id: int
    created_at: datetime


# ============================================================================
# TASK SCHEMAS
# ============================================================================

class TaskBase(BaseSchema):
    """Core attributes for Task / Milestone checklist items."""

    title: str = Field(..., min_length=1, max_length=150, description="Milestone title")
    description: Optional[str] = Field(None, max_length=1000, description="Task details")
    priority: str = Field(
        "Medium",
        pattern=r"^(High|Medium|Low)$",
        description="Priority ranking",
    )
    due_date: Optional[date] = Field(None, description="Target completion deadline")
    assignee: Optional[str] = Field(None, max_length=100, description="Assigned team member")
    is_completed: bool = Field(False, description="Completion toggle state")
    category: str = Field("General", max_length=50, description="Milestone category")


class TaskCreate(TaskBase):
    """Payload schema for creating an event checklist task."""

    @field_validator("title", "description", "assignee", "category", mode="before")
    @classmethod
    def sanitize_task_text(cls, value: Any) -> Any:
        """Sanitize task text fields against XSS."""
        if isinstance(value, str):
            return sanitize_text(value)
        return value


class TaskUpdate(BaseSchema):
    """Payload schema for updating a task checklist item."""

    title: Optional[str] = Field(None, min_length=1, max_length=150)
    description: Optional[str] = Field(None, max_length=1000)
    priority: Optional[str] = Field(None, pattern=r"^(High|Medium|Low)$")
    due_date: Optional[date] = None
    assignee: Optional[str] = Field(None, max_length=100)
    is_completed: Optional[bool] = None
    category: Optional[str] = Field(None, max_length=50)

    @field_validator("title", "description", "assignee", "category", mode="before")
    @classmethod
    def sanitize_task_update(cls, value: Any) -> Any:
        """Sanitize task update text against XSS."""
        if isinstance(value, str):
            return sanitize_text(value)
        return value


class TaskResponse(TaskBase):
    """Response model for a task checklist item."""

    id: int
    event_id: int
    created_at: datetime


# ============================================================================
# VENDOR SCHEMAS
# ============================================================================

class VendorBase(BaseSchema):
    """Core attributes for Vendor entities."""

    name: str = Field(..., min_length=1, max_length=150, description="Business name")
    service_type: str = Field(..., min_length=1, max_length=100, description="Service specialty")
    contact_name: str = Field(..., min_length=1, max_length=100, description="Primary contact name")
    email: str = Field(
        ...,
        min_length=5,
        max_length=120,
        pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
        description="Vendor email address",
    )
    phone: Optional[str] = Field(None, max_length=30, description="Vendor phone number")
    contract_status: str = Field(
        "Inquiry",
        pattern=r"^(Inquiry|Quoted|Contract Signed|Paid in Full|Cancelled)$",
        description="Procurement contract status",
    )
    cost_estimate: float = Field(0.0, ge=0.0, description="Quoted or estimated cost in USD")
    notes: Optional[str] = Field(None, max_length=500, description="Vendor details or contract terms")


class VendorCreate(VendorBase):
    """Payload schema for registering a vendor."""

    @field_validator("name", "service_type", "contact_name", "phone", "notes", mode="before")
    @classmethod
    def sanitize_vendor_text(cls, value: Any) -> Any:
        """Sanitize vendor text fields against XSS."""
        if isinstance(value, str):
            return sanitize_text(value)
        return value


class VendorUpdate(BaseSchema):
    """Payload schema for modifying a vendor profile."""

    name: Optional[str] = Field(None, min_length=1, max_length=150)
    service_type: Optional[str] = Field(None, min_length=1, max_length=100)
    contact_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[str] = Field(
        None,
        min_length=5,
        max_length=120,
        pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
    )
    phone: Optional[str] = Field(None, max_length=30)
    contract_status: Optional[str] = Field(
        None, pattern=r"^(Inquiry|Quoted|Contract Signed|Paid in Full|Cancelled)$"
    )
    cost_estimate: Optional[float] = Field(None, ge=0.0)
    notes: Optional[str] = Field(None, max_length=500)

    @field_validator("name", "service_type", "contact_name", "phone", "notes", mode="before")
    @classmethod
    def sanitize_vendor_update(cls, value: Any) -> Any:
        """Sanitize vendor update text against XSS."""
        if isinstance(value, str):
            return sanitize_text(value)
        return value


class VendorResponse(VendorBase):
    """Response model for a vendor record."""

    id: int
    created_at: datetime


# ============================================================================
# ANALYTICS & AGGREGATION SCHEMAS
# ============================================================================

class EventBudgetSummary(BaseSchema):
    """Itemized budget performance summary for a specific event."""

    total_budget: float
    total_estimated: float
    total_actual: float
    total_paid: float
    total_pending: float
    remaining_budget: float
    burn_rate_pct: float
    is_over_budget: bool


class EventRSVPSummary(BaseSchema):
    """Guest participation and capacity metrics for a specific event."""

    total_guests: int
    attending_count: int
    pending_count: int
    declined_count: int
    total_attendees: int
    capacity: int
    capacity_utilization_pct: float


class EventTaskSummary(BaseSchema):
    """Milestone execution metrics for a specific event."""

    total_tasks: int
    completed_tasks: int
    pending_tasks: int
    completion_rate_pct: float


class EventDetailResponse(BaseSchema):
    """Comprehensive composite response for an event including all child entities and aggregations."""

    event: EventResponse
    budget_summary: EventBudgetSummary
    rsvp_summary: EventRSVPSummary
    task_summary: EventTaskSummary
    guests: List[GuestResponse]
    expenses: List[ExpenseResponse]
    tasks: List[TaskResponse]


class GlobalAnalyticsResponse(BaseSchema):
    """Platform-level overview analytics computed across all managed events."""

    total_events: int
    total_guests: int
    total_attending: int
    rsvp_conversion_rate: float
    total_budget: float
    total_spent: float
    budget_utilization_pct: float
    total_tasks: int
    completed_tasks: int
    task_completion_pct: float
    category_distribution: Dict[str, int]
    rsvp_status_distribution: Dict[str, int]
    expense_category_distribution: Dict[str, float]


class MessageResponse(BaseSchema):
    """Standard generic API response message."""

    detail: str
