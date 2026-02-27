use axum::{
    extract::{Path, State},
    Json,
};
use sqlx::PgPool;
use uuid::Uuid;

use crate::models::{
    Estimate, EstimateLineItem,
    CreateEstimateRequest, CreateLineItemRequest, UpdateLineItemRequest,
};

/// GET /api/projects/:project_id/estimates
pub async fn list_estimates(
    State(pool): State<PgPool>,
    Path(project_id): Path<Uuid>,
) -> Json<Vec<Estimate>> {
    let estimates = sqlx::query_as::<_, Estimate>(
        "SELECT * FROM estimates WHERE project_id = $1 ORDER BY created_at DESC"
    )
    .bind(project_id)
    .fetch_all(&pool)
    .await
    .unwrap_or_default();

    Json(estimates)
}

/// POST /api/projects/:project_id/estimates
pub async fn create_estimate(
    State(pool): State<PgPool>,
    Path(project_id): Path<Uuid>,
    Json(body): Json<CreateEstimateRequest>,
) -> Json<Estimate> {
    let estimate = sqlx::query_as::<_, Estimate>(
        r#"
        INSERT INTO estimates (id, project_id, name, status, created_by, created_at, updated_at)
        VALUES ($1, $2, $3, 'draft', $4, NOW(), NOW())
        RETURNING *
        "#,
    )
    .bind(Uuid::new_v4())
    .bind(project_id)
    .bind(&body.name)
    .bind(Uuid::nil()) // TODO: get from auth context
    .fetch_one(&pool)
    .await
    .expect("Failed to create estimate");

    Json(estimate)
}

/// GET /api/estimates/:estimate_id
pub async fn get_estimate(
    State(pool): State<PgPool>,
    Path(estimate_id): Path<Uuid>,
) -> Json<Option<Estimate>> {
    let estimate = sqlx::query_as::<_, Estimate>(
        "SELECT * FROM estimates WHERE id = $1"
    )
    .bind(estimate_id)
    .fetch_optional(&pool)
    .await
    .unwrap_or(None);

    Json(estimate)
}

/// GET /api/estimates/:estimate_id/line-items
pub async fn list_line_items(
    State(pool): State<PgPool>,
    Path(estimate_id): Path<Uuid>,
) -> Json<Vec<EstimateLineItem>> {
    let items = sqlx::query_as::<_, EstimateLineItem>(
        "SELECT * FROM estimate_line_items WHERE estimate_id = $1 ORDER BY sort_order, created_at"
    )
    .bind(estimate_id)
    .fetch_all(&pool)
    .await
    .unwrap_or_default();

    Json(items)
}

/// POST /api/estimates/:estimate_id/line-items
pub async fn create_line_item(
    State(pool): State<PgPool>,
    Path(estimate_id): Path<Uuid>,
    Json(body): Json<CreateLineItemRequest>,
) -> Json<EstimateLineItem> {
    let item = sqlx::query_as::<_, EstimateLineItem>(
        r#"
        INSERT INTO estimate_line_items (id, estimate_id, cost_code, description, quantity, unit, unit_cost_cents, measurement_id, sort_order, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 0, NOW(), NOW())
        RETURNING *
        "#,
    )
    .bind(Uuid::new_v4())
    .bind(estimate_id)
    .bind(&body.cost_code)
    .bind(&body.description)
    .bind(body.quantity)
    .bind(&body.unit)
    .bind(body.unit_cost_cents)
    .bind(body.measurement_id)
    .fetch_one(&pool)
    .await
    .expect("Failed to create line item");

    Json(item)
}

/// PUT /api/line-items/:item_id
pub async fn update_line_item(
    State(pool): State<PgPool>,
    Path(item_id): Path<Uuid>,
    Json(body): Json<UpdateLineItemRequest>,
) -> Json<Option<EstimateLineItem>> {
    let item = sqlx::query_as::<_, EstimateLineItem>(
        r#"
        UPDATE estimate_line_items SET
            cost_code = COALESCE($2, cost_code),
            description = COALESCE($3, description),
            quantity = COALESCE($4, quantity),
            unit = COALESCE($5, unit),
            unit_cost_cents = COALESCE($6, unit_cost_cents),
            updated_at = NOW()
        WHERE id = $1
        RETURNING *
        "#,
    )
    .bind(item_id)
    .bind(body.cost_code.as_deref())
    .bind(body.description.as_deref())
    .bind(body.quantity)
    .bind(body.unit.as_deref())
    .bind(body.unit_cost_cents)
    .fetch_optional(&pool)
    .await
    .unwrap_or(None);

    Json(item)
}

/// DELETE /api/line-items/:item_id
pub async fn delete_line_item(
    State(pool): State<PgPool>,
    Path(item_id): Path<Uuid>,
) -> Json<serde_json::Value> {
    sqlx::query("DELETE FROM estimate_line_items WHERE id = $1")
        .bind(item_id)
        .execute(&pool)
        .await
        .ok();

    Json(serde_json::json!({ "deleted": true }))
}
