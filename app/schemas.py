"""Pydantic models for request and response payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, root_validator, validator

TaskStatus = Literal["pending", "in_progress", "complete", "blocked"]


class PaginationMeta(BaseModel):
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)


class UserBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr

    @validator("name")
    def strip_name(cls, value: str) -> str:  # noqa: D401
        return value.strip()


class UserCreate(UserBase):
    pass


class UserRead(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class UserPage(BaseModel):
    items: list[UserRead]
    meta: PaginationMeta


class TaskBase(BaseModel):
    task_id: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=255)
    project: str | None = Field(default=None, max_length=120)
    status: TaskStatus = Field(default="pending")
    context: dict = Field(default_factory=dict)
    outputs: dict = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    owner_id: int | None = None

    @validator("task_id", "name", pre=True)
    def strip_strings(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value

    @validator("task_id")
    def uppercase_task_id(cls, value: str) -> str:
        return value.upper()

    @validator("project", pre=True, always=True)
    def strip_project(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @validator("dependencies", pre=True, always=True)
    def normalise_dependencies(cls, value: list[str]) -> list[str]:
        if not value:
            return []
        return sorted({dep.strip() for dep in value if isinstance(dep, str) and dep.strip()})


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    project: str | None = Field(default=None, max_length=120)
    status: TaskStatus | None = None
    context: dict | None = None
    outputs: dict | None = None
    dependencies: list[str] | None = None
    owner_id: int | None = None

    @validator("name", "project", pre=True)
    def strip_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @validator("dependencies", pre=True)
    def normalise_optional_dependencies(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return sorted({dep.strip() for dep in value if isinstance(dep, str) and dep.strip()})


class TaskRead(TaskBase):
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class TaskBulkUpdateItem(BaseModel):
    task_id: str = Field(..., min_length=1, max_length=64)
    status: TaskStatus | None = None
    context: dict | None = None
    outputs: dict | None = None
    dependencies: list[str] | None = None
    owner_id: int | None = None

    @validator("task_id", pre=True)
    def strip_task_id(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @validator("dependencies", pre=True)
    def normalise_bulk_dependencies(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return sorted({dep.strip() for dep in value if isinstance(dep, str) and dep.strip()})


class TaskBulkUpdateRequest(BaseModel):
    updates: list[TaskBulkUpdateItem]


class TaskPage(BaseModel):
    items: list[TaskRead]
    meta: PaginationMeta


class Message(BaseModel):
    detail: str


NODE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,63}$"
EDGE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,63}$"
TRACE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{2,63}$"


class MemoryNodeBase(BaseModel):
    node_id: str = Field(..., regex=NODE_ID_PATTERN, max_length=64)
    title: str = Field(..., min_length=1, max_length=255)
    summary: str | None = Field(default=None, max_length=500)
    data: dict = Field(default_factory=dict)
    originating_task_ref: str | None = Field(default=None, max_length=64)

    @validator("node_id", "title", pre=True)
    def strip_values(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value

    @validator("node_id")
    def uppercase_node_id(cls, value: str) -> str:
        return value.upper()

    @validator("summary", pre=True)
    def strip_summary(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @validator("originating_task_ref")
    def uppercase_originating_task(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.upper()


class MemoryNodeCreate(MemoryNodeBase):
    pass


class MemoryNodeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    summary: str | None = Field(default=None, max_length=500)
    data: dict | None = None
    originating_task_ref: str | None = Field(default=None, max_length=64)

    @validator("title", "summary", pre=True)
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @validator("originating_task_ref")
    def uppercase_originating(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.upper()


class MemoryNodeRead(MemoryNodeBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class MemoryNodePage(BaseModel):
    items: list[MemoryNodeRead]
    meta: PaginationMeta


class MemoryEdgeBase(BaseModel):
    edge_id: str = Field(..., regex=EDGE_ID_PATTERN, max_length=64)
    relation: str = Field(..., min_length=1, max_length=80)
    weight: float = Field(default=1.0, gt=0)
    source_node_ref: str | None = Field(default=None, max_length=64)
    target_node_ref: str | None = Field(default=None, max_length=64)
    source_task_ref: str | None = Field(default=None, max_length=64)
    target_task_ref: str | None = Field(default=None, max_length=64)

    @validator("edge_id", "relation", pre=True)
    def strip_string_values(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value

    @validator("edge_id")
    def uppercase_edge_id(cls, value: str) -> str:
        return value.upper()

    @validator(
        "source_node_ref",
        "target_node_ref",
        "source_task_ref",
        "target_task_ref",
    )
    def uppercase_refs(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.upper()


class MemoryEdgeCreate(MemoryEdgeBase):
    @root_validator()
    def validate_endpoints(cls, values):  # noqa: ANN001
        if not values.get("source_node_ref") and not values.get("source_task_ref"):
            raise ValueError("Edge must specify a source node or task.")
        if not values.get("target_node_ref") and not values.get("target_task_ref"):
            raise ValueError("Edge must specify a target node or task.")
        return values


class MemoryEdgeUpdate(BaseModel):
    relation: str | None = Field(default=None, min_length=1, max_length=80)
    weight: float | None = Field(default=None, gt=0)
    target_node_ref: str | None = Field(default=None, max_length=64)
    target_task_ref: str | None = Field(default=None, max_length=64)

    @validator("relation", pre=True)
    def strip_relation(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class MemoryEdgeRead(MemoryEdgeBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class MemoryEdgePage(BaseModel):
    items: list[MemoryEdgeRead]
    meta: PaginationMeta


class MemoryGraphRead(BaseModel):
    nodes: list[MemoryNodeRead]
    edges: list[MemoryEdgeRead]


class MemoryTraceBase(BaseModel):
    trace_id: str = Field(..., regex=TRACE_ID_PATTERN, max_length=64)
    source: str = Field(..., min_length=1, max_length=120)
    payload: dict = Field(default_factory=dict)
    task_ref: str | None = Field(default=None, max_length=64)
    node_ref: str | None = Field(default=None, max_length=64)

    @validator("trace_id", "source", pre=True)
    def strip_trace_values(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value

    @validator("trace_id")
    def uppercase_trace(cls, value: str) -> str:
        return value.upper()

    @validator("task_ref", "node_ref")
    def uppercase_refs(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.upper()


class MemoryTraceCreate(MemoryTraceBase):
    @root_validator()
    def ensure_anchor(cls, values):  # noqa: ANN001
        if not values.get("task_ref") and not values.get("node_ref"):
            raise ValueError("Trace must reference a task or node.")
        return values


class MemoryTraceRead(MemoryTraceBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


class ApiKeyAnalytics(BaseModel):
    name: str
    owner_email: str | None
    description: str | None
    scopes: list[str]
    is_active: bool
    request_count: int
    error_count: int
    last_used_at: datetime | None
    last_error_at: datetime | None
    last_error_reason: str | None
    expires_at: datetime | None


class ApiKeyArchiveRead(BaseModel):
    name: str
    owner_email: str | None
    scopes: list[str]
    expires_at: datetime | None
    archived_at: datetime
    archive_reason: str | None
    last_error_reason: str | None
    request_count: int
    error_count: int

    class Config:
        orm_mode = True


class ApiKeyArchivePage(BaseModel):
    items: list[ApiKeyArchiveRead]
    meta: PaginationMeta
