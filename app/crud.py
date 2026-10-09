from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models import (
    ServiceRequest, User, Category, SLAConfig, RequestComment, RequestHistory,
    StatusEnum, PriorityEnum, RoleEnum
)
from app.schemas import ServiceRequestCreate, ServiceRequestAssign, ServiceRequestStatusUpdate, CommentCreate


# --- SLA Helper Functions ---
def compute_sla_due_date(db: Session, priority: PriorityEnum, start_time: datetime) -> datetime:
    config = db.query(SLAConfig).filter(SLAConfig.priority == priority).first()
    hours = config.resolution_hours if config else 24
    return start_time + timedelta(hours=hours)


def calculate_sla_status(req: ServiceRequest) -> str:
    now = datetime.utcnow()
    
    # If ticket was resolved
    if req.resolved_at and req.sla_due_at:
        if req.resolved_at <= req.sla_due_at:
            return "Resolved Within SLA"
        return "Resolved SLA Breached"

    # For open tickets
    if req.sla_due_at:
        if now > req.sla_due_at:
            return "SLA Breached"
        elif req.sla_due_at - now <= timedelta(hours=2):
            return "Approaching SLA Breach"
        return "Within SLA"
    
    return "No SLA Configured"


def enrich_request(req: ServiceRequest) -> ServiceRequest:
    """Dynamically attaches the calculated SLA status string to the response object."""
    req.sla_status = calculate_sla_status(req)
    return req


# --- Service Request CRUD ---
def create_service_request(db: Session, req_in: ServiceRequestCreate) -> ServiceRequest:
    # Validate requester exists
    requester = db.query(User).filter(User.id == req_in.requester_id).first()
    if not requester:
        raise HTTPException(status_code=400, detail="Requester not found.")

    # Validate category exists
    category = db.query(Category).filter(Category.id == req_in.category_id).first()
    if not category:
        raise HTTPException(status_code=400, detail="Category not found.")

    now = datetime.utcnow()
    sla_due = compute_sla_due_date(db, req_in.priority, now)

    new_request = ServiceRequest(
        subject=req_in.subject,
        description=req_in.description,
        priority=req_in.priority,
        status=StatusEnum.NEW,
        category_id=req_in.category_id,
        requester_id=req_in.requester_id,
        created_at=now,
        updated_at=now,
        sla_due_at=sla_due
    )
    db.add(new_request)
    db.commit()
    db.refresh(new_request)

    # Log initial creation history
    history = RequestHistory(
        request_id=new_request.id,
        actor_id=req_in.requester_id,
        action_type="CREATED",
        new_value=StatusEnum.NEW.value
    )
    db.add(history)
    db.commit()

    return enrich_request(new_request)


def get_requests(
    db: Session,
    status_filter: Optional[StatusEnum] = None,
    priority_filter: Optional[PriorityEnum] = None,
    assignee_id: Optional[int] = None
) -> List[ServiceRequest]:
    query = db.query(ServiceRequest)
    if status_filter:
        query = query.filter(ServiceRequest.status == status_filter)
    if priority_filter:
        query = query.filter(ServiceRequest.priority == priority_filter)
    if assignee_id is not None:
        query = query.filter(ServiceRequest.assignee_id == assignee_id)
    
    requests = query.order_by(ServiceRequest.created_at.desc()).all()
    return [enrich_request(r) for r in requests]


def get_request_by_id(db: Session, req_id: int) -> ServiceRequest:
    req = db.query(ServiceRequest).filter(ServiceRequest.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Service request not found.")
    return enrich_request(req)


# --- Workflow Operations ---
VALID_TRANSITIONS = {
    StatusEnum.NEW: [StatusEnum.ASSIGNED, StatusEnum.IN_PROGRESS],
    StatusEnum.ASSIGNED: [StatusEnum.IN_PROGRESS, StatusEnum.ON_HOLD],
    StatusEnum.IN_PROGRESS: [StatusEnum.ON_HOLD, StatusEnum.RESOLVED],
    StatusEnum.ON_HOLD: [StatusEnum.IN_PROGRESS, StatusEnum.RESOLVED],
    StatusEnum.RESOLVED: [StatusEnum.CLOSED, StatusEnum.IN_PROGRESS],  # In Progress if reopened
    StatusEnum.CLOSED: []  # Closed is terminal
}

def assign_request(db: Session, req_id: int, assign_in: ServiceRequestAssign) -> ServiceRequest:
    req = get_request_by_id(db, req_id)
    if req.status == StatusEnum.CLOSED:
        raise HTTPException(status_code=400, detail="Cannot assign a closed request.")

    # Validate assignee is an IT Agent or Manager
    assignee = db.query(User).filter(User.id == assign_in.assignee_id).first()
    if not assignee or assignee.role not in [RoleEnum.IT_AGENT, RoleEnum.MANAGER]:
        raise HTTPException(status_code=400, detail="Assignee must be an active IT Agent or Manager.")

    old_assignee_name = req.assignee.name if req.assignee else "Unassigned"
    req.assignee_id = assignee.id

    # Auto transition New -> Assigned if not already further along
    old_status = req.status
    if req.status == StatusEnum.NEW:
        req.status = StatusEnum.ASSIGNED

    req.updated_at = datetime.utcnow()

    # Log history
    history_assign = RequestHistory(
        request_id=req.id,
        actor_id=assign_in.actor_id,
        action_type="ASSIGNMENT",
        old_value=old_assignee_name,
        new_value=assignee.name
    )
    db.add(history_assign)

    if old_status != req.status:
        history_status = RequestHistory(
            request_id=req.id,
            actor_id=assign_in.actor_id,
            action_type="STATUS_CHANGE",
            old_value=old_status.value,
            new_value=req.status.value
        )
        db.add(history_status)

    db.commit()
    db.refresh(req)
    return enrich_request(req)


def update_status(db: Session, req_id: int, update_in: ServiceRequestStatusUpdate) -> ServiceRequest:
    req = get_request_by_id(db, req_id)
    current_status = req.status
    target_status = update_in.new_status

    if current_status == StatusEnum.CLOSED:
        raise HTTPException(status_code=400, detail="A closed request cannot be modified.")

    # Validate transition
    allowed = VALID_TRANSITIONS.get(current_status, [])
    if target_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition: Cannot move directly from '{current_status.value}' to '{target_status.value}'."
        )

    # Validate resolution details if transitioning to Resolved
    if target_status == StatusEnum.RESOLVED:
        if not update_in.resolution_details or not update_in.resolution_details.strip():
            raise HTTPException(
                status_code=400,
                detail="Resolution details are mandatory before marking a request as Resolved."
            )
        req.resolution_details = update_in.resolution_details.strip()
        req.resolved_at = datetime.utcnow()

    # If transitioning to Closed, ensure it was resolved
    if target_status == StatusEnum.CLOSED:
        if current_status != StatusEnum.RESOLVED:
            raise HTTPException(status_code=400, detail="Only resolved requests can be closed.")
        req.closed_at = datetime.utcnow()

    req.status = target_status
    req.updated_at = datetime.utcnow()

    # Log history
    history = RequestHistory(
        request_id=req.id,
        actor_id=update_in.actor_id,
        action_type="STATUS_CHANGE",
        old_value=current_status.value,
        new_value=target_status.value
    )
    db.add(history)
    db.commit()
    db.refresh(req)
    return enrich_request(req)


# --- Comments CRUD ---
def add_comment(db: Session, req_id: int, comment_in: CommentCreate) -> RequestComment:
    req = get_request_by_id(db, req_id)
    if req.status == StatusEnum.CLOSED:
        raise HTTPException(status_code=400, detail="Cannot add comments to a closed request.")

    new_comment = RequestComment(
        request_id=req_id,
        author_id=comment_in.author_id,
        comment=comment_in.comment,
        created_at=datetime.utcnow()
    )
    db.add(new_comment)

    history = RequestHistory(
        request_id=req.id,
        actor_id=comment_in.author_id,
        action_type="COMMENT_ADDED",
        new_value=comment_in.comment[:50] + ("..." if len(comment_in.comment) > 50 else "")
    )
    db.add(history)
    db.commit()
    db.refresh(new_comment)
    return new_comment


def get_comments(db: Session, req_id: int) -> List[RequestComment]:
    return db.query(RequestComment).filter(RequestComment.request_id == req_id).order_by(RequestComment.created_at.asc()).all()


def get_history(db: Session, req_id: int) -> List[RequestHistory]:
    return db.query(RequestHistory).filter(RequestHistory.request_id == req_id).order_by(RequestHistory.timestamp.asc()).all()


# --- Reporting & Dashboard Metrics ---
def get_dashboard_metrics(db: Session) -> Dict[str, Any]:
    all_requests = db.query(ServiceRequest).all()
    enriched = [enrich_request(r) for r in all_requests]

    total_requests = len(enriched)
    open_requests = [r for r in enriched if r.status not in [StatusEnum.RESOLVED, StatusEnum.CLOSED]]
    unassigned_requests = [r for r in open_requests if r.assignee_id is None]
    sla_breached = [r for r in enriched if r.sla_status in ["SLA Breached", "Resolved SLA Breached"]]
    
    # Group by Priority
    by_priority = {}
    for p in PriorityEnum:
        by_priority[p.value] = len([r for r in enriched if r.priority == p])

    # Group by Status
    by_status = {}
    for s in StatusEnum:
        by_status[s.value] = len([r for r in enriched if r.status == s])

    # Group by Category
    categories = db.query(Category).all()
    by_category = {c.name: len([r for r in enriched if r.category_id == c.id]) for c in categories}

    return {
        "total_requests": total_requests,
        "total_open_requests": len(open_requests),
        "total_unassigned_requests": len(unassigned_requests),
        "total_sla_breached": len(sla_breached),
        "by_priority": by_priority,
        "by_status": by_status,
        "by_category": by_category
    }