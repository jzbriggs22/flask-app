"""API routes for the task registry."""

from __future__ import annotations

from typing import Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .database import get_session
from .models import (
    ApiKey,
    ApiKeyArchive,
    MemoryEdge,
    MemoryNode,
    MemoryTrace,
    TASK_STATUSES,
    Task,
    User,
)
from .schemas import (
    ApiKeyAnalytics,
    ApiKeyArchivePage,
    ApiKeyArchiveRead,
    Message,
    MemoryEdgeCreate,
    MemoryEdgeRead,
    MemoryEdgeUpdate,
    MemoryGraphRead,
    MemoryNodeCreate,
    MemoryNodeRead,
    MemoryNodeUpdate,
    MemoryTraceCreate,
    MemoryTraceRead,
    TaskBulkUpdateRequest,
    TaskRead,
    TaskPage,
    TaskUpdate,
    UserCreate,
    UserRead,
)
from .schemas import TaskCreate

router = APIRouter()


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(user_in: UserCreate, session: Session = Depends(get_session)) -> UserRead:
    existing = session.execute(select(User).where(User.email == user_in.email)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with that email already exists.")

    user = User(name=user_in.name.strip(), email=user_in.email.strip())
    session.add(user)
    session.commit()
    session.refresh(user)
    return UserRead.from_orm(user)


@router.get("/users", response_model=list[UserRead])
def list_users(session: Session = Depends(get_session)) -> list[UserRead]:
    users = session.execute(select(User).order_by(User.id.asc())).scalars().all()
    return [UserRead.from_orm(user) for user in users]


@router.get("/users/{user_id}", response_model=UserRead)
def get_user(user_id: int, session: Session = Depends(get_session)) -> UserRead:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return UserRead.from_orm(user)


def _ensure_owner_exists(session: Session, owner_id: int | None) -> None:
    if owner_id is None:
        return
    if session.get(User, owner_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Owner user does not exist.")


def _require_scope(request: Request, scope: str) -> None:
    scopes = getattr(request.state, "api_key_scopes", set())
    if scope not in scopes and "all" not in scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Scope '{scope}' is required for this endpoint.",
        )


def _get_task_by_ref(session: Session, task_ref: str) -> Task:
    task_ref = task_ref.upper()
    task = session.execute(select(Task).where(Task.task_id == task_ref)).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    return task


def _get_node_by_ref(session: Session, node_ref: str) -> MemoryNode:
    node_ref = node_ref.upper()
    node = session.execute(select(MemoryNode).where(MemoryNode.node_id == node_ref)).scalar_one_or_none()
    if node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory node not found.")
    return node


@router.post("/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(task_in: TaskCreate, session: Session = Depends(get_session)) -> TaskRead:
    _ensure_owner_exists(session, task_in.owner_id)

    existing = session.execute(select(Task).where(Task.task_id == task_in.task_id)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Task identifier must be unique.")

    task = Task(
        task_id=task_in.task_id,
        name=task_in.name,
        project=task_in.project,
        status=task_in.status,
        context=task_in.context,
        outputs=task_in.outputs,
        dependencies=task_in.dependencies,
        owner_id=task_in.owner_id,
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return TaskRead.from_orm(task)


@router.get("/tasks", response_model=TaskPage)
def list_tasks(
    status_filter: str | None = Query(default=None, alias="status"),
    project: str | None = None,
    owner_id: int | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> TaskPage:
    query = select(Task)

    if status_filter:
        if status_filter not in TASK_STATUSES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status filter.")
        query = query.where(Task.status == status_filter)
    if project:
        query = query.where(Task.project == project)
    if owner_id is not None:
        query = query.where(Task.owner_id == owner_id)

    total = session.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    rows = (
        session.execute(
            query.order_by(Task.created_at.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return TaskPage(
        items=[TaskRead.from_orm(task) for task in rows],
        meta={"total": total, "page": page, "page_size": page_size},
    )


@router.get("/tasks/{task_id}", response_model=TaskRead)
def get_task(task_id: str, session: Session = Depends(get_session)) -> TaskRead:
    task = session.execute(select(Task).where(Task.task_id == task_id.upper())).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    return TaskRead.from_orm(task)


@router.patch("/tasks/{task_id}", response_model=TaskRead)
def update_task(task_id: str, task_update: TaskUpdate, session: Session = Depends(get_session)) -> TaskRead:
    task = session.execute(select(Task).where(Task.task_id == task_id.upper())).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

    if task_update.owner_id is not None:
        _ensure_owner_exists(session, task_update.owner_id)

    update_data = task_update.dict(exclude_unset=True)

    for field, value in update_data.items():
        setattr(task, field, value)

    session.add(task)
    session.commit()
    session.refresh(task)
    return TaskRead.from_orm(task)


@router.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_task(task_id: str, session: Session = Depends(get_session)) -> Response:
    task = session.execute(select(Task).where(Task.task_id == task_id.upper())).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    session.delete(task)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/memory/nodes", response_model=MemoryNodeRead, status_code=status.HTTP_201_CREATED)
def create_memory_node(
    node_in: MemoryNodeCreate, session: Session = Depends(get_session)
) -> MemoryNodeRead:
    existing = (
        session.execute(select(MemoryNode).where(MemoryNode.node_id == node_in.node_id))
        .scalar_one_or_none()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Memory node identifier must be unique.",
        )

    originating_task_id: int | None = None
    if node_in.originating_task_ref:
        originating_task_id = _get_task_by_ref(session, node_in.originating_task_ref).id

    node = MemoryNode(
        node_id=node_in.node_id,
        title=node_in.title,
        summary=node_in.summary,
        data=node_in.data,
        originating_task_id=originating_task_id,
    )
    session.add(node)
    session.commit()
    session.refresh(node)
    return MemoryNodeRead.from_orm(node)


@router.get("/memory/nodes", response_model=list[MemoryNodeRead])
def list_memory_nodes(
    task_ref: str | None = Query(default=None, alias="task"),
    session: Session = Depends(get_session),
) -> list[MemoryNodeRead]:
    query = select(MemoryNode)
    if task_ref:
        task = _get_task_by_ref(session, task_ref)
        query = query.where(MemoryNode.originating_task_id == task.id)

    nodes = session.execute(query.order_by(MemoryNode.created_at.asc())).scalars().all()
    return [MemoryNodeRead.from_orm(node) for node in nodes]


@router.get("/memory/nodes/{node_ref}", response_model=MemoryNodeRead)
def get_memory_node(node_ref: str, session: Session = Depends(get_session)) -> MemoryNodeRead:
    node = _get_node_by_ref(session, node_ref)
    return MemoryNodeRead.from_orm(node)


@router.patch("/memory/nodes/{node_ref}", response_model=MemoryNodeRead)
def update_memory_node(
    node_ref: str, node_update: MemoryNodeUpdate, session: Session = Depends(get_session)
) -> MemoryNodeRead:
    node = _get_node_by_ref(session, node_ref)

    update_data = node_update.dict(exclude_unset=True)

    if "originating_task_ref" in update_data:
        task_ref = update_data.pop("originating_task_ref")
        if task_ref is None:
            node.originating_task_id = None
        else:
            node.originating_task_id = _get_task_by_ref(session, task_ref).id

    for field, value in update_data.items():
        setattr(node, field, value)

    session.add(node)
    session.commit()
    session.refresh(node)
    return MemoryNodeRead.from_orm(node)


@router.delete(
    "/memory/nodes/{node_ref}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_memory_node(node_ref: str, session: Session = Depends(get_session)) -> Response:
    node = _get_node_by_ref(session, node_ref)
    session.delete(node)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _attach_node(
    session: Session, node_ref: str | None, allow_none: bool = True
) -> int | None:
    if node_ref is None:
        if allow_none:
            return None
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Node reference required.")
    return _get_node_by_ref(session, node_ref).id


def _attach_task(session: Session, task_ref: str | None) -> int | None:
    if task_ref is None:
        return None
    return _get_task_by_ref(session, task_ref).id


def _get_trace_by_ref(session: Session, trace_ref: str) -> MemoryTrace:
    trace = (
        session.execute(
            select(MemoryTrace)
            .where(MemoryTrace.trace_id == trace_ref.upper())
            .options(
                selectinload(MemoryTrace.task),
                selectinload(MemoryTrace.node),
            )
        )
        .scalar_one_or_none()
    )
    if trace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Memory trace not found."
        )
    return trace


@router.post("/memory/edges", response_model=MemoryEdgeRead, status_code=status.HTTP_201_CREATED)
def create_memory_edge(
    edge_in: MemoryEdgeCreate, session: Session = Depends(get_session)
) -> MemoryEdgeRead:
    existing = (
        session.execute(select(MemoryEdge).where(MemoryEdge.edge_id == edge_in.edge_id))
        .scalar_one_or_none()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Memory edge identifier must be unique.",
        )

    edge = MemoryEdge(
        edge_id=edge_in.edge_id,
        relation=edge_in.relation,
        weight=edge_in.weight,
        source_node_id=_attach_node(session, edge_in.source_node_ref),
        target_node_id=_attach_node(session, edge_in.target_node_ref),
        source_task_id=_attach_task(session, edge_in.source_task_ref),
        target_task_id=_attach_task(session, edge_in.target_task_ref),
    )
    session.add(edge)
    session.commit()
    session.refresh(edge)
    return MemoryEdgeRead.from_orm(edge)


@router.get("/memory/edges", response_model=list[MemoryEdgeRead])
def list_memory_edges(
    source_node: str | None = Query(default=None, alias="source_node"),
    target_node: str | None = Query(default=None, alias="target_node"),
    source_task: str | None = Query(default=None, alias="source_task"),
    target_task: str | None = Query(default=None, alias="target_task"),
    session: Session = Depends(get_session),
) -> list[MemoryEdgeRead]:
    query = select(MemoryEdge).options(
        selectinload(MemoryEdge.source_node),
        selectinload(MemoryEdge.target_node),
        selectinload(MemoryEdge.source_task),
        selectinload(MemoryEdge.target_task),
    )

    if source_node:
        query = query.where(MemoryEdge.source_node_id == _attach_node(session, source_node, allow_none=False))
    if target_node:
        query = query.where(MemoryEdge.target_node_id == _attach_node(session, target_node, allow_none=False))
    if source_task:
        query = query.where(MemoryEdge.source_task_id == _attach_task(session, source_task))
    if target_task:
        query = query.where(MemoryEdge.target_task_id == _attach_task(session, target_task))

    edges = session.execute(query.order_by(MemoryEdge.created_at.asc())).scalars().all()
    return [MemoryEdgeRead.from_orm(edge) for edge in edges]


@router.get("/memory/edges/{edge_ref}", response_model=MemoryEdgeRead)
def get_memory_edge(edge_ref: str, session: Session = Depends(get_session)) -> MemoryEdgeRead:
    edge = (
        session.execute(
            select(MemoryEdge)
            .where(MemoryEdge.edge_id == edge_ref.upper())
            .options(
                selectinload(MemoryEdge.source_node),
                selectinload(MemoryEdge.target_node),
                selectinload(MemoryEdge.source_task),
                selectinload(MemoryEdge.target_task),
            )
        )
        .scalar_one_or_none()
    )
    if edge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory edge not found.")
    return MemoryEdgeRead.from_orm(edge)


@router.patch("/memory/edges/{edge_ref}", response_model=MemoryEdgeRead)
def update_memory_edge(
    edge_ref: str, edge_update: MemoryEdgeUpdate, session: Session = Depends(get_session)
) -> MemoryEdgeRead:
    edge = (
        session.execute(select(MemoryEdge).where(MemoryEdge.edge_id == edge_ref.upper()))
        .scalar_one_or_none()
    )
    if edge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory edge not found.")

    update_data = edge_update.dict(exclude_unset=True)

    if "target_node_ref" in update_data:
        node_ref = update_data.pop("target_node_ref")
        edge.target_node_id = _attach_node(session, node_ref) if node_ref else None
    if "target_task_ref" in update_data:
        task_ref = update_data.pop("target_task_ref")
        edge.target_task_id = _attach_task(session, task_ref)

    for field, value in update_data.items():
        setattr(edge, field, value)

    session.add(edge)
    session.commit()
    session.refresh(edge)
    return MemoryEdgeRead.from_orm(edge)


@router.delete(
    "/memory/edges/{edge_ref}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_memory_edge(edge_ref: str, session: Session = Depends(get_session)) -> Response:
    edge = (
        session.execute(select(MemoryEdge).where(MemoryEdge.edge_id == edge_ref.upper()))
        .scalar_one_or_none()
    )
    if edge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory edge not found.")
    session.delete(edge)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/memory/traces", response_model=MemoryTraceRead, status_code=status.HTTP_201_CREATED)
def create_memory_trace(
    trace_in: MemoryTraceCreate, session: Session = Depends(get_session)
) -> MemoryTraceRead:
    existing = (
        session.execute(select(MemoryTrace).where(MemoryTrace.trace_id == trace_in.trace_id))
        .scalar_one_or_none()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Memory trace identifier must be unique.",
        )

    trace = MemoryTrace(
        trace_id=trace_in.trace_id,
        source=trace_in.source,
        payload=trace_in.payload,
        task_id=_attach_task(session, trace_in.task_ref),
        node_id=_attach_node(session, trace_in.node_ref),
    )
    session.add(trace)
    session.commit()
    session.refresh(trace)
    return MemoryTraceRead.from_orm(trace)


@router.get("/memory/traces", response_model=list[MemoryTraceRead])
def list_memory_traces(
    task_ref: str | None = Query(default=None, alias="task"),
    node_ref: str | None = Query(default=None, alias="node"),
    source: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
) -> list[MemoryTraceRead]:
    query = select(MemoryTrace).options(
        selectinload(MemoryTrace.task),
        selectinload(MemoryTrace.node),
    )

    if task_ref:
        task_id = _attach_task(session, task_ref)
        query = query.where(MemoryTrace.task_id == task_id)
    if node_ref:
        node_id = _attach_node(session, node_ref, allow_none=False)
        query = query.where(MemoryTrace.node_id == node_id)
    if source:
        source_value = source.strip()
        if source_value:
            query = query.where(MemoryTrace.source == source_value)

    traces = (
        session.execute(
            query.order_by(MemoryTrace.created_at.desc()).limit(limit)
        )
        .scalars()
        .all()
    )
    return [MemoryTraceRead.from_orm(trace) for trace in traces]


@router.get("/memory/traces/{trace_ref}", response_model=MemoryTraceRead)
def get_memory_trace(trace_ref: str, session: Session = Depends(get_session)) -> MemoryTraceRead:
    trace = _get_trace_by_ref(session, trace_ref)
    return MemoryTraceRead.from_orm(trace)


@router.get("/memory/graph", response_model=MemoryGraphRead)
def memory_graph(
    node_ref: str | None = Query(default=None, alias="node"),
    task_ref: str | None = Query(default=None, alias="task"),
    session: Session = Depends(get_session),
) -> MemoryGraphRead:
    nodes: list[MemoryNode] = []
    node_ids: set[int] = set()
    task = None

    if node_ref:
        node = _get_node_by_ref(session, node_ref)
        nodes.append(node)
        node_ids.add(node.id)

    if task_ref:
        task = _get_task_by_ref(session, task_ref)
        task_nodes = (
            session.execute(
                select(MemoryNode).where(MemoryNode.originating_task_id == task.id)
            )
            .scalars()
            .all()
        )
        for node in task_nodes:
            if node.id not in node_ids:
                nodes.append(node)
                node_ids.add(node.id)

    edges_query = select(MemoryEdge).options(
        selectinload(MemoryEdge.source_node),
        selectinload(MemoryEdge.target_node),
        selectinload(MemoryEdge.source_task),
        selectinload(MemoryEdge.target_task),
    )

    conditions = []
    if node_ids:
        conditions.append(
            or_(
                MemoryEdge.source_node_id.in_(node_ids),
                MemoryEdge.target_node_id.in_(node_ids),
            )
        )
    if task is not None:
        conditions.append(
            or_(
                MemoryEdge.source_task_id == task.id,
                MemoryEdge.target_task_id == task.id,
            )
        )

    if conditions:
        edges_query = edges_query.where(or_(*conditions))

    edge_models = session.execute(edges_query.order_by(MemoryEdge.created_at.asc())).scalars().all()

    extra_node_ids: set[int] = set()
    for edge in edge_models:
        if edge.source_node_id and edge.source_node_id not in node_ids:
            extra_node_ids.add(edge.source_node_id)
        if edge.target_node_id and edge.target_node_id not in node_ids:
            extra_node_ids.add(edge.target_node_id)

    if extra_node_ids:
        extra_nodes = (
            session.execute(select(MemoryNode).where(MemoryNode.id.in_(extra_node_ids)))
            .scalars()
            .all()
        )
        for node in extra_nodes:
            if node.id not in node_ids:
                nodes.append(node)
                node_ids.add(node.id)

    nodes_sorted = sorted(nodes, key=lambda n: n.created_at)

    return MemoryGraphRead(
        nodes=[MemoryNodeRead.from_orm(node) for node in nodes_sorted],
        edges=[MemoryEdgeRead.from_orm(edge) for edge in edge_models],
    )


@router.get("/tasks/{task_id}/timeline", response_model=list[MemoryTraceRead])
def task_timeline(task_id: str, session: Session = Depends(get_session)) -> list[MemoryTraceRead]:
    task = _get_task_by_ref(session, task_id)
    traces = (
        session.execute(
            select(MemoryTrace)
            .where(MemoryTrace.task_id == task.id)
            .options(selectinload(MemoryTrace.node))
            .order_by(MemoryTrace.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [MemoryTraceRead.from_orm(trace) for trace in traces]
@router.post("/tasks/bulk-update", response_model=list[TaskRead])
def bulk_update_tasks(
    bulk_update: TaskBulkUpdateRequest, session: Session = Depends(get_session)
) -> list[TaskRead]:
    if not bulk_update.updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No updates supplied.")

    task_ids = [item.task_id for item in bulk_update.updates]
    seen: set[str] = set()
    for task_id in task_ids:
        if task_id in seen:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate task identifiers provided in bulk update.",
            )
        seen.add(task_id)

    tasks: Sequence[Task] = (
        session.execute(select(Task).where(Task.task_id.in_(task_ids))).scalars().all()
    )

    if len(tasks) != len(task_ids):
        found_ids = {task.task_id for task in tasks}
        missing = sorted(set(task_ids) - found_ids)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tasks not found: {', '.join(missing)}",
        )

    mapped_tasks = {task.task_id: task for task in tasks}

    for update in bulk_update.updates:
        task = mapped_tasks.get(update.task_id)
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {update.task_id} not found.")
        if update.owner_id is not None:
            _ensure_owner_exists(session, update.owner_id)
        update_data = update.dict(exclude_unset=True)
        update_data.pop("task_id", None)
        for field, value in update_data.items():
            setattr(task, field, value)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc.orig)) from exc

    refreshed = [TaskRead.from_orm(mapped_tasks[task_id]) for task_id in task_ids]
    return refreshed


@router.get("/admin/api-keys/analytics", response_model=list[ApiKeyAnalytics])
def list_api_key_analytics(
    request: Request, session: Session = Depends(get_session)
) -> list[ApiKeyAnalytics]:
    _require_scope(request, "monitor")
    records = (
        session.execute(select(ApiKey).order_by(ApiKey.created_at.asc())).scalars().all()
    )
    return [
        ApiKeyAnalytics(
            name=record.name,
            owner_email=record.owner_email,
            description=record.description,
            scopes=record.scopes or [],
            is_active=record.is_active,
            request_count=record.request_count,
            error_count=record.error_count,
            last_used_at=record.last_used_at,
            last_error_at=record.last_error_at,
            last_error_reason=record.last_error_reason,
            expires_at=record.expires_at,
        )
        for record in records
    ]


@router.get("/admin/api-keys/archives", response_model=ApiKeyArchivePage)
def list_api_key_archives(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> ApiKeyArchivePage:
    _require_scope(request, "monitor")
    query = select(ApiKeyArchive)
    total = session.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    rows = (
        session.execute(
            query.order_by(ApiKeyArchive.archived_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return ApiKeyArchivePage(
        items=[ApiKeyArchiveRead.from_orm(row) for row in rows],
        meta={"total": total, "page": page, "page_size": page_size},
    )
