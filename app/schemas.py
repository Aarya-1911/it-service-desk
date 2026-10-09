from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
from app.models import RoleEnum, PriorityEnum, StatusEnum


# --- User Schemas ---
class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: RoleEnum

    class Config:
        from_attributes = True


# --- Category Schemas ---
class CategoryOut(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


# --- History & Comment Schemas ---
class RequestHistoryOut(BaseModel):
    id: int
    action_type: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    timestamp: datetime
    actor_id: Optional[int] = None

    class Config:
        from_attributes = True


class CommentCreate(BaseModel):
    author_id: int
    comment: str = Field(..., min_length=1, description="Comment text cannot be empty")


class CommentOut(BaseModel):
    id: int
    author_id: int
    comment: str
    created_at: datetime
    author: Optional[UserOut] = None

    class Config:
        from_attributes = True


# --- Service Request Schemas ---
class ServiceRequestCreate(BaseModel):
    requester_id: int
    subject: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=5)
    category_id: int
    priority: PriorityEnum = PriorityEnum.MEDIUM


class ServiceRequestAssign(BaseModel):
    assignee_id: int
    actor_id: int


class ServiceRequestStatusUpdate(BaseModel):
    new_status: StatusEnum
    actor_id: int
    resolution_details: Optional[str] = None
    reason: Optional[str] = None


class ServiceRequestOut(BaseModel):
    id: int
    subject: str
    description: str
    priority: PriorityEnum
    status: StatusEnum
    category_id: int
    requester_id: int
    assignee_id: Optional[int] = None
    resolution_details: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    sla_due_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    
    # SLA status dynamically populated
    sla_status: Optional[str] = None

    category: Optional[CategoryOut] = None
    requester: Optional[UserOut] = None
    assignee: Optional[UserOut] = None

    class Config:
        from_attributes = True