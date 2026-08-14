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
use crate::services::quantity;

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
        "SELECT * FROM estimate_line_items WHERE estimate_id = $1 AND deleted_at IS NULL ORDER BY sort_order, created_at"
    )
    .bind(estimate_id)
    .fetch_all(&pool)
    .await?;

    Ok(Json(items))
}

/// A validated driven source, loaded from a live measurement.
struct DrivenSource {
    measurement_id: Uuid,
    version_id: Uuid,
    quantity: f64,
    uom: String,
}

/// Load one driven source measurement inside the caller's transaction.
/// Returns Ok(None) if the measurement is missing or soft-deleted; errors
/// if it is uncalibrated (must not drive pricing, §5/§11) or has no
/// version record (indicates corruption, §15).
async fn load_driven_source(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    measurement_id: Uuid,
) -> Result<Option<DrivenSource>, ApiError> {
    let row: Option<(Option<f64>, String)> = sqlx::query_as(
        "SELECT quantity_real, uom FROM measurements WHERE id = $1 AND deleted_at IS NULL"
    )
    .bind(measurement_id)
    .fetch_optional(&mut **tx)
    .await?;

    let Some((quantity_real, uom)) = row else {
        return Ok(None);
    };

    // quantity_raw is in PDF_PT — pricing it as a real-world quantity would
    // silently inflate the estimate. An uncalibrated measurement must not
    // drive pricing.
    let Some(qty) = quantity_real else {
        return Err(ApiError::unprocessable(
            "UNCALIBRATED_MEASUREMENT",
            format!(
                "measurement {measurement_id} is uncalibrated and cannot drive pricing — calibrate the sheet first"
            ),
        ));
    };

    let version_id: Option<Uuid> = sqlx::query_scalar(
        "SELECT id FROM measurement_versions WHERE measurement_id = $1 ORDER BY version_number DESC LIMIT 1"
    )
    .bind(measurement_id)
    .fetch_optional(&mut **tx)
    .await?;

    let Some(version_id) = version_id else {
        return Err(ApiError::unprocessable(
            "MISSING_VERSION",
            format!("measurement {measurement_id} has no version record"),
        ));
    };

    Ok(Some(DrivenSource { measurement_id, version_id, quantity: qty, uom }))
}

/// Sum validated sources into (total, uom), rejecting mixed units.
fn total_driven_quantity(sources: &[DrivenSource]) -> Result<(f64, String), ApiError> {
    let uom = sources[0].uom.clone();
    let mut total = 0.0;
    for s in sources {
        if !s.uom.eq_ignore_ascii_case(&uom) {
            return Err(ApiError::unprocessable(
                "MIXED_UOMS",
                format!(
                    "source measurements mix units ('{}' vs '{}') and cannot be summed into one line item",
                    uom, s.uom
                ),
            ));
        }
        total += s.quantity;
    }
    Ok((quantity::round_quantity(total, &uom), uom))
}

/// POST /api/estimates/:estimate_id/line-items
/// Supports both manual and driven line items (Spec §11).
///
/// For driven items the quantity and unit are DERIVED from the linked
/// measurements' calibrated quantities — never taken from the client —
/// so the pricing quantity and the staleness baseline cannot disagree
/// with the takeoff.
pub async fn create_line_item(
    State(pool): State<PgPool>,
    Path(estimate_id): Path<Uuid>,
    Json(body): Json<CreateLineItemRequest>,
) -> ApiResult<EstimateLineItem> {
    assert_estimate_in_org(&pool, estimate_id).await?;

    let item_id = Uuid::new_v4();
    let source_type = body.source_type.as_deref().unwrap_or("manual");
    let user_id = SYSTEM_USER_ID;

    let measurement_ids = body.measurement_ids.clone().unwrap_or_default();
    if source_type == "driven" && measurement_ids.is_empty() {
        return Err(ApiError::unprocessable(
            "MISSING_SOURCES",
            "driven line items must reference at least one measurement",
        ));
    }

    // Line item + its measurement source links must land atomically (§11):
    // a driven item without its source records loses traceability.
    let mut tx = pool.begin().await.map_err(ApiError::from)?;

    // For driven items: validate sources and derive the quantity
    let mut sources: Vec<DrivenSource> = Vec::new();
    let (item_quantity, item_unit, quantity_snapshot, snapshot_at) = if source_type == "driven" {
        for measurement_id in &measurement_ids {
            // The measurement must belong to the same project as the estimate —
            // otherwise a client could drive pricing from another project's
            // (or, once auth lands, another tenant's) takeoff.
            let in_project: bool = sqlx::query_scalar(
                r#"
                SELECT EXISTS(
                    SELECT 1 FROM measurements m
                    JOIN takeoff_layers tl ON tl.id = m.layer_id
                    JOIN drawing_sets ds ON ds.id = tl.drawing_set_id
                    JOIN estimates e ON e.project_id = ds.project_id
                    WHERE m.id = $1 AND e.id = $2
                )
                "#,
            )
            .bind(measurement_id)
            .bind(estimate_id)
            .fetch_one(&mut *tx)
            .await?;

            if !in_project {
                return Err(ApiError::unprocessable(
                    "CROSS_REFERENCE",
                    format!("measurement {measurement_id} does not belong to this estimate's project"),
                ));
            }

            let source = load_driven_source(&mut tx, *measurement_id)
                .await?
                .ok_or_else(|| ApiError::not_found("Source measurement"))?;
            sources.push(source);
        }

        let (total, uom) = total_driven_quantity(&sources)?;
        (total, uom, Some(total), Some(chrono::Utc::now()))
    } else {
        (body.quantity, body.unit.clone(), None, None)
    };

    let item = sqlx::query_as::<_, EstimateLineItem>(
        r#"
        INSERT INTO estimate_line_items (
            id, estimate_id, cost_code, description, quantity, unit,
            unit_cost_cents, source_type, quantity_snapshot, snapshot_at,
            is_stale, sort_order, created_by, created_at, updated_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6,
            $7, $8, $9, $10,
            false, 0, $11, NOW(), NOW()
        )
        RETURNING *
        "#,
    )
    .bind(item_id)
    .bind(estimate_id)
    .bind(&body.cost_code)
    .bind(&body.description)
    .bind(item_quantity)
    .bind(&item_unit)
    .bind(body.unit_cost_cents)
    .bind(source_type)
    .bind(quantity_snapshot)
    .bind(snapshot_at)
    .bind(user_id)
    .fetch_one(&mut *tx)
    .await?;

    // Record the per-measurement snapshots (§11 traceability)
    for source in &sources {
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
        .bind(source.measurement_id)
        .bind(source.version_id)
        .bind(source.quantity)
        .bind(&source.uom)
        .bind(user_id)
        .execute(&mut *tx)
        .await?;
    }

    tx.commit().await.map_err(ApiError::from)?;

    Ok(Json(item))
}

/// POST /api/line-items/:item_id/recompute
/// Re-derives a driven line item's quantity from its current source
/// measurements and clears is_stale (Spec §11: "offer recompute").
/// Soft-deleted source measurements simply stop contributing.
pub async fn recompute_line_item(
    State(pool): State<PgPool>,
    Path(item_id): Path<Uuid>,
) -> ApiResult<EstimateLineItem> {
    assert_line_item_in_org(&pool, item_id).await?;

    let user_id = SYSTEM_USER_ID;
    let mut tx = pool.begin().await.map_err(ApiError::from)?;

    let item = sqlx::query_as::<_, EstimateLineItem>(
        "SELECT * FROM estimate_line_items WHERE id = $1 AND deleted_at IS NULL FOR UPDATE"
    )
    .bind(item_id)
    .fetch_optional(&mut *tx)
    .await?
    .ok_or_else(|| ApiError::not_found("Line item"))?;

    if item.source_type != "driven" {
        return Err(ApiError::unprocessable(
            "NOT_DRIVEN",
            "only driven line items can be recomputed from measurements",
        ));
    }

    let measurement_ids: Vec<Uuid> = sqlx::query_scalar(
        "SELECT measurement_id FROM estimate_line_item_sources WHERE line_item_id = $1"
    )
    .bind(item_id)
    .fetch_all(&mut *tx)
    .await?;

    let mut sources: Vec<DrivenSource> = Vec::new();
    for measurement_id in &measurement_ids {
        if let Some(source) = load_driven_source(&mut tx, *measurement_id).await? {
            sources.push(source);
        }
        // None = source measurement soft-deleted: its contribution drops out
    }

    if sources.is_empty() {
        return Err(ApiError::unprocessable(
            "NO_LIVE_SOURCES",
            "all source measurements have been deleted; delete this line item or relink it",
        ));
    }

    let (total, uom) = total_driven_quantity(&sources)?;

    // Refresh per-measurement snapshots to the current versions
    for source in &sources {
        sqlx::query(
            r#"
            UPDATE estimate_line_item_sources SET
                measurement_version_id = $3,
                quantity_snapshot = $4,
                uom_snapshot = $5,
                linked_at = NOW(),
                linked_by = $6
            WHERE line_item_id = $1 AND measurement_id = $2
            "#,
        )
        .bind(item_id)
        .bind(source.measurement_id)
        .bind(source.version_id)
        .bind(source.quantity)
        .bind(&source.uom)
        .bind(user_id)
        .execute(&mut *tx)
        .await?;
    }

    let updated = sqlx::query_as::<_, EstimateLineItem>(
        r#"
        UPDATE estimate_line_items SET
            quantity = $2, unit = $3, quantity_snapshot = $2,
            snapshot_at = NOW(), is_stale = false, updated_at = NOW()
        WHERE id = $1
        RETURNING *
        "#,
    )
    .bind(item_id)
    .bind(total)
    .bind(&uom)
    .fetch_one(&mut *tx)
    .await?;

    tx.commit().await.map_err(ApiError::from)?;

    Ok(Json(updated))
}

/// PUT /api/line-items/:item_id
pub async fn update_line_item(
    State(pool): State<PgPool>,
    Path(item_id): Path<Uuid>,
    Json(body): Json<UpdateLineItemRequest>,
) -> ApiResult<EstimateLineItem> {
    assert_line_item_in_org(&pool, item_id).await?;

    // A driven item's quantity/unit are derived from its measurements —
    // manual overrides would silently desync pricing from the takeoff.
    if body.quantity.is_some() || body.unit.is_some() {
        let source_type: Option<String> = sqlx::query_scalar(
            "SELECT source_type FROM estimate_line_items WHERE id = $1 AND deleted_at IS NULL"
        )
        .bind(item_id)
        .fetch_optional(&pool)
        .await?;

        if source_type.as_deref() == Some("driven") {
            return Err(ApiError::unprocessable(
                "DRIVEN_QUANTITY_IMMUTABLE",
                "quantity and unit of a driven line item come from its measurements — use recompute instead",
            ));
        }
    }

    let item = sqlx::query_as::<_, EstimateLineItem>(
        r#"
        UPDATE estimate_line_items SET
            cost_code = COALESCE($2, cost_code),
            description = COALESCE($3, description),
            quantity = COALESCE($4, quantity),
            unit = COALESCE($5, unit),
            unit_cost_cents = COALESCE($6, unit_cost_cents),
            updated_at = NOW()
        WHERE id = $1 AND deleted_at IS NULL
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

/// DELETE /api/line-items/:item_id (soft delete — line items are financial
/// records; their estimate_line_item_sources traceability rows survive)
pub async fn delete_line_item(
    State(pool): State<PgPool>,
    Path(item_id): Path<Uuid>,
) -> ApiResult<serde_json::Value> {
    assert_line_item_in_org(&pool, item_id).await?;

    let result = sqlx::query(
        "UPDATE estimate_line_items SET deleted_at = NOW(), updated_at = NOW() WHERE id = $1 AND deleted_at IS NULL"
    )
    .bind(item_id)
    .execute(&pool)
    .await?;

    if result.rows_affected() == 0 {
        return Err(ApiError::not_found("Line item"));
    }

    Ok(Json(serde_json::json!({ "deleted": true })))
}
