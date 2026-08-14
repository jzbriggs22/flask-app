use axum::{
    extract::{Path, State},
    Json,
};
use sqlx::PgPool;
use uuid::Uuid;

use crate::error::{ApiError, ApiResult};
use crate::models::{
    DrawingSet, DrawingSheetRevision, TakeoffLayer, Measurement, MeasurementVersion,
    MeasurementType, ScaleCalibration, TakeoffEvent,
    CreateDrawingSetRequest, CreateLayerRequest, CreateMeasurementRequest,
    CreateCalibrationRequest, UpdateMeasurementRequest, WorldPoint,
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

async fn assert_drawing_set_in_org(pool: &PgPool, drawing_set_id: Uuid) -> Result<(), ApiError> {
    let exists: bool = sqlx::query_scalar(
        r#"
        SELECT EXISTS(
            SELECT 1 FROM drawing_sets ds
            JOIN projects p ON p.id = ds.project_id
            WHERE ds.id = $1 AND p.organization_id = $2 AND p.deleted_at IS NULL
        )
        "#,
    )
    .bind(drawing_set_id)
    .bind(SYSTEM_ORG_ID)
    .fetch_one(pool)
    .await?;

    if exists { Ok(()) } else { Err(ApiError::not_found("Drawing set")) }
}

async fn assert_layer_in_org(pool: &PgPool, layer_id: Uuid) -> Result<(), ApiError> {
    let exists: bool = sqlx::query_scalar(
        r#"
        SELECT EXISTS(
            SELECT 1 FROM takeoff_layers tl
            JOIN drawing_sets ds ON ds.id = tl.drawing_set_id
            JOIN projects p ON p.id = ds.project_id
            WHERE tl.id = $1 AND p.organization_id = $2 AND p.deleted_at IS NULL
        )
        "#,
    )
    .bind(layer_id)
    .bind(SYSTEM_ORG_ID)
    .fetch_one(pool)
    .await?;

    if exists { Ok(()) } else { Err(ApiError::not_found("Layer")) }
}

async fn assert_measurement_in_org(pool: &PgPool, measurement_id: Uuid) -> Result<(), ApiError> {
    let exists: bool = sqlx::query_scalar(
        r#"
        SELECT EXISTS(
            SELECT 1 FROM measurements m
            JOIN takeoff_layers tl ON tl.id = m.layer_id
            JOIN drawing_sets ds ON ds.id = tl.drawing_set_id
            JOIN projects p ON p.id = ds.project_id
            WHERE m.id = $1 AND p.organization_id = $2 AND p.deleted_at IS NULL
        )
        "#,
    )
    .bind(measurement_id)
    .bind(SYSTEM_ORG_ID)
    .fetch_one(pool)
    .await?;

    if exists { Ok(()) } else { Err(ApiError::not_found("Measurement")) }
}

// ============================================================
// Drawing Sets
// ============================================================

/// GET /api/projects/:project_id/drawing-sets
pub async fn list_drawing_sets(
    State(pool): State<PgPool>,
    Path(project_id): Path<Uuid>,
) -> ApiResult<Vec<DrawingSet>> {
    let sets = sqlx::query_as::<_, DrawingSet>(
        r#"
        SELECT ds.* FROM drawing_sets ds
        JOIN projects p ON p.id = ds.project_id
        WHERE ds.project_id = $1 AND p.organization_id = $2 AND p.deleted_at IS NULL
        ORDER BY ds.created_at DESC
        "#,
    )
    .bind(project_id)
    .bind(SYSTEM_ORG_ID)
    .fetch_all(&pool)
    .await?;

    Ok(Json(sets))
}

/// POST /api/projects/:project_id/drawing-sets
pub async fn upload_drawing_set(
    State(pool): State<PgPool>,
    Path(project_id): Path<Uuid>,
    Json(body): Json<CreateDrawingSetRequest>,
) -> ApiResult<DrawingSet> {
    assert_project_in_org(&pool, project_id).await?;

    // TODO: Handle multipart file upload to S3/MinIO
    let set = sqlx::query_as::<_, DrawingSet>(
        r#"
        INSERT INTO drawing_sets (id, project_id, name, revision, file_url, file_size, sheet_count, created_by, created_at, updated_at)
        VALUES ($1, $2, $3, 1, '', 0, 0, $4, NOW(), NOW())
        RETURNING *
        "#,
    )
    .bind(Uuid::new_v4())
    .bind(project_id)
    .bind(&body.name)
    .bind(SYSTEM_USER_ID)
    .fetch_one(&pool)
    .await?;

    Ok(Json(set))
}

/// GET /api/projects/:project_id/drawing-sets/:id
pub async fn get_drawing_set(
    State(pool): State<PgPool>,
    Path((project_id, id)): Path<(Uuid, Uuid)>,
) -> ApiResult<DrawingSet> {
    let set = sqlx::query_as::<_, DrawingSet>(
        r#"
        SELECT ds.* FROM drawing_sets ds
        JOIN projects p ON p.id = ds.project_id
        WHERE ds.id = $1 AND ds.project_id = $2 AND p.organization_id = $3 AND p.deleted_at IS NULL
        "#,
    )
    .bind(id)
    .bind(project_id)
    .bind(SYSTEM_ORG_ID)
    .fetch_optional(&pool)
    .await?
    .ok_or_else(|| ApiError::not_found("Drawing set"))?;

    Ok(Json(set))
}

// ============================================================
// Sheet Revisions (Spec §12)
// ============================================================

/// GET /api/sheets/:sheet_id/revisions
pub async fn list_sheet_revisions(
    State(pool): State<PgPool>,
    Path(sheet_id): Path<Uuid>,
) -> ApiResult<Vec<DrawingSheetRevision>> {
    let revisions = sqlx::query_as::<_, DrawingSheetRevision>(
        r#"
        SELECT r.* FROM drawing_sheet_revisions r
        JOIN drawing_sets ds ON ds.id = r.drawing_set_id
        JOIN projects p ON p.id = ds.project_id
        WHERE r.sheet_id = $1 AND p.organization_id = $2 AND p.deleted_at IS NULL
        ORDER BY r.revision_number DESC
        "#,
    )
    .bind(sheet_id)
    .bind(SYSTEM_ORG_ID)
    .fetch_all(&pool)
    .await?;

    Ok(Json(revisions))
}

// ============================================================
// Calibration (Spec §5)
// ============================================================

/// GET /api/sheet-revisions/:revision_id/calibration
/// A missing calibration is a legitimate state (uncalibrated sheet, §5),
/// so this returns 200 with null rather than 404.
pub async fn get_calibration(
    State(pool): State<PgPool>,
    Path(revision_id): Path<Uuid>,
) -> ApiResult<Option<ScaleCalibration>> {
    let cal = sqlx::query_as::<_, ScaleCalibration>(
        r#"
        SELECT c.* FROM scale_calibrations c
        JOIN drawing_sheet_revisions r ON r.id = c.sheet_revision_id
        JOIN drawing_sets ds ON ds.id = r.drawing_set_id
        JOIN projects p ON p.id = ds.project_id
        WHERE c.sheet_revision_id = $1 AND p.organization_id = $2
        ORDER BY c.created_at DESC LIMIT 1
        "#,
    )
    .bind(revision_id)
    .bind(SYSTEM_ORG_ID)
    .fetch_optional(&pool)
    .await?;

    Ok(Json(cal))
}

/// POST /api/sheet-revisions/:revision_id/calibration
///
/// Recalibration is auditable (Spec §9): a CALIBRATION_SET event is always
/// emitted; when a previous calibration existed, a CALIBRATION_INVALIDATED
/// event is emitted for it and every driven line item sourced from
/// measurements on this revision is marked stale — their quantities were
/// derived under the superseded scale (Spec §11, §15).
pub async fn set_calibration(
    State(pool): State<PgPool>,
    Path(revision_id): Path<Uuid>,
    Json(body): Json<CreateCalibrationRequest>,
) -> ApiResult<ScaleCalibration> {
    if body.real_distance <= 0.0 {
        return Err(ApiError::unprocessable(
            "INVALID_CALIBRATION",
            "real_distance must be positive",
        ));
    }

    // Compute world_distance_pt and scale_factor from the two points
    let dx = body.point2_x - body.point1_x;
    let dy = body.point2_y - body.point1_y;
    let world_distance_pt = (dx * dx + dy * dy).sqrt();
    if world_distance_pt <= 0.0 {
        return Err(ApiError::unprocessable(
            "INVALID_CALIBRATION",
            "calibration points must be distinct",
        ));
    }
    let scale_factor = body.real_distance / world_distance_pt;

    // Get the revision (org-scoped)
    let revision = sqlx::query_as::<_, DrawingSheetRevision>(
        r#"
        SELECT r.* FROM drawing_sheet_revisions r
        JOIN drawing_sets ds ON ds.id = r.drawing_set_id
        JOIN projects p ON p.id = ds.project_id
        WHERE r.id = $1 AND p.organization_id = $2 AND p.deleted_at IS NULL
        "#,
    )
    .bind(revision_id)
    .bind(SYSTEM_ORG_ID)
    .fetch_optional(&pool)
    .await?
    .ok_or_else(|| ApiError::not_found("Sheet revision"))?;

    let mut tx = pool.begin().await.map_err(ApiError::from)?;

    // The calibration being superseded, if any
    let previous_calibration_id: Option<Uuid> = sqlx::query_scalar(
        "SELECT id FROM scale_calibrations WHERE sheet_revision_id = $1 ORDER BY created_at DESC LIMIT 1"
    )
    .bind(revision_id)
    .fetch_optional(&mut *tx)
    .await?;

    let cal = sqlx::query_as::<_, ScaleCalibration>(
        r#"
        INSERT INTO scale_calibrations (
            id, sheet_id, sheet_revision_id, unit_system, display_unit,
            point1_x, point1_y, point2_x, point2_y,
            world_distance_pt, real_distance, scale_factor,
            method, confidence, unit, created_by, created_at
        ) VALUES (
            $1, $2, $3, $4, $5,
            $6, $7, $8, $9,
            $10, $11, $12,
            $13, $14, $15, $16, NOW()
        )
        RETURNING *
        "#,
    )
    .bind(Uuid::new_v4())
    .bind(revision.sheet_id)
    .bind(revision_id)
    .bind(&body.unit_system)
    .bind(&body.display_unit)
    .bind(body.point1_x)
    .bind(body.point1_y)
    .bind(body.point2_x)
    .bind(body.point2_y)
    .bind(world_distance_pt)
    .bind(body.real_distance)
    .bind(scale_factor)
    .bind(body.method.as_deref().unwrap_or("two-point"))
    .bind(body.confidence.as_deref().unwrap_or("exact"))
    .bind(&body.display_unit)
    .bind(SYSTEM_USER_ID)
    .fetch_one(&mut *tx)
    .await?;

    // CALIBRATION_SET audit event (Spec §9)
    sqlx::query(
        r#"
        INSERT INTO takeoff_events (
            id, project_id, sheet_revision_id, event_type, calibration_id,
            payload, created_by, created_at
        ) VALUES (
            $1,
            (SELECT project_id FROM drawing_sets WHERE id = $2),
            $3, 'CALIBRATION_SET', $4, $5, $6, NOW()
        )
        "#,
    )
    .bind(Uuid::new_v4())
    .bind(revision.drawing_set_id)
    .bind(revision_id)
    .bind(cal.id)
    .bind(sqlx::types::Json(&serde_json::json!({
        "scale_factor": scale_factor,
        "display_unit": body.display_unit,
        "real_distance": body.real_distance,
        "supersedes": previous_calibration_id,
    })))
    .bind(SYSTEM_USER_ID)
    .execute(&mut *tx)
    .await?;

    if let Some(prev_id) = previous_calibration_id {
        // CALIBRATION_INVALIDATED for the superseded calibration (Spec §15)
        sqlx::query(
            r#"
            INSERT INTO takeoff_events (
                id, project_id, sheet_revision_id, event_type, calibration_id,
                payload, created_by, created_at
            ) VALUES (
                $1,
                (SELECT project_id FROM drawing_sets WHERE id = $2),
                $3, 'CALIBRATION_INVALIDATED', $4, $5, $6, NOW()
            )
            "#,
        )
        .bind(Uuid::new_v4())
        .bind(revision.drawing_set_id)
        .bind(revision_id)
        .bind(prev_id)
        .bind(sqlx::types::Json(&serde_json::json!({
            "superseded_by": cal.id,
        })))
        .bind(SYSTEM_USER_ID)
        .execute(&mut *tx)
        .await?;

        // Quantities derived under the old scale are now suspect: flag every
        // driven line item sourced from a measurement on this revision.
        // Measurements themselves are NOT silently recomputed — that would
        // violate the append-only rule (§9); users re-measure or update them,
        // which creates new versions under the new calibration.
        sqlx::query(
            r#"
            UPDATE estimate_line_items SET is_stale = true, updated_at = NOW()
            WHERE deleted_at IS NULL AND source_type = 'driven' AND id IN (
                SELECT s.line_item_id
                FROM estimate_line_item_sources s
                JOIN measurements m ON m.id = s.measurement_id
                WHERE m.sheet_revision_id = $1
            )
            "#,
        )
        .bind(revision_id)
        .execute(&mut *tx)
        .await?;
    }

    tx.commit().await.map_err(ApiError::from)?;

    Ok(Json(cal))
}

// ============================================================
// Layers (Spec §8)
// ============================================================

/// GET /api/drawing-sets/:drawing_set_id/layers
pub async fn list_layers(
    State(pool): State<PgPool>,
    Path(drawing_set_id): Path<Uuid>,
) -> ApiResult<Vec<TakeoffLayer>> {
    let layers = sqlx::query_as::<_, TakeoffLayer>(
        r#"
        SELECT tl.* FROM takeoff_layers tl
        JOIN drawing_sets ds ON ds.id = tl.drawing_set_id
        JOIN projects p ON p.id = ds.project_id
        WHERE tl.drawing_set_id = $1 AND p.organization_id = $2 AND p.deleted_at IS NULL
        ORDER BY tl.sort_order
        "#,
    )
    .bind(drawing_set_id)
    .bind(SYSTEM_ORG_ID)
    .fetch_all(&pool)
    .await?;

    Ok(Json(layers))
}

/// POST /api/drawing-sets/:drawing_set_id/layers
pub async fn create_layer(
    State(pool): State<PgPool>,
    Path(drawing_set_id): Path<Uuid>,
    Json(body): Json<CreateLayerRequest>,
) -> ApiResult<TakeoffLayer> {
    assert_drawing_set_in_org(&pool, drawing_set_id).await?;

    let layer = sqlx::query_as::<_, TakeoffLayer>(
        r#"
        INSERT INTO takeoff_layers (id, drawing_set_id, name, color, cost_code, visible, sort_order, created_by, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, true, 0, $6, NOW(), NOW())
        RETURNING *
        "#,
    )
    .bind(Uuid::new_v4())
    .bind(drawing_set_id)
    .bind(&body.name)
    .bind(&body.color)
    .bind(body.cost_code.as_deref().unwrap_or(""))
    .bind(SYSTEM_USER_ID)
    .fetch_one(&pool)
    .await?;

    Ok(Json(layer))
}

// ============================================================
// Measurements (Spec §6, §9)
// ============================================================

/// GET /api/layers/:layer_id/measurements
/// Returns only non-deleted measurements.
pub async fn list_measurements(
    State(pool): State<PgPool>,
    Path(layer_id): Path<Uuid>,
) -> ApiResult<Vec<Measurement>> {
    let measurements = sqlx::query_as::<_, Measurement>(
        r#"
        SELECT m.* FROM measurements m
        JOIN takeoff_layers tl ON tl.id = m.layer_id
        JOIN drawing_sets ds ON ds.id = tl.drawing_set_id
        JOIN projects p ON p.id = ds.project_id
        WHERE m.layer_id = $1 AND m.deleted_at IS NULL
          AND p.organization_id = $2 AND p.deleted_at IS NULL
        ORDER BY m.created_at
        "#,
    )
    .bind(layer_id)
    .bind(SYSTEM_ORG_ID)
    .fetch_all(&pool)
    .await?;

    Ok(Json(measurements))
}

/// POST /api/layers/:layer_id/measurements
/// Creates a measurement + initial version + MEASUREMENT_CREATED event (Spec §9),
/// atomically. Validates that the referenced sheet revision belongs to the
/// layer's drawing set and that the calibration belongs to that revision.
pub async fn create_measurement(
    State(pool): State<PgPool>,
    Path(layer_id): Path<Uuid>,
    Json(body): Json<CreateMeasurementRequest>,
) -> ApiResult<Measurement> {
    assert_layer_in_org(&pool, layer_id).await?;

    // Cross-entity validation: the revision must belong to this layer's
    // drawing set, and sheet_id must be the revision's sheet. Without this
    // a client could attach geometry (and a foreign calibration's scale)
    // from another sheet, project, or tenant.
    let revision_sheet_id: Option<Uuid> = sqlx::query_scalar(
        r#"
        SELECT r.sheet_id FROM drawing_sheet_revisions r
        JOIN takeoff_layers tl ON tl.drawing_set_id = r.drawing_set_id
        WHERE r.id = $1 AND tl.id = $2
        "#,
    )
    .bind(body.sheet_revision_id)
    .bind(layer_id)
    .fetch_optional(&pool)
    .await?;

    let Some(revision_sheet_id) = revision_sheet_id else {
        return Err(ApiError::unprocessable(
            "CROSS_REFERENCE",
            "sheet revision does not belong to this layer's drawing set",
        ));
    };
    if revision_sheet_id != body.sheet_id {
        return Err(ApiError::unprocessable(
            "CROSS_REFERENCE",
            "sheet_id does not match the sheet revision",
        ));
    }

    // Load the calibration, bound to this exact revision (Spec §5)
    let calibration = load_calibration(&pool, body.calibration_id, body.sheet_revision_id).await?;

    // The uom must agree with the measurement type and calibration (Spec §5, §10)
    validate_uom(&body.measurement_type, calibration.as_ref(), &body.uom)?;

    // Compute quantities server-side from WORLD geometry (Spec §6)
    let quantity_raw = compute_quantity_raw(&body.measurement_type, &body.points);
    let quantity_real =
        compute_quantity_real(&body.measurement_type, quantity_raw, calibration.as_ref(), &body.uom);

    let measurement_id = Uuid::new_v4();
    let version_id = Uuid::new_v4();
    let user_id = SYSTEM_USER_ID;

    // Measurement + version + event must land atomically (Spec §9):
    // a measurement without its version record or audit event would
    // silently diverge the materialized state from history.
    let mut tx = pool.begin().await.map_err(ApiError::from)?;

    // Insert measurement (materialized state)
    let measurement = sqlx::query_as::<_, Measurement>(
        r#"
        INSERT INTO measurements (
            id, layer_id, sheet_id, sheet_revision_id, measurement_type,
            points, value, unit, cost_code, label,
            calibration_id, quantity_raw, quantity_real, uom, version,
            created_by, created_at
        ) VALUES (
            $1, $2, $3, $4, $5,
            $6, $7, $8, $9, $10,
            $11, $12, $13, $14, 1,
            $15, NOW()
        )
        RETURNING *
        "#,
    )
    .bind(measurement_id)
    .bind(layer_id)
    .bind(body.sheet_id)
    .bind(body.sheet_revision_id)
    .bind(&body.measurement_type)
    .bind(sqlx::types::Json(&body.points))
    .bind(quantity_raw)
    .bind(&body.uom)
    .bind(body.cost_code.as_deref().unwrap_or(""))
    .bind(body.label.as_deref())
    .bind(body.calibration_id)
    .bind(quantity_raw)
    .bind(quantity_real)
    .bind(&body.uom)
    .bind(user_id)
    .fetch_one(&mut *tx)
    .await?;

    // Insert initial version (Spec §9: append-only)
    let metadata = serde_json::json!({
        "label": body.label,
        "cost_code": body.cost_code,
    });
    sqlx::query(
        r#"
        INSERT INTO measurement_versions (
            id, measurement_id, version_number, geometry_world,
            calibration_id, quantity_raw, quantity_real, uom,
            metadata, created_by, created_at
        ) VALUES ($1, $2, 1, $3, $4, $5, $6, $7, $8, $9, NOW())
        "#,
    )
    .bind(version_id)
    .bind(measurement_id)
    .bind(sqlx::types::Json(&body.points))
    .bind(body.calibration_id)
    .bind(quantity_raw)
    .bind(quantity_real)
    .bind(&body.uom)
    .bind(sqlx::types::Json(&metadata))
    .bind(user_id)
    .execute(&mut *tx)
    .await?;

    // Insert event (Spec §9: append-only audit log)
    sqlx::query(
        r#"
        INSERT INTO takeoff_events (
            id, project_id, sheet_revision_id, event_type,
            measurement_id, measurement_version_id, calibration_id, layer_id,
            payload, created_by, created_at
        ) VALUES (
            $1, (SELECT project_id FROM drawing_sets WHERE id = (SELECT drawing_set_id FROM takeoff_layers WHERE id = $2)),
            $3, 'MEASUREMENT_CREATED',
            $4, $5, $6, $2,
            $7, $8, NOW()
        )
        "#,
    )
    .bind(Uuid::new_v4())
    .bind(layer_id)
    .bind(body.sheet_revision_id)
    .bind(measurement_id)
    .bind(version_id)
    .bind(body.calibration_id)
    .bind(sqlx::types::Json(&serde_json::json!({
        "type": format!("{:?}", body.measurement_type),
        "quantity_raw": quantity_raw,
        "uom": body.uom,
    })))
    .bind(user_id)
    .execute(&mut *tx)
    .await?;

    tx.commit().await.map_err(ApiError::from)?;

    Ok(Json(measurement))
}

/// PUT /api/measurements/:id — update creates a new version (Spec §9).
pub async fn update_measurement(
    State(pool): State<PgPool>,
    Path(measurement_id): Path<Uuid>,
    Json(body): Json<UpdateMeasurementRequest>,
) -> ApiResult<Measurement> {
    assert_measurement_in_org(&pool, measurement_id).await?;

    let user_id = SYSTEM_USER_ID;

    // The read-modify-write must be atomic (Spec §9). FOR UPDATE serializes
    // concurrent edits so two users can't both claim the same version_number;
    // the loser blocks, then re-reads the winner's committed version.
    let mut tx = pool.begin().await.map_err(ApiError::from)?;

    let existing = sqlx::query_as::<_, Measurement>(
        "SELECT * FROM measurements WHERE id = $1 AND deleted_at IS NULL FOR UPDATE"
    )
    .bind(measurement_id)
    .fetch_optional(&mut *tx)
    .await?
    .ok_or_else(|| ApiError::not_found("Measurement"))?;

    let new_version_number = existing.version + 1;
    let version_id = Uuid::new_v4();

    // Determine new geometry
    let new_points = body.points.as_ref().unwrap_or(&existing.points.0);
    let new_uom = body.uom.as_deref().unwrap_or(&existing.uom);
    let quantity_raw = compute_quantity_raw(&existing.measurement_type, new_points);

    // Load calibration on the SAME connection as the transaction — acquiring
    // a second pool connection while holding a FOR UPDATE lock risks
    // pool-exhaustion stalls under concurrent updates.
    let calibration = match existing.calibration_id {
        Some(cal_id) => sqlx::query_as::<_, CalibrationInfo>(
            "SELECT scale_factor, display_unit FROM scale_calibrations WHERE id = $1",
        )
        .bind(cal_id)
        .fetch_optional(&mut *tx)
        .await?,
        None => None,
    };

    // The (possibly changed) uom must still agree with type + calibration
    validate_uom(&existing.measurement_type, calibration.as_ref(), new_uom)?;

    // Recompute the calibrated quantity for the NEW geometry — a stale
    // quantity_real surviving a geometry edit is silent financial corruption.
    let quantity_real =
        compute_quantity_real(&existing.measurement_type, quantity_raw, calibration.as_ref(), new_uom);

    // Get previous version id for supersedes link
    let prev_version_id: Option<Uuid> = sqlx::query_scalar(
        "SELECT id FROM measurement_versions WHERE measurement_id = $1 ORDER BY version_number DESC LIMIT 1"
    )
    .bind(measurement_id)
    .fetch_optional(&mut *tx)
    .await?;

    // Update materialized state (both raw and recomputed real quantities)
    let updated = sqlx::query_as::<_, Measurement>(
        r#"
        UPDATE measurements SET
            points = $2, value = $3, quantity_raw = $3, quantity_real = $8,
            cost_code = COALESCE($4, cost_code),
            label = COALESCE($5, label),
            uom = COALESCE($6, uom),
            version = $7
        WHERE id = $1 AND deleted_at IS NULL
        RETURNING *
        "#,
    )
    .bind(measurement_id)
    .bind(sqlx::types::Json(new_points))
    .bind(quantity_raw)
    .bind(body.cost_code.as_deref())
    .bind(body.label.as_deref())
    .bind(body.uom.as_deref())
    .bind(new_version_number)
    .bind(quantity_real)
    .fetch_optional(&mut *tx)
    .await?
    .ok_or_else(|| ApiError::not_found("Measurement"))?;

    // Insert new version (Spec §9: append-only, prior versions immutable)
    sqlx::query(
        r#"
        INSERT INTO measurement_versions (
            id, measurement_id, version_number, geometry_world,
            calibration_id, quantity_raw, quantity_real, uom,
            metadata, created_by, created_at, supersedes_version_id
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW(), $11)
        "#,
    )
    .bind(version_id)
    .bind(measurement_id)
    .bind(new_version_number)
    .bind(sqlx::types::Json(new_points))
    .bind(existing.calibration_id)
    .bind(quantity_raw)
    .bind(quantity_real)
    .bind(new_uom)
    .bind(sqlx::types::Json(&serde_json::json!({
        "label": body.label.as_deref().unwrap_or(existing.label.as_deref().unwrap_or("")),
        "cost_code": body.cost_code.as_deref().unwrap_or(&existing.cost_code),
    })))
    .bind(user_id)
    .bind(prev_version_id)
    .execute(&mut *tx)
    .await?;

    // Insert MEASUREMENT_UPDATED event
    sqlx::query(
        r#"
        INSERT INTO takeoff_events (
            id, project_id, sheet_revision_id, event_type,
            measurement_id, measurement_version_id, layer_id,
            payload, created_by, created_at
        ) VALUES (
            $1,
            (SELECT project_id FROM drawing_sets WHERE id = (SELECT drawing_set_id FROM takeoff_layers WHERE id = $2)),
            $3, 'MEASUREMENT_UPDATED',
            $4, $5, $2,
            $6, $7, NOW()
        )
        "#,
    )
    .bind(Uuid::new_v4())
    .bind(existing.layer_id)
    .bind(existing.sheet_revision_id)
    .bind(measurement_id)
    .bind(version_id)
    .bind(sqlx::types::Json(&serde_json::json!({
        "version": new_version_number,
        "changes": {
            "points_changed": body.points.is_some(),
            "cost_code_changed": body.cost_code.is_some(),
            "label_changed": body.label.is_some(),
        },
    })))
    .bind(user_id)
    .execute(&mut *tx)
    .await?;

    // Staleness propagation (Spec §11): if the quantity this measurement
    // contributes changed, every driven line item sourced from it is now
    // pricing an outdated snapshot.
    if updated.quantity_real != existing.quantity_real || updated.uom != existing.uom {
        mark_dependent_line_items_stale(&mut tx, measurement_id).await?;
    }

    tx.commit().await.map_err(ApiError::from)?;

    Ok(Json(updated))
}

/// DELETE /api/measurements/:id — soft delete (Spec §9).
pub async fn soft_delete_measurement(
    State(pool): State<PgPool>,
    Path(measurement_id): Path<Uuid>,
) -> ApiResult<serde_json::Value> {
    assert_measurement_in_org(&pool, measurement_id).await?;

    // Delete + audit event must land atomically (Spec §9)
    let mut tx = pool.begin().await.map_err(ApiError::from)?;

    let result = sqlx::query(
        "UPDATE measurements SET deleted_at = NOW() WHERE id = $1 AND deleted_at IS NULL"
    )
    .bind(measurement_id)
    .execute(&mut *tx)
    .await?;

    if result.rows_affected() == 0 {
        return Err(ApiError::not_found("Measurement"));
    }

    // Insert MEASUREMENT_DELETED event
    sqlx::query(
        r#"
        INSERT INTO takeoff_events (
            id, project_id, sheet_revision_id, event_type,
            measurement_id, payload, created_by, created_at
        ) VALUES (
            $1,
            (SELECT ds.project_id FROM drawing_sets ds
             JOIN takeoff_layers tl ON tl.drawing_set_id = ds.id
             JOIN measurements m ON m.layer_id = tl.id
             WHERE m.id = $2 LIMIT 1),
            (SELECT sheet_revision_id FROM measurements WHERE id = $2),
            'MEASUREMENT_DELETED',
            $2, '{}', $3, NOW()
        )
        "#,
    )
    .bind(Uuid::new_v4())
    .bind(measurement_id)
    .bind(SYSTEM_USER_ID)
    .execute(&mut *tx)
    .await?;

    // A deleted source always leaves its driven line items out of date (§11)
    mark_dependent_line_items_stale(&mut tx, measurement_id).await?;

    tx.commit().await.map_err(ApiError::from)?;

    Ok(Json(serde_json::json!({ "deleted": true })))
}

/// GET /api/measurements/:id/versions — version history (Spec §9).
pub async fn list_measurement_versions(
    State(pool): State<PgPool>,
    Path(measurement_id): Path<Uuid>,
) -> ApiResult<Vec<MeasurementVersion>> {
    assert_measurement_in_org(&pool, measurement_id).await?;

    let versions = sqlx::query_as::<_, MeasurementVersion>(
        "SELECT * FROM measurement_versions WHERE measurement_id = $1 ORDER BY version_number"
    )
    .bind(measurement_id)
    .fetch_all(&pool)
    .await?;

    Ok(Json(versions))
}

// ============================================================
// Events (Spec §9)
// ============================================================

/// GET /api/projects/:project_id/takeoff-events
pub async fn list_events(
    State(pool): State<PgPool>,
    Path(project_id): Path<Uuid>,
) -> ApiResult<Vec<TakeoffEvent>> {
    assert_project_in_org(&pool, project_id).await?;

    let events = sqlx::query_as::<_, TakeoffEvent>(
        "SELECT * FROM takeoff_events WHERE project_id = $1 ORDER BY created_at DESC LIMIT 100"
    )
    .bind(project_id)
    .fetch_all(&pool)
    .await?;

    Ok(Json(events))
}

// ============================================================
// Calibration + quantity helpers (Spec §5, §6, §10)
// ============================================================

/// The subset of a calibration needed to derive and validate quantities.
#[derive(Debug, sqlx::FromRow)]
struct CalibrationInfo {
    scale_factor: f64,
    display_unit: String,
}

/// Load a calibration by id, requiring it to belong to the given sheet
/// revision (Spec §5: calibrations are bound to a specific revision).
/// Returns Ok(None) when no calibration id was supplied (uncalibrated).
async fn load_calibration(
    pool: &PgPool,
    calibration_id: Option<Uuid>,
    sheet_revision_id: Uuid,
) -> Result<Option<CalibrationInfo>, ApiError> {
    let Some(cal_id) = calibration_id else {
        return Ok(None);
    };

    let cal = sqlx::query_as::<_, CalibrationInfo>(
        "SELECT scale_factor, display_unit FROM scale_calibrations WHERE id = $1 AND sheet_revision_id = $2",
    )
    .bind(cal_id)
    .bind(sheet_revision_id)
    .fetch_optional(pool)
    .await?;

    match cal {
        Some(c) => Ok(Some(c)),
        None => Err(ApiError::unprocessable(
            "INVALID_CALIBRATION",
            "calibration does not belong to this sheet revision",
        )),
    }
}

/// Reject a uom that disagrees with the measurement type and calibration.
/// A quantity derived in feet but labeled meters is silent financial
/// corruption (Spec §5, §10).
fn validate_uom(
    measurement_type: &MeasurementType,
    calibration: Option<&CalibrationInfo>,
    uom: &str,
) -> Result<(), ApiError> {
    let expected = quantity::expected_uom(
        measurement_type,
        calibration.map(|c| c.display_unit.as_str()),
    );

    if let Some(expected) = expected {
        if !uom.eq_ignore_ascii_case(expected) {
            return Err(ApiError::unprocessable(
                "UOM_MISMATCH",
                format!(
                    "uom '{uom}' does not match '{expected}' expected for this measurement type and sheet calibration"
                ),
            ));
        }
    }
    Ok(())
}

/// Compute the calibrated real-world quantity (Spec §6), rounded per §10.
/// Counts are unit-independent and never require calibration. Linear scales
/// by scale_factor; area by scale_factor². Returns None when uncalibrated (§5).
fn compute_quantity_real(
    measurement_type: &MeasurementType,
    quantity_raw: f64,
    calibration: Option<&CalibrationInfo>,
    uom: &str,
) -> Option<f64> {
    match measurement_type {
        MeasurementType::Count => Some(quantity_raw),
        // Volume deferred in MVP (Spec §6 placeholder)
        MeasurementType::Volume => None,
        _ => {
            let cal = calibration?;
            if cal.scale_factor <= 0.0 {
                return None;
            }
            let real = match measurement_type {
                MeasurementType::Area => quantity_raw * cal.scale_factor * cal.scale_factor,
                _ => quantity_raw * cal.scale_factor,
            };
            Some(quantity::round_quantity(real, uom))
        }
    }
}

/// Mark every non-deleted driven line item sourced from this measurement as
/// stale (Spec §11). Runs inside the caller's transaction.
async fn mark_dependent_line_items_stale(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    measurement_id: Uuid,
) -> Result<(), ApiError> {
    sqlx::query(
        r#"
        UPDATE estimate_line_items SET is_stale = true, updated_at = NOW()
        WHERE deleted_at IS NULL AND source_type = 'driven' AND id IN (
            SELECT line_item_id FROM estimate_line_item_sources WHERE measurement_id = $1
        )
        "#,
    )
    .bind(measurement_id)
    .execute(&mut **tx)
    .await?;
    Ok(())
}

fn compute_quantity_raw(
    measurement_type: &MeasurementType,
    points: &[WorldPoint],
) -> f64 {
    match measurement_type {
        MeasurementType::Linear => {
            if points.len() < 2 { return 0.0; }
            let mut total = 0.0;
            for i in 1..points.len() {
                let dx = points[i].x - points[i - 1].x;
                let dy = points[i].y - points[i - 1].y;
                total += (dx * dx + dy * dy).sqrt();
            }
            total
        }
        MeasurementType::Area => {
            if points.len() < 3 { return 0.0; }
            let mut area = 0.0;
            let n = points.len();
            for i in 0..n {
                let j = (i + 1) % n;
                area += points[i].x * points[j].y;
                area -= points[j].x * points[i].y;
            }
            area.abs() / 2.0
        }
        MeasurementType::Count => points.len() as f64,
        MeasurementType::Volume => 0.0,
    }
}
