# IT Service Request Management System

A centralized IT Service Request Management System built with Python, FastAPI, and SQLAlchemy. It streamlines ticket creation, enforces strict status lifecycles, automates SLA tracking with breach warnings, logs full audit trails, and provides real-time workload analytics for management.

---

## 1. Technology Stack

- **Backend:** Python 3.10+, FastAPI (Asynchronous REST API, Pydantic validation)
- **Database / ORM:** SQLite for rapid local testing (fully compatible with MariaDB / MySQL via SQLAlchemy ORM)
- **Frontend:** Single-page dashboard built with HTML5, TailwindCSS, and Fetch API (zero build setup)
- **API Documentation:** Interactive OpenAPI 3.0 / Swagger UI generated at `/docs`

---


## 2. System Architecture & Database Design

### Core Entities & Relational Schema
- **users:** Manages employees and IT staff with role-based segregation (Requester, IT_Agent, Manager).
- **categories:** Manageable lookup table for classification (Hardware, Software, Network, Access / Permission, Email, Other).
- **sla_configs:** Configurable resolution time limits mapped to priorities without hardcoding.
- **service_requests:** Central ticket table with timestamps, foreign keys to requester/assignee/category, resolution notes, and SLA deadlines.
- **request_comments:** Team communication thread with author and timestamp tracking.
- **request_history:** Immutable audit log capturing action type (STATUS_CHANGE, ASSIGNMENT), previous value, updated value, actor, and timestamp.

---

## 3. Business Rules & SLA Interpretation

### Status Lifecycle State Machine
- **Lifecycle Flow:** New -> Assigned -> In Progress <-> On Hold -> Resolved -> Closed
- **Assignment Guard:** Only active IT_Agent or Manager users can be assigned. Reassignment is tracked in history.
- **Resolution Guard:** Transition to Resolved strictly mandates non-empty resolution_details.
- **Terminal State:** Closed tickets are immutable; further status updates or assignments are rejected with HTTP 400.

### SLA Calculation Engine
- **Critical:** 4 Hours resolution target.
- **High:** 8 Hours resolution target.
- **Medium:** 24 Hours resolution target.
- **Low:** 48 Hours resolution target.
- **Clock Initiation:** The SLA clock starts immediately at created_at.
- **Dynamic Breach Detection:** Evaluated at request time where SLA is breached if current time exceeds sla_due_at and status is not Resolved or Closed.
- **Breach Warning:** Approaching breach warning triggers when remaining time is less than or equal to 2 hours.
- **Resolution Verification:** For resolved/closed tickets, breach is evaluated against resolved_at being less than or equal to sla_due_at.

---

## 4. Setup Instructions

- **Step 1 - Environment Setup:** Clone the repository and create a virtual environment using `python -m venv venv`, then activate it via `.\venv\Scripts\Activate.ps1` (Windows) or `source venv/bin/activate` (Mac/Linux).
- **Step 2 - Install Dependencies:** Run `pip install -r requirements.txt` to install FastAPI, Uvicorn, and SQLAlchemy.
- **Step 3 - Initialize Database:** Run `python -m app.seed` to create the SQLite tables and insert default users, categories, and SLA thresholds.
- **Step 4 - Run Application:** Launch the backend server with `uvicorn app.main:app --reload`.
- **Step 5 - Access Application:** Open the web portal at `http://127.0.0.1:8000` or the interactive Swagger API documentation at `http://127.0.0.1:8000/docs`.

## 5. Automated Testing

Run the included verification suite covering both positive flows and negative security/validation checks:

python test_suite.py

### Test Coverage Highlights
- **Positive Testing:** Ticket creation, priority-to-SLA computation, valid agent assignment, and full lifecycle progression through resolution and closure.
- **Negative Testing:** Blocks assigning tickets to non-IT staff, blocks skipping directly from New to Closed, blocks resolution without details, and rejects any modification on closed tickets.
- **Audit Logging Verification:** Confirms all actor actions, status changes, and reassignments are recorded in the history trail.


## 6. Known Limitations & Future Improvements
- **Business Hours SLA:** Current implementation runs on absolute elapsed hours. Future iterations can add holiday and business-hour calendars (skipping weekends).
- **Authentication:** Currently utilizes role and actor identity parameters; production readiness would incorporate OAuth2/JWT session tokens.