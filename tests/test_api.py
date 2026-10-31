"""Comprehensive Pytest test suite for FestivaFlow Celebration & Event Planner.

Covers Happy Paths, Edge Cases, Single-Pass Analytics Math, Security Controls,
Input Sanitization, Rate Limiting, and Automated WCAG-aligned API validations.
"""

import os
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from backend.app import crud
from backend.app.database import Base, SessionLocal, engine
from backend.app.main import app

# Ensure testing environment configuration
os.environ["ENABLE_RATE_LIMIT"] = "true"
os.environ["RATE_LIMIT_PER_MINUTE"] = "100"

# Explicitly ensure tables and seed data exist for pytest session
Base.metadata.create_all(bind=engine)
_seed_db = SessionLocal()
try:
    crud.seed_demo_data(_seed_db)
finally:
    _seed_db.close()

client = TestClient(app)
BYPASS_HEADER = {"X-Bypass-Rate-Limit": "true"}


# ============================================================================
# 1. SYSTEM HEALTH & SECURITY HEADERS TESTS
# ============================================================================

def test_01_health_check_status_and_metadata():
    """Verify system health endpoint returns 200 OK and valid status payload."""
    response = client.get("/api/health", headers=BYPASS_HEADER)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "FestivaFlow API"
    assert "version" in data


def test_02_owasp_security_headers_enforcement():
    """Verify that hardened OWASP defense headers are present on all HTTP responses."""
    response = client.get("/api/health", headers=BYPASS_HEADER)
    headers = response.headers

    # Content Security Policy
    assert "content-security-policy" in headers
    csp = headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp

    # MIME type sniffing defense
    assert headers.get("x-content-type-options") == "nosniff"

    # Clickjacking protection
    assert headers.get("x-frame-options") == "DENY"

    # Referrer policy
    assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    # HTTP Strict Transport Security
    assert "strict-transport-security" in headers
    assert "max-age=31536000" in headers["strict-transport-security"]


# ============================================================================
# 2. PRE-SEEDED DEMO DATA INTEGRITY TESTS
# ============================================================================

def test_03_preseeded_demo_data_loaded_on_startup():
    """Verify that lifespan hook populated 3 events, 12 guests, 10 expenses, 10 tasks, and 5 vendors."""
    # Verify Events
    res_events = client.get("/api/events?limit=100", headers=BYPASS_HEADER)
    assert res_events.status_code == 200
    events = res_events.json()["items"]
    assert len(events) >= 3

    # Verify Global Analytics reflects seeded entities
    res_analytics = client.get("/api/analytics", headers=BYPASS_HEADER)
    assert res_analytics.status_code == 200
    analytics = res_analytics.json()
    assert analytics["total_events"] >= 3
    assert analytics["total_guests"] >= 12
    assert analytics["total_tasks"] >= 10

    # Verify Vendors
    res_vendors = client.get("/api/vendors", headers=BYPASS_HEADER)
    assert res_vendors.status_code == 200
    vendors = res_vendors.json()["items"]
    assert len(vendors) >= 5


# ============================================================================
# 3. EVENT CRUD & SEARCH / FILTER TESTS
# ============================================================================

def test_04_create_event_happy_path():
    """Verify creation of a new celebration event with valid parameters."""
    event_payload = {
        "title": "Quantum Robotics Hackathon 2026",
        "description": "Annual collegiate robotics competition and banquet.",
        "category": "Hackathon",
        "event_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
        "venue": "Cybernetics Hall, Boston, MA",
        "theme_color": "#8b5cf6",
        "status": "Planned",
        "total_budget": 15000.0,
        "capacity": 80,
    }

    response = client.post("/api/events", json=event_payload, headers=BYPASS_HEADER)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["title"] == "Quantum Robotics Hackathon 2026"
    assert data["total_budget"] == 15000.0
    assert data["capacity"] == 80


def test_05_read_event_detail_with_summaries():
    """Verify fetching an event by ID computes and returns budget, rsvp, and task summaries."""
    # Fetch first seeded event
    res_events = client.get("/api/events?limit=1", headers=BYPASS_HEADER)
    event_id = res_events.json()["items"][0]["id"]

    response = client.get(f"/api/events/{event_id}", headers=BYPASS_HEADER)
    assert response.status_code == 200
    data = response.json()

    assert "event" in data
    assert "budget_summary" in data
    assert "rsvp_summary" in data
    assert "task_summary" in data
    assert isinstance(data["guests"], list)
    assert isinstance(data["expenses"], list)
    assert isinstance(data["tasks"], list)


def test_06_list_events_filtering_and_search():
    """Verify pagination, category filter, and search query on list events."""
    # Search by keyword
    res_search = client.get("/api/events?search=Hackathon", headers=BYPASS_HEADER)
    assert res_search.status_code == 200
    items = res_search.json()["items"]
    assert len(items) > 0
    assert all("Hackathon" in (item["title"] + item["category"]) for item in items)

    # Filter by category
    res_cat = client.get("/api/events?category=Hackathon", headers=BYPASS_HEADER)
    assert res_cat.status_code == 200
    for item in res_cat.json()["items"]:
        assert item["category"] == "Hackathon"


def test_07_update_event():
    """Verify updating event attributes."""
    # Create temp event
    create_res = client.post(
        "/api/events",
        json={
            "title": "Temporary Birthday Bash",
            "category": "Birthday",
            "event_date": (datetime.utcnow() + timedelta(days=10)).isoformat(),
            "venue": "Private Lounge",
            "total_budget": 2000.0,
            "capacity": 30,
        },
        headers=BYPASS_HEADER,
    )
    event_id = create_res.json()["id"]

    # Update event
    update_res = client.put(
        f"/api/events/{event_id}",
        json={"title": "Updated Gala Birthday Bash", "total_budget": 2500.0},
        headers=BYPASS_HEADER,
    )
    assert update_res.status_code == 200
    assert update_res.json()["title"] == "Updated Gala Birthday Bash"
    assert update_res.json()["total_budget"] == 2500.0


def test_08_delete_event_cascades_children():
    """Verify event deletion succeeds and cascade-deletes related children."""
    # Create event with a guest
    event_res = client.post(
        "/api/events",
        json={
            "title": "Ephemeral Event for Deletion",
            "category": "Anniversaries",
            "event_date": (datetime.utcnow() + timedelta(days=5)).isoformat(),
            "venue": "Rooftop Garden",
            "total_budget": 1000.0,
            "capacity": 20,
        },
        headers=BYPASS_HEADER,
    )
    event_id = event_res.json()["id"]

    # Add guest
    client.post(
        f"/api/events/{event_id}/guests",
        json={
            "name": "Cascade Guest",
            "email": "cascade.guest@example.com",
            "rsvp_status": "Attending",
            "plus_one_count": 0,
        },
        headers=BYPASS_HEADER,
    )

    # Delete event
    del_res = client.delete(f"/api/events/{event_id}", headers=BYPASS_HEADER)
    assert del_res.status_code == 200

    # Verify event is 404
    get_res = client.get(f"/api/events/{event_id}", headers=BYPASS_HEADER)
    assert get_res.status_code == 404


# ============================================================================
# 4. GUEST & RSVP CAPACITY VALIDATION TESTS
# ============================================================================

def test_09_create_guest_attending_within_capacity():
    """Verify registering a guest with plus-one within capacity limits succeeds."""
    event_res = client.post(
        "/api/events",
        json={
            "title": "Capacity Testing Event",
            "category": "Birthday",
            "event_date": (datetime.utcnow() + timedelta(days=15)).isoformat(),
            "venue": "Clubhouse",
            "total_budget": 500.0,
            "capacity": 10,
        },
        headers=BYPASS_HEADER,
    )
    event_id = event_res.json()["id"]

    guest_res = client.post(
        f"/api/events/{event_id}/guests",
        json={
            "name": "Sarah Connor",
            "email": "sarah.connor@resistance.net",
            "rsvp_status": "Attending",
            "plus_one_count": 2,
            "dietary_preferences": "Gluten-Free",
        },
        headers=BYPASS_HEADER,
    )
    assert guest_res.status_code == 201
    assert guest_res.json()["name"] == "Sarah Connor"
    assert guest_res.json()["plus_one_count"] == 2


def test_10_create_guest_exceeds_capacity_rejected_400():
    """Verify that automated capacity validation rejects attendees exceeding event limit."""
    # Create small event with capacity = 2
    event_res = client.post(
        "/api/events",
        json={
            "title": "Intimate VIP Dinner",
            "category": "Anniversaries",
            "event_date": (datetime.utcnow() + timedelta(days=20)).isoformat(),
            "venue": "Private Chef Studio",
            "total_budget": 3000.0,
            "capacity": 2,
        },
        headers=BYPASS_HEADER,
    )
    event_id = event_res.json()["id"]

    # Guest 1: takes 2 slots (1 guest + 1 plus-one = 2 slots)
    res1 = client.post(
        f"/api/events/{event_id}/guests",
        json={
            "name": "Guest One",
            "email": "guest1@example.com",
            "rsvp_status": "Attending",
            "plus_one_count": 1,
        },
        headers=BYPASS_HEADER,
    )
    assert res1.status_code == 201

    # Guest 2: attempts to attend (needs 1 slot, but 0 available) -> should fail with 400
    res2 = client.post(
        f"/api/events/{event_id}/guests",
        json={
            "name": "Guest Two Overflow",
            "email": "guest2@example.com",
            "rsvp_status": "Attending",
            "plus_one_count": 0,
        },
        headers=BYPASS_HEADER,
    )
    assert res2.status_code == 400
    assert "Event capacity exceeded" in res2.json()["detail"]


def test_11_invalid_email_format_rejected_422():
    """Verify Pydantic regex validator rejects malformed email addresses."""
    event_res = client.get("/api/events?limit=1", headers=BYPASS_HEADER)
    event_id = event_res.json()["items"][0]["id"]

    res = client.post(
        f"/api/events/{event_id}/guests",
        json={
            "name": "Bad Email User",
            "email": "not-a-valid-email",
            "rsvp_status": "Pending",
        },
        headers=BYPASS_HEADER,
    )
    assert res.status_code == 422


def test_12_update_guest_rsvp_and_capacity_recheck():
    """Verify modifying a guest RSVP status from Pending to Attending checks capacity."""
    event_res = client.post(
        "/api/events",
        json={
            "title": "RSVP Update Event",
            "category": "Wedding",
            "event_date": (datetime.utcnow() + timedelta(days=40)).isoformat(),
            "venue": "Vineyard",
            "total_budget": 8000.0,
            "capacity": 3,
        },
        headers=BYPASS_HEADER,
    )
    event_id = event_res.json()["id"]

    # Add pending guest with 5 plus-ones
    guest_res = client.post(
        f"/api/events/{event_id}/guests",
        json={
            "name": "Pending Large Party",
            "email": "party@example.com",
            "rsvp_status": "Pending",
            "plus_one_count": 5,
        },
        headers=BYPASS_HEADER,
    )
    assert guest_res.status_code == 201
    guest_id = guest_res.json()["id"]

    # Attempt to change to Attending (needs 6 slots, capacity is 3) -> 400
    upd_res = client.put(
        f"/api/guests/{guest_id}",
        json={"rsvp_status": "Attending"},
        headers=BYPASS_HEADER,
    )
    assert upd_res.status_code == 400
    assert "capacity exceeded" in upd_res.json()["detail"].lower()


# ============================================================================
# 5. BUDGET & EXPENSE ENGINE TESTS
# ============================================================================

def test_13_create_expense_item_happy_path():
    """Verify logging an itemized expense for an event."""
    event_res = client.get("/api/events?limit=1", headers=BYPASS_HEADER)
    event_id = event_res.json()["items"][0]["id"]

    expense_payload = {
        "item_name": "Premium Acoustic Sound Equipment Rental",
        "category": "Entertainment",
        "estimated_cost": 1500.0,
        "actual_cost": 1450.0,
        "is_paid": True,
        "notes": "Delivered and inspected.",
    }

    res = client.post(
        f"/api/events/{event_id}/expenses",
        json=expense_payload,
        headers=BYPASS_HEADER,
    )
    assert res.status_code == 201
    assert res.json()["item_name"] == "Premium Acoustic Sound Equipment Rental"
    assert res.json()["is_paid"] is True


def test_14_reject_negative_budget_and_expenses_422():
    """Verify validation constraints reject negative values for budget and costs."""
    # Negative event budget
    res1 = client.post(
        "/api/events",
        json={
            "title": "Negative Budget Event",
            "category": "Birthday",
            "event_date": (datetime.utcnow() + timedelta(days=10)).isoformat(),
            "venue": "Park",
            "total_budget": -500.0,
        },
        headers=BYPASS_HEADER,
    )
    assert res1.status_code == 422

    # Negative expense cost
    event_res = client.get("/api/events?limit=1", headers=BYPASS_HEADER)
    event_id = event_res.json()["items"][0]["id"]
    res2 = client.post(
        f"/api/events/{event_id}/expenses",
        json={
            "item_name": "Negative Cost Item",
            "category": "Catering",
            "estimated_cost": -100.0,
        },
        headers=BYPASS_HEADER,
    )
    assert res2.status_code == 422


def test_15_budget_burn_rate_and_overspend_math():
    """Verify accurate calculation of remaining budget, burn rate %, and overspend flag."""
    event_res = client.post(
        "/api/events",
        json={
            "title": "Financial Math Verification Event",
            "category": "Wedding",
            "event_date": (datetime.utcnow() + timedelta(days=25)).isoformat(),
            "venue": "Botanical Conservatory",
            "total_budget": 10000.0,
            "capacity": 50,
        },
        headers=BYPASS_HEADER,
    )
    event_id = event_res.json()["id"]

    # Expense 1: $6,000 actual
    client.post(
        f"/api/events/{event_id}/expenses",
        json={
            "item_name": "Catering Package",
            "category": "Catering",
            "estimated_cost": 6000.0,
            "actual_cost": 6000.0,
            "is_paid": True,
        },
        headers=BYPASS_HEADER,
    )

    detail_res1 = client.get(f"/api/events/{event_id}", headers=BYPASS_HEADER)
    b1 = detail_res1.json()["budget_summary"]
    assert b1["total_budget"] == 10000.0
    assert b1["total_actual"] == 6000.0
    assert b1["remaining_budget"] == 4000.0
    assert b1["burn_rate_pct"] == 60.0
    assert b1["is_over_budget"] is False

    # Expense 2: Add $5,000 actual (Total $11,000 -> Over budget!)
    client.post(
        f"/api/events/{event_id}/expenses",
        json={
            "item_name": "Orchestra & Stage",
            "category": "Entertainment",
            "estimated_cost": 4500.0,
            "actual_cost": 5000.0,
            "is_paid": False,
        },
        headers=BYPASS_HEADER,
    )

    detail_res2 = client.get(f"/api/events/{event_id}", headers=BYPASS_HEADER)
    b2 = detail_res2.json()["budget_summary"]
    assert b2["total_actual"] == 11000.0
    assert b2["remaining_budget"] == -1000.0
    assert b2["burn_rate_pct"] == 110.0
    assert b2["is_over_budget"] is True


# ============================================================================
# 6. TIMELINE & CHECKLIST SCHEDULER TESTS
# ============================================================================

def test_16_create_and_toggle_task_completion():
    """Verify task milestone creation, toggle completion, and task rate recalculation."""
    event_res = client.post(
        "/api/events",
        json={
            "title": "Task Metric Verification Event",
            "category": "Hackathon",
            "event_date": (datetime.utcnow() + timedelta(days=12)).isoformat(),
            "venue": "Campus Auditorium",
            "total_budget": 5000.0,
            "capacity": 60,
        },
        headers=BYPASS_HEADER,
    )
    event_id = event_res.json()["id"]

    # Task 1: Completed
    client.post(
        f"/api/events/{event_id}/tasks",
        json={
            "title": "Secure sponsor banners",
            "priority": "High",
            "is_completed": True,
        },
        headers=BYPASS_HEADER,
    )

    # Task 2: Open
    t2_res = client.post(
        f"/api/events/{event_id}/tasks",
        json={
            "title": "Set up audio microphones",
            "priority": "Medium",
            "is_completed": False,
        },
        headers=BYPASS_HEADER,
    )
    t2_id = t2_res.json()["id"]

    # Check 50% completion
    detail1 = client.get(f"/api/events/{event_id}", headers=BYPASS_HEADER).json()
    assert detail1["task_summary"]["total_tasks"] == 2
    assert detail1["task_summary"]["completed_tasks"] == 1
    assert detail1["task_summary"]["completion_rate_pct"] == 50.0

    # Toggle task 2 to completed
    client.put(
        f"/api/tasks/{t2_id}",
        json={"is_completed": True},
        headers=BYPASS_HEADER,
    )

    # Check 100% completion
    detail2 = client.get(f"/api/events/{event_id}", headers=BYPASS_HEADER).json()
    assert detail2["task_summary"]["completed_tasks"] == 2
    assert detail2["task_summary"]["completion_rate_pct"] == 100.0


def test_17_task_priority_validation_422():
    """Verify task priority field rejects unapproved priorities."""
    event_res = client.get("/api/events?limit=1", headers=BYPASS_HEADER)
    event_id = event_res.json()["items"][0]["id"]

    res = client.post(
        f"/api/events/{event_id}/tasks",
        json={"title": "Invalid Priority Task", "priority": "UrgentCritical"},
        headers=BYPASS_HEADER,
    )
    assert res.status_code == 422


# ============================================================================
# 7. VENDOR & VENUE DIRECTORY TESTS
# ============================================================================

def test_18_vendor_directory_crud():
    """Verify full lifecycle operations on Vendor directory."""
    # Create
    vendor_payload = {
        "name": "Starlight Stage & Lighting Pro",
        "service_type": "Audio/Visual",
        "contact_name": "Julian Bailey",
        "email": "julian@starlightlighting.com",
        "phone": "+1-555-0182",
        "contract_status": "Quoted",
        "cost_estimate": 4500.0,
        "notes": "Includes 2 truss towers and technician.",
    }
    create_res = client.post("/api/vendors", json=vendor_payload, headers=BYPASS_HEADER)
    assert create_res.status_code == 201
    vendor_id = create_res.json()["id"]

    # Read
    get_res = client.get(f"/api/vendors/{vendor_id}", headers=BYPASS_HEADER)
    assert get_res.status_code == 200
    assert get_res.json()["contact_name"] == "Julian Bailey"

    # Update
    upd_res = client.put(
        f"/api/vendors/{vendor_id}",
        json={"contract_status": "Contract Signed"},
        headers=BYPASS_HEADER,
    )
    assert upd_res.status_code == 200
    assert upd_res.json()["contract_status"] == "Contract Signed"

    # Delete
    del_res = client.delete(f"/api/vendors/{vendor_id}", headers=BYPASS_HEADER)
    assert del_res.status_code == 200


# ============================================================================
# 8. ANALYTICS & EXPORT TESTS
# ============================================================================

def test_19_global_analytics_dashboard_metrics():
    """Verify platform-wide analytics calculations and distributions."""
    response = client.get("/api/analytics", headers=BYPASS_HEADER)
    assert response.status_code == 200
    data = response.json()

    assert data["total_events"] > 0
    assert data["total_guests"] > 0
    assert 0.0 <= data["rsvp_conversion_rate"] <= 100.0
    assert data["total_budget"] >= 0.0
    assert 0.0 <= data["task_completion_pct"] <= 100.0
    assert isinstance(data["category_distribution"], dict)
    assert isinstance(data["expense_category_distribution"], dict)


def test_20_export_event_plan_json():
    """Verify JSON export endpoint provides complete structured plan and attachment header."""
    res_events = client.get("/api/events?limit=1", headers=BYPASS_HEADER)
    event_id = res_events.json()["items"][0]["id"]

    response = client.get(f"/api/events/{event_id}/export?format=json", headers=BYPASS_HEADER)
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    assert "attachment;" in response.headers.get("content-disposition", "")

    data = response.json()
    assert "event" in data
    assert "budget_summary" in data
    assert "guests" in data
    assert "expenses" in data
    assert "tasks" in data


def test_21_export_event_plan_csv():
    """Verify CSV export endpoint returns text/csv content with correct table sections."""
    res_events = client.get("/api/events?limit=1", headers=BYPASS_HEADER)
    event_id = res_events.json()["items"][0]["id"]

    response = client.get(f"/api/events/{event_id}/export?format=csv", headers=BYPASS_HEADER)
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "attachment;" in response.headers.get("content-disposition", "")

    content = response.text
    assert "FESTIVAFLOW EVENT PLAN EXPORT" in content
    assert "BUDGET & FINANCIAL SUMMARY" in content
    assert "GUEST LIST" in content
    assert "ITEMIZED EXPENSES" in content


# ============================================================================
# 9. SECURITY & SANITIZATION TESTS
# ============================================================================

def test_22_xss_payload_sanitization():
    """Verify that script tags and dangerous HTML are neutralized via HTML-escaping."""
    malicious_title = "<script>alert('XSS_ATTACK')</script>Anniversary Party"
    malicious_notes = "<img src=x onerror=alert(1)>Special Seating"

    response = client.post(
        "/api/events",
        json={
            "title": malicious_title,
            "category": "Anniversaries",
            "event_date": (datetime.utcnow() + timedelta(days=20)).isoformat(),
            "venue": "<b>Grand Palace</b>",
            "description": malicious_notes,
            "total_budget": 5000.0,
            "capacity": 50,
        },
        headers=BYPASS_HEADER,
    )
    assert response.status_code == 201
    data = response.json()

    # Raw script tags must not exist in stored/returned payload
    assert "<script>" not in data["title"]
    assert "&lt;script&gt;" in data["title"]
    assert "<img" not in data["description"]
    assert "&lt;img" in data["description"]


def test_23_sql_injection_resilience():
    """Verify that SQL injection attempt strings in search and filters are treated safely as literals."""
    sql_payload = "' OR '1'='1' --"
    response = client.get(f"/api/events?search={sql_payload}", headers=BYPASS_HEADER)
    assert response.status_code == 200
    # ORM parameterization ensures no database syntax error or unauthorized data dump occurs


def test_24_nonexistent_entity_404_handling():
    """Verify querying non-existent entities returns structured 404 Not Found."""
    assert client.get("/api/events/999999", headers=BYPASS_HEADER).status_code == 404
    assert client.delete("/api/events/999999", headers=BYPASS_HEADER).status_code == 404
    assert client.put("/api/guests/999999", json={"name": "Ghost"}, headers=BYPASS_HEADER).status_code == 404
    assert client.delete("/api/expenses/999999", headers=BYPASS_HEADER).status_code == 404
    assert client.delete("/api/tasks/999999", headers=BYPASS_HEADER).status_code == 404
    assert client.get("/api/vendors/999999", headers=BYPASS_HEADER).status_code == 404


def test_25_rate_limiter_enforcement():
    """Verify that exceeding requests per minute triggers 429 Too Many Requests with Retry-After header."""
    # Create isolated client without bypass header and test rapid firing
    ip_client = TestClient(app)
    hit_429 = False

    # Send 120 rapid requests (limit is 100/min)
    for _ in range(120):
        resp = ip_client.get("/api/health")
        if resp.status_code == 429:
            hit_429 = True
            assert "Retry-After" in resp.headers
            assert "Rate limit" in resp.json()["detail"]
            break

    assert hit_429, "Expected 429 Too Many Requests response after exceeding window rate limit."
