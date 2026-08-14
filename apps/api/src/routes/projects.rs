use axum::{
    extract::{Path, State},
    Json,
};
use sqlx::PgPool;
use uuid::Uuid;

use crate::error::{ApiError, ApiResult};
use crate::models::{Project, CreateProjectRequest, UpdateProjectRequest};
use crate::services::auth::{SYSTEM_ORG_ID, SYSTEM_USER_ID};

/// GET /api/projects
/// Scoped to the caller's organization for multi-tenant isolation.
pub async fn list_projects(State(pool): State<PgPool>) -> ApiResult<Vec<Project>> {
    let projects = sqlx::query_as::<_, Project>(
        "SELECT * FROM projects WHERE organization_id = $1 AND deleted_at IS NULL ORDER BY created_at DESC"
    )
    .bind(SYSTEM_ORG_ID)
    .fetch_all(&pool)
    .await?;

    Ok(Json(projects))
}

/// POST /api/projects
pub async fn create_project(
    State(pool): State<PgPool>,
    Json(body): Json<CreateProjectRequest>,
) -> ApiResult<Project> {
    let project = sqlx::query_as::<_, Project>(
        r#"
        INSERT INTO projects (id, organization_id, name, number, status, address, created_by, created_at, updated_at)
        VALUES ($1, $2, $3, $4, 'active', $5, $6, NOW(), NOW())
        RETURNING *
        "#,
    )
    .bind(Uuid::new_v4())
    .bind(SYSTEM_ORG_ID)
    .bind(&body.name)
    .bind(body.number.as_deref().unwrap_or(""))
    .bind(body.address.as_deref())
    .bind(SYSTEM_USER_ID)
    .fetch_one(&pool)
    .await?;

    Ok(Json(project))
}

/// GET /api/projects/:id
pub async fn get_project(
    State(pool): State<PgPool>,
    Path(id): Path<Uuid>,
) -> ApiResult<Project> {
    let project = sqlx::query_as::<_, Project>(
        "SELECT * FROM projects WHERE id = $1 AND organization_id = $2 AND deleted_at IS NULL"
    )
    .bind(id)
    .bind(SYSTEM_ORG_ID)
    .fetch_optional(&pool)
    .await?
    .ok_or_else(|| ApiError::not_found("Project"))?;

    Ok(Json(project))
}

/// PUT /api/projects/:id
pub async fn update_project(
    State(pool): State<PgPool>,
    Path(id): Path<Uuid>,
    Json(body): Json<UpdateProjectRequest>,
) -> ApiResult<Project> {
    let project = sqlx::query_as::<_, Project>(
        r#"
        UPDATE projects SET
            name = COALESCE($2, name),
            number = COALESCE($3, number),
            address = COALESCE($4, address),
            updated_at = NOW()
        WHERE id = $1 AND organization_id = $5 AND deleted_at IS NULL
        RETURNING *
        "#,
    )
    .bind(id)
    .bind(body.name.as_deref())
    .bind(body.number.as_deref())
    .bind(body.address.as_deref())
    .bind(SYSTEM_ORG_ID)
    .fetch_optional(&pool)
    .await?
    .ok_or_else(|| ApiError::not_found("Project"))?;

    Ok(Json(project))
}

/// DELETE /api/projects/:id (soft delete)
pub async fn delete_project(
    State(pool): State<PgPool>,
    Path(id): Path<Uuid>,
) -> ApiResult<serde_json::Value> {
    let result = sqlx::query(
        "UPDATE projects SET deleted_at = NOW() WHERE id = $1 AND organization_id = $2 AND deleted_at IS NULL"
    )
    .bind(id)
    .bind(SYSTEM_ORG_ID)
    .execute(&pool)
    .await?;

    if result.rows_affected() == 0 {
        return Err(ApiError::not_found("Project"));
    }

    Ok(Json(serde_json::json!({ "deleted": true })))
}
