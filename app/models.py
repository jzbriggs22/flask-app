"""SQLAlchemy ORM models for the task registry domain."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    event,
)
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from .database import Base

TASK_STATUSES = ("pending", "in_progress", "complete", "blocked")


def default_api_key_scopes() -> list[str]:
    """Return default scopes granted to a new API key."""

    return ["read", "write", "monitor"]


class ApiKey(Base):
    """API keys secure the service for authenticated callers."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    owner_email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    scopes: Mapped[list[str]] = mapped_column(
        SQLiteJSON().with_variant(JSON, "postgresql"),
        default=default_api_key_scopes,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    last_rotated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    request_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def scope_contains(self, value: str) -> bool:
        return value in (self.scopes or [])

    def scope_allows(self, required: Sequence[str]) -> bool:
        scopes = set(self.scopes or [])
        return any(scope in scopes for scope in required)

    @property
    def is_expired(self) -> bool:
        return bool(self.expires_at and self.expires_at < datetime.utcnow())


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="owner", cascade="all")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    project: Mapped[str | None] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(
        Enum(*TASK_STATUSES, name="task_status"), default="pending", nullable=False
    )
    context: Mapped[dict[str, Any]] = mapped_column(
        SQLiteJSON().with_variant(JSON, "postgresql"), default=dict, nullable=False
    )
    outputs: Mapped[dict[str, Any]] = mapped_column(
        SQLiteJSON().with_variant(JSON, "postgresql"), default=dict, nullable=False
    )
    dependencies: Mapped[list[str]] = mapped_column(
        SQLiteJSON().with_variant(JSON, "postgresql"), default=list, nullable=False
    )
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    owner: Mapped[User | None] = relationship("User", back_populates="tasks")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


@event.listens_for(Task, "before_insert")
@event.listens_for(Task, "before_update")
def normalize_dependencies(_, __, target: Task) -> None:
    """Ensure dependency lists remain unique and sorted."""

    if isinstance(target.dependencies, list):
        target.dependencies = sorted({dep for dep in target.dependencies if dep})


class MemoryNode(Base):
    """Nodes store durable memory artifacts that tasks and agents can reference."""

    __tablename__ = "memory_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    node_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(500))
    data: Mapped[dict[str, Any]] = mapped_column(
        SQLiteJSON().with_variant(JSON, "postgresql"), default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    originating_task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), index=True
    )
    originating_task: Mapped[Task | None] = relationship("Task", backref="authored_nodes")

    @property
    def originating_task_ref(self) -> str | None:
        return self.originating_task.task_id if self.originating_task else None


class MemoryEdge(Base):
    """Edges connect nodes and tasks into a neural-like web of references."""

    __tablename__ = "memory_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    edge_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    relation: Mapped[str] = mapped_column(String(80), nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    source_node_id: Mapped[int | None] = mapped_column(
        ForeignKey("memory_nodes.id", ondelete="CASCADE"), index=True
    )
    target_node_id: Mapped[int | None] = mapped_column(
        ForeignKey("memory_nodes.id", ondelete="CASCADE"), index=True
    )
    source_task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    target_task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    source_node: Mapped[MemoryNode | None] = relationship(
        "MemoryNode", foreign_keys=[source_node_id], backref="outgoing_edges"
    )
    target_node: Mapped[MemoryNode | None] = relationship(
        "MemoryNode", foreign_keys=[target_node_id], backref="incoming_edges"
    )
    source_task: Mapped[Task | None] = relationship(
        "Task", foreign_keys=[source_task_id], backref="outgoing_edges"
    )
    target_task: Mapped[Task | None] = relationship(
        "Task", foreign_keys=[target_task_id], backref="incoming_edges"
    )

    @property
    def source_node_ref(self) -> str | None:
        return self.source_node.node_id if self.source_node else None

    @property
    def target_node_ref(self) -> str | None:
        return self.target_node.node_id if self.target_node else None

    @property
    def source_task_ref(self) -> str | None:
        return self.source_task.task_id if self.source_task else None

    @property
    def target_task_ref(self) -> str | None:
        return self.target_task.task_id if self.target_task else None


class ApiKeyArchive(Base):
    """Historical record for API keys that have been rotated or expired."""

    __tablename__ = "api_key_archives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    api_key_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    owner_email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    scopes: Mapped[list[str]] = mapped_column(
        SQLiteJSON().with_variant(JSON, "postgresql"), default=list, nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    archive_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_error_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    request_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class MemoryTrace(Base):
    """Immutable timeline entries for agent memory usage."""

    __tablename__ = "memory_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        SQLiteJSON().with_variant(JSON, "postgresql"), default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"), index=True)
    node_id: Mapped[int | None] = mapped_column(
        ForeignKey("memory_nodes.id", ondelete="SET NULL"), index=True
    )

    task: Mapped[Task | None] = relationship("Task", backref="memory_traces")
    node: Mapped[MemoryNode | None] = relationship("MemoryNode", backref="memory_traces")

    @property
    def task_ref(self) -> str | None:
        return self.task.task_id if self.task else None

    @property
    def node_ref(self) -> str | None:
        return self.node.node_id if self.node else None
