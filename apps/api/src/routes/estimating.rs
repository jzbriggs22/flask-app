use axum::{
    extract::{Path, State},
    Json,
};
use sqlx::PgPool;
use uuid::Uuid;

use crate::models::{
    Estimate, EstimateLineItem, EstimateLineItemSource,
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
/// Supports both manual and driven line items (Spec §11).
pub async fn create_line_item(
    State(pool): State<PgPool>,
    Path(estimate_id): Path<Uuid>,
    Json(body): Json<CreateLineItemRequest>,
) -> Json<EstimateLineItem> {
    let item_id = Uuid::new_v4();
    let source_type = body.source_type.as_deref().unwrap_or("manual");
    let user_id = Uuid::nil(); // TODO: get from auth context

    // For driven items, snapshot the quantity at linking time (§11)
    let (quantity_snapshot, snapshot_at): (Option<f64>, Option<chrono::DateTime<chrono::Utc>>) =
        if source_type == "driven" {
            (Some(body.quantity), Some(chrono::Utc::now()))
        } else {
            (None, None)
        };

    let item = sqlx::query_as::<_, EstimateLineItem>(
        r#"
        INSERT INTO estimate_line_items (
            id, estimate_id, cost_code, description, quantity, unit,
            unit_cost_cents, source_type, quantity_snapshot, snapshot_at,
            is_stale, sort_order, created_at, updated_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6,
            $7, $8, $9, $10,
            false, 0, NOW(), NOW()
        )
        RETURNING *
        "#,
    )
    .bind(item_id)
    .bind(estimate_id)
    .bind(&body.cost_code)
    .bind(&body.description)
    .bind(body.quantity)
    .bind(&body.unit)
    .bind(body.unit_cost_cents)
    .bind(source_type)
    .bind(quantity_snapshot)
    .bind(snapshot_at)
    .fetch_one(&pool)
    .await
    .expect("Failed to create line item");

    // For driven items: create source links to measurements (§11)
    if source_type == "driven" {
        if let Some(measurement_ids) = &body.measurement_ids {
            for measurement_id in measurement_ids {
                // Get the latest version for this measurement
                let latest_version_id: Option<Uuid> = sqlx::query_scalar(
                    "SELECT id FROM measurement_versions WHERE measurement_id = $1 ORDER BY version_number DESC LIMIT 1"
                )
                .bind(measurement_id)
                .fetch_optional(&pool)
                .await
                .unwrap_or(None);

                if let Some(version_id) = latest_version_id {
                    // Get the measurement's quantity for the snapshot
                    let qty: Option<f64> = sqlx::query_scalar(
                        "SELECT COALESCE(quantity_real, quantity_raw) FROM measurements WHERE id = $1"
                    )
                    .bind(measurement_id)
                    .fetch_optional(&pool)
                    .await
                    .unwrap_or(None);

                    let uom: Option<String> = sqlx::query_scalar(
                        "SELECT uom FROM measurements WHERE id = $1"
                    )
                    .bind(measurement_id)
                    .fetch_optional(&pool)
                    .await
                    .unwrap_or(None);

                    sqlx::query(
                        r#"
                        INSERT INTO estimate_line_item_sources (
                            id, line_item_id, measurement_id, measurement_version_id,
                            quantity_snapshot, uom_snapshot, linked_at, linked_by
                        ) VALUES ($1, $2, $3, $4, $5, $6, NOW(), $7)
                        "#,
                    )
                    .bind(Uuid::new_v4())
                    .bind(item_id)
                    .bind(measurement_id)
                    .bind(version_id)
                    .bind(qty.unwrap_or(0.0))
                    .bind(uom.as_deref().unwrap_or(""))
                    .bind(user_id)
                    .execute(&pool)
                    .await
                    .ok();
                }
            }
        }
    }

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
