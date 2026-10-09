import os
from typing import List, Optional
from fastapi import FastAPI, Depends, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.database import get_db, engine, Base
from app.models import StatusEnum, PriorityEnum, User, Category
from app.schemas import (
    ServiceRequestCreate,
    ServiceRequestOut,
    ServiceRequestAssign,
    ServiceRequestStatusUpdate,
    CommentCreate,
    CommentOut,
    RequestHistoryOut,
    UserOut,
    CategoryOut,
)
from app import crud

# 1. Initialize Database Tables
Base.metadata.create_all(bind=engine)

# 2. Initialize FastAPI Application
app = FastAPI(
    title="IT Service Request Management System",
    description="REST API for managing IT Service Requests, SLAs, Assignments, and Lifecycles.",
    version="1.0.0",
)

# 3. Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Mount Static Directory
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


# ==============================================================================
# 5. FRONTEND PAGE ROUTES
# ==============================================================================

@app.get("/", include_in_schema=False)
def root_redirect():
    """Redirect base URL to the Login Portal."""
    return RedirectResponse(url="/login")


@app.get("/login", include_in_schema=False)
def get_login_page():
    """Serves the Unified Role-Based Login Screen."""
    return FileResponse("static/login.html")


@app.get("/employee", include_in_schema=False)
def get_employee_portal():
    """Serves the Employee Self-Service Portal."""
    return FileResponse("static/employee.html")


@app.get("/agent", include_in_schema=False)
def get_agent_workspace():
    """Serves the IT Staff Workspace."""
    return FileResponse("static/agent.html")


# ==============================================================================
# 6. METADATA ENDPOINTS
# ==============================================================================

@app.get("/users", response_model=List[UserOut], tags=["Users"])
def get_users(db: Session = Depends(get_db)):
    return db.query(User).all()


@app.get("/categories", response_model=List[CategoryOut], tags=["Categories"])
def get_categories(db: Session = Depends(get_db)):
    return db.query(Category).all()


# ==============================================================================
# 7. SERVICE REQUEST ENDPOINTS
# ==============================================================================

@app.post("/requests", response_model=ServiceRequestOut, status_code=status.HTTP_201_CREATED, tags=["Requests"])
def create_request(req_in: ServiceRequestCreate, db: Session = Depends(get_db)):
    """Create a new service request. Auto-calculates SLA due date based on priority."""
    return crud.create_service_request(db, req_in)


@app.get("/requests", response_model=List[ServiceRequestOut], tags=["Requests"])
def list_requests(
    status_filter: Optional[StatusEnum] = Query(None, alias="status"),
    priority_filter: Optional[PriorityEnum] = Query(None, alias="priority"),
    assignee_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Retrieve service requests with optional filters for status, priority, and assignee."""
    return crud.get_requests(db, status_filter, priority_filter, assignee_id)


@app.get("/requests/{req_id}", response_model=ServiceRequestOut, tags=["Requests"])
def get_request(req_id: int, db: Session = Depends(get_db)):
    """Get complete details of a specific service request including SLA status."""
    return crud.get_request_by_id(db, req_id)


# ==============================================================================
# 8. LIFECYCLE & WORKFLOW
# ==============================================================================

@app.post("/requests/{req_id}/assign", response_model=ServiceRequestOut, tags=["Workflow"])
def assign_request(req_id: int, assign_in: ServiceRequestAssign, db: Session = Depends(get_db)):
    """Assign or reassign an IT ticket to an IT Agent or Manager."""
    return crud.assign_request(db, req_id, assign_in)


@app.post("/requests/{req_id}/status", response_model=ServiceRequestOut, tags=["Workflow"])
def update_status(req_id: int, update_in: ServiceRequestStatusUpdate, db: Session = Depends(get_db)):
    """
    Transition request lifecycle status.
    Requires resolution details if transitioning to 'Resolved'.
    Prevents invalid transitions or updating closed requests.
    """
    return crud.update_status(db, req_id, update_in)


# ==============================================================================
# 9. COMMENTS & AUDIT HISTORY
# ==============================================================================

@app.post("/requests/{req_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED, tags=["Collaboration"])
def add_comment(req_id: int, comment_in: CommentCreate, db: Session = Depends(get_db)):
    """Add a communication update/comment to a request."""
    return crud.add_comment(db, req_id, comment_in)


@app.get("/requests/{req_id}/comments", response_model=List[CommentOut], tags=["Collaboration"])
def get_comments(req_id: int, db: Session = Depends(get_db)):
    """Get all comments for a request."""
    return crud.get_comments(db, req_id)


@app.get("/requests/{req_id}/history", response_model=List[RequestHistoryOut], tags=["Audit History"])
def get_history(req_id: int, db: Session = Depends(get_db)):
    """Get the full audit history trail of status and assignment changes."""
    return crud.get_history(db, req_id)


# ==============================================================================
# 10. REPORTS & DASHBOARD
# ==============================================================================

@app.get("/reports/dashboard", tags=["Reports"])
def dashboard_metrics(db: Session = Depends(get_db)):
    """Management dashboard report: ticket counts, priority, category, SLA breaches."""
    return crud.get_dashboard_metrics(db)