use axum::{
    extract::{Path, State},
    Json,
};
use sqlx::PgPool;
use uuid::Uuid;

use crate::error::{ApiError, ApiResult};
use crate::models::{
    Estimate, EstimateLineItem,
    CreateEstimateRequest, CreateLineItemRequest, UpdateLineItemRequest,
};
use crate::services::auth::{SYSTEM_ORG_ID, SYSTEM_USER_ID};

// ============================================================
// Org-scoping helpers (multi-tenant isolation)
// ============================================================

async fn assert_project_in_org(pool: &PgPool, project_id: Uuid) -> Result<(), ApiError> {
    let exists: bool = sqlx::query_scalar(
        "SELECT EXISTS(SELECT 1 FROM projects WHERE id = $1 AND organization_id = $2 AND deleted_at IS NULL)"
    )
    .bind(project_id)
    .bind(SYSTEM_ORG_ID)
    .fetch_one(pool)
    .await?;

    if exists { Ok(()) } else { Err(ApiError::not_found("Project")) }
}

async fn assert_estimate_in_org(pool: &PgPool, estimate_id: Uuid) -> Result<(), ApiError> {
    let exists: bool = sqlx::query_scalar(
        r#"
        SELECT EXISTS(
            SELECT 1 FROM estimates e
            JOIN projects p ON p.id = e.project_id
            WHERE e.id = $1 AND p.organization_id = $2 AND p.deleted_at IS NULL
        )
        "#,
    )
    .bind(estimate_id)
    .bind(SYSTEM_ORG_ID)
    .fetch_one(pool)
    .await?;

    if exists { Ok(()) } else { Err(ApiError::not_found("Estimate")) }
}

async fn assert_line_item_in_org(pool: &PgPool, item_id: Uuid) -> Result<(), ApiError> {
    let exists: bool = sqlx::query_scalar(
        r#"
        SELECT EXISTS(
            SELECT 1 FROM estimate_line_items li
            JOIN estimates e ON e.id = li.estimate_id
            JOIN projects p ON p.id = e.project_id
            WHERE li.id = $1 AND p.organization_id = $2 AND p.deleted_at IS NULL
        )
        "#,
    )
    .bind(item_id)
    .bind(SYSTEM_ORG_ID)
    .fetch_one(pool)
    .await?;

    if exists { Ok(()) } else { Err(ApiError::not_found("Line item")) }
}

// ============================================================
// Estimates
// ============================================================

/// GET /api/projects/:project_id/estimates
pub async fn list_estimates(
    State(pool): State<PgPool>,
    Path(project_id): Path<Uuid>,
) -> ApiResult<Vec<Estimate>> {
    let estimates = sqlx::query_as::<_, Estimate>(
        r#"
        SELECT e.* FROM estimates e
        JOIN projects p ON p.id = e.project_id
        WHERE e.project_id = $1 AND p.organization_id = $2 AND p.deleted_at IS NULL
        ORDER BY e.created_at DESC
        "#,
    )
    .bind(project_id)
    .bind(SYSTEM_ORG_ID)
    .fetch_all(&pool)
    .await?;

    Ok(Json(estimates))
}

/// POST /api/projects/:project_id/estimates
pub async fn create_estimate(
    State(pool): State<PgPool>,
    Path(project_id): Path<Uuid>,
    Json(body): Json<CreateEstimateRequest>,
) -> ApiResult<Estimate> {
    assert_project_in_org(&pool, project_id).await?;

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
    .bind(SYSTEM_USER_ID)
    .fetch_one(&pool)
    .await?;

    Ok(Json(estimate))
}

/// GET /api/estimates/:estimate_id
pub async fn get_estimate(
    State(pool): State<PgPool>,
    Path(estimate_id): Path<Uuid>,
) -> ApiResult<Estimate> {
    let estimate = sqlx::query_as::<_, Estimate>(
        r#"
        SELECT e.* FROM estimates e
        JOIN projects p ON p.id = e.project_id
        WHERE e.id = $1 AND p.organization_id = $2 AND p.deleted_at IS NULL
        "#,
    )
    .bind(estimate_id)
    .bind(SYSTEM_ORG_ID)
    .fetch_optional(&pool)
    .await?
    .ok_or_else(|| ApiError::not_found("Estimate"))?;

    Ok(Json(estimate))
}

// ============================================================
// Line Items (Spec §11)
// ============================================================

/// GET /api/estimates/:estimate_id/line-items
pub async fn list_line_items(
    State(pool): State<PgPool>,
    Path(estimate_id): Path<Uuid>,
) -> ApiResult<Vec<EstimateLineItem>> {
    assert_estimate_in_org(&pool, estimate_id).await?;

    let items = sqlx::query_as::<_, EstimateLineItem>(
        "SELECT * FROM estimate_line_items WHERE estimate_id = $1 ORDER BY sort_order, created_at"
    )
    .bind(estimate_id)
    .fetch_all(&pool)
    .await?;

    Ok(Json(items))
}

/// POST /api/estimates/:estimate_id/line-items
/// Supports both manual and driven line items (Spec §11).
pub async fn create_line_item(
    State(pool): State<PgPool>,
    Path(estimate_id): Path<Uuid>,
    Json(body): Json<CreateLineItemRequest>,
) -> ApiResult<EstimateLineItem> {
    assert_estimate_in_org(&pool, estimate_id).await?;

    let item_id = Uuid::new_v4();
    let source_type = body.source_type.as_deref().unwrap_or("manual");
    let user_id = SYSTEM_USER_ID;

    if source_type == "driven"
        && body.measurement_ids.as_ref().map_or(true, |ids| ids.is_empty())
    {
        return Err(ApiError::unprocessable(
            "MISSING_SOURCES",
            "driven line items must reference at least one measurement",
        ));
    }

    // For driven items, snapshot the quantity at linking time (§11)
    let (quantity_snapshot, snapshot_at): (Option<f64>, Option<chrono::DateTime<chrono::Utc>>) =
        if source_type == "driven" {
            (Some(body.quantity), Some(chrono::Utc::now()))
        } else {
            (None, None)
        };

    // Line item + its measurement source links must land atomically (§11):
    // a driven item without its source records loses traceability.
    let mut tx = pool.begin().await.map_err(ApiError::from)?;

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
    .fetch_one(&mut *tx)
    .await?;

    // For driven items: create source links to measurements (§11)
    if source_type == "driven" {
        if let Some(measurement_ids) = &body.measurement_ids {
            for measurement_id in measurement_ids {
                // Get the latest version for this measurement
                let latest_version_id: Option<Uuid> = sqlx::query_scalar(
                    "SELECT id FROM measurement_versions WHERE measurement_id = $1 ORDER BY version_number DESC LIMIT 1"
                )
                .bind(measurement_id)
                .fetch_optional(&mut *tx)
                .await?;

                let Some(version_id) = latest_version_id else {
                    return Err(ApiError::unprocessable(
                        "MISSING_VERSION",
                        format!("measurement {measurement_id} has no version record"),
                    ));
                };

                // Snapshot the CALIBRATED quantity only (Spec §5, §11).
                // quantity_raw is in PDF_PT — pricing it as a real-world
                // quantity would silently inflate the estimate. An
                // uncalibrated measurement must not drive pricing.
                let row: Option<(Option<f64>, String)> = sqlx::query_as(
                    "SELECT quantity_real, uom FROM measurements WHERE id = $1 AND deleted_at IS NULL"
                )
                .bind(measurement_id)
                .fetch_optional(&mut *tx)
                .await?;

                let Some((quantity_real, uom)) = row else {
                    return Err(ApiError::not_found("Source measurement"));
                };
                let Some(qty) = quantity_real else {
                    return Err(ApiError::unprocessable(
                        "UNCALIBRATED_MEASUREMENT",
                        format!(
                            "measurement {measurement_id} is uncalibrated and cannot drive pricing — calibrate the sheet first"
                        ),
                    ));
                };

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
                .bind(qty)
                .bind(&uom)
                .bind(user_id)
                .execute(&mut *tx)
                .await?;
            }
        }
    }

    tx.commit().await.map_err(ApiError::from)?;

    Ok(Json(item))
}

/// PUT /api/line-items/:item_id
pub async fn update_line_item(
    State(pool): State<PgPool>,
    Path(item_id): Path<Uuid>,
    Json(body): Json<UpdateLineItemRequest>,
) -> ApiResult<EstimateLineItem> {
    assert_line_item_in_org(&pool, item_id).await?;

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
    .await?
    .ok_or_else(|| ApiError::not_found("Line item"))?;

    Ok(Json(item))
}

/// DELETE /api/line-items/:item_id
pub async fn delete_line_item(
    State(pool): State<PgPool>,
    Path(item_id): Path<Uuid>,
) -> ApiResult<serde_json::Value> {
    assert_line_item_in_org(&pool, item_id).await?;

    let result = sqlx::query("DELETE FROM estimate_line_items WHERE id = $1")
        .bind(item_id)
        .execute(&pool)
        .await?;

    if result.rows_affected() == 0 {
        return Err(ApiError::not_found("Line item"));
    }

    Ok(Json(serde_json::json!({ "deleted": true })))
}
