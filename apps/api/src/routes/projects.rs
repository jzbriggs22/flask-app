use axum::{
    extract::{Path, State},
    Json,
};
use sqlx::PgPool;
use uuid::Uuid;

use crate::models::{Project, CreateProjectRequest, UpdateProjectRequest};

/// GET /api/projects
pub async fn list_projects(
    State(pool): State<PgPool>,
) -> Json<Vec<Project>> {
    let projects = sqlx::query_as::<_, Project>(
        "SELECT * FROM projects WHERE deleted_at IS NULL ORDER BY created_at DESC"
    )
    .fetch_all(&pool)
    .await
    .unwrap_or_default();

    Json(projects)
}

/// POST /api/projects
pub async fn create_project(
    State(pool): State<PgPool>,
    Json(body): Json<CreateProjectRequest>,
) -> Json<Project> {
    let project = sqlx::query_as::<_, Project>(
        r#"
        INSERT INTO projects (id, organization_id, name, number, status, address, created_by, created_at, updated_at)
        VALUES ($1, $2, $3, $4, 'active', $5, $6, NOW(), NOW())
        RETURNING *
        "#,
    )
    .bind(Uuid::new_v4())
    .bind(Uuid::nil()) // TODO: get from auth context
    .bind(&body.name)
    .bind(body.number.as_deref().unwrap_or(""))
    .bind(body.address.as_deref())
    .bind(Uuid::nil()) // TODO: get from auth context
    .fetch_one(&pool)
    .await
    .expect("Failed to create project");

    Json(project)
}

/// GET /api/projects/:id
pub async fn get_project(
    State(pool): State<PgPool>,
    Path(id): Path<Uuid>,
) -> Json<Option<Project>> {
    let project = sqlx::query_as::<_, Project>(
        "SELECT * FROM projects WHERE id = $1 AND deleted_at IS NULL"
    )
    .bind(id)
    .fetch_optional(&pool)
    .await
    .unwrap_or(None);

    Json(project)
}

/// PUT /api/projects/:id
pub async fn update_project(
    State(pool): State<PgPool>,
    Path(id): Path<Uuid>,
    Json(body): Json<UpdateProjectRequest>,
) -> Json<Option<Project>> {
    // Build dynamic update - for MVP, update all provided fields
    let project = sqlx::query_as::<_, Project>(
        r#"
        UPDATE projects SET
            name = COALESCE($2, name),
            number = COALESCE($3, number),
            address = COALESCE($4, address),
            updated_at = NOW()
        WHERE id = $1 AND deleted_at IS NULL
        RETURNING *
        "#,
    )
    .bind(id)
    .bind(body.name.as_deref())
    .bind(body.number.as_deref())
    .bind(body.address.as_deref())
    .fetch_optional(&pool)
    .await
    .unwrap_or(None);

    Json(project)
}

/// DELETE /api/projects/:id (soft delete)
pub async fn delete_project(
    State(pool): State<PgPool>,
    Path(id): Path<Uuid>,
) -> Json<serde_json::Value> {
    sqlx::query("UPDATE projects SET deleted_at = NOW() WHERE id = $1")
        .bind(id)
        .execute(&pool)
        .await
        .ok();

    Json(serde_json::json!({ "deleted": true }))
}
