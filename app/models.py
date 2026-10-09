import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from app.database import Base


class RoleEnum(str, enum.Enum):
    REQUESTER = "Requester"
    IT_AGENT = "IT_Agent"
    MANAGER = "Manager"


class PriorityEnum(str, enum.Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class StatusEnum(str, enum.Enum):
    NEW = "New"
    ASSIGNED = "Assigned"
    IN_PROGRESS = "In Progress"
    ON_HOLD = "On Hold"
    RESOLVED = "Resolved"
    CLOSED = "Closed"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    role = Column(SQLEnum(RoleEnum), default=RoleEnum.REQUESTER, nullable=False)

    created_requests = relationship("ServiceRequest", back_populates="requester", foreign_keys="ServiceRequest.requester_id")
    assigned_requests = relationship("ServiceRequest", back_populates="assignee", foreign_keys="ServiceRequest.assignee_id")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)


class SLAConfig(Base):
    __tablename__ = "sla_configs"

    id = Column(Integer, primary_key=True, index=True)
    priority = Column(SQLEnum(PriorityEnum), unique=True, nullable=False)
    resolution_hours = Column(Integer, nullable=False)


class ServiceRequest(Base):
    __tablename__ = "service_requests"

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)

    priority = Column(SQLEnum(PriorityEnum), nullable=False, default=PriorityEnum.MEDIUM)
    status = Column(SQLEnum(StatusEnum), nullable=False, default=StatusEnum.NEW)

    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assignee_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    resolution_details = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    sla_due_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    category = relationship("Category")
    requester = relationship("User", foreign_keys=[requester_id], back_populates="created_requests")
    assignee = relationship("User", foreign_keys=[assignee_id], back_populates="assigned_requests")
    comments = relationship("RequestComment", back_populates="request", cascade="all, delete-orphan")
    history = relationship("RequestHistory", back_populates="request", cascade="all, delete-orphan")


class RequestComment(Base):
    __tablename__ = "request_comments"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("service_requests.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    comment = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    request = relationship("ServiceRequest", back_populates="comments")
    author = relationship("User")


class RequestHistory(Base):
    __tablename__ = "request_history"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("service_requests.id"), nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action_type = Column(String(50), nullable=False)
    old_value = Column(String(255), nullable=True)
    new_value = Column(String(255), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    request = relationship("ServiceRequest", back_populates="history")
    actor = relationship("User")