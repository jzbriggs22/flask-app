use axum::{
    extract::{Path, State},
    Json,
};
use sqlx::PgPool;
use uuid::Uuid;

use crate::models::{
    DrawingSet, DrawingSheetRevision, TakeoffLayer, Measurement, MeasurementVersion,
    ScaleCalibration, TakeoffEvent, TakeoffEventType,
    CreateDrawingSetRequest, CreateLayerRequest, CreateMeasurementRequest,
    CreateCalibrationRequest, UpdateMeasurementRequest, WorldPoint,
};

// ============================================================
// Drawing Sets
// ============================================================

/// GET /api/projects/:project_id/drawing-sets
pub async fn list_drawing_sets(
    State(pool): State<PgPool>,
    Path(project_id): Path<Uuid>,
) -> Json<Vec<DrawingSet>> {
    let sets = sqlx::query_as::<_, DrawingSet>(
        "SELECT * FROM drawing_sets WHERE project_id = $1 ORDER BY created_at DESC"
    )
    .bind(project_id)
    .fetch_all(&pool)
    .await
    .unwrap_or_default();

    Json(sets)
}

/// POST /api/projects/:project_id/drawing-sets
pub async fn upload_drawing_set(
    State(pool): State<PgPool>,
    Path(project_id): Path<Uuid>,
    Json(body): Json<CreateDrawingSetRequest>,
) -> Json<DrawingSet> {
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
    .bind(Uuid::nil()) // TODO: get from auth context
    .fetch_one(&pool)
    .await
    .expect("Failed to create drawing set");

    Json(set)
}

/// GET /api/projects/:project_id/drawing-sets/:id
pub async fn get_drawing_set(
    State(pool): State<PgPool>,
    Path((_project_id, id)): Path<(Uuid, Uuid)>,
) -> Json<Option<DrawingSet>> {
    let set = sqlx::query_as::<_, DrawingSet>(
        "SELECT * FROM drawing_sets WHERE id = $1"
    )
    .bind(id)
    .fetch_optional(&pool)
    .await
    .unwrap_or(None);

    Json(set)
}

// ============================================================
// Sheet Revisions (Spec §12)
// ============================================================

/// GET /api/sheets/:sheet_id/revisions
pub async fn list_sheet_revisions(
    State(pool): State<PgPool>,
    Path(sheet_id): Path<Uuid>,
) -> Json<Vec<DrawingSheetRevision>> {
    let revisions = sqlx::query_as::<_, DrawingSheetRevision>(
        "SELECT * FROM drawing_sheet_revisions WHERE sheet_id = $1 ORDER BY revision_number DESC"
    )
    .bind(sheet_id)
    .fetch_all(&pool)
    .await
    .unwrap_or_default();

    Json(revisions)
}

// ============================================================
// Calibration (Spec §5)
// ============================================================

/// GET /api/sheet-revisions/:revision_id/calibration
pub async fn get_calibration(
    State(pool): State<PgPool>,
    Path(revision_id): Path<Uuid>,
) -> Json<Option<ScaleCalibration>> {
    let cal = sqlx::query_as::<_, ScaleCalibration>(
        "SELECT * FROM scale_calibrations WHERE sheet_revision_id = $1 ORDER BY created_at DESC LIMIT 1"
    )
    .bind(revision_id)
    .fetch_optional(&pool)
    .await
    .unwrap_or(None);

    Json(cal)
}

/// POST /api/sheet-revisions/:revision_id/calibration
pub async fn set_calibration(
    State(pool): State<PgPool>,
    Path(revision_id): Path<Uuid>,
    Json(body): Json<CreateCalibrationRequest>,
) -> Json<ScaleCalibration> {
    // Compute world_distance_pt and scale_factor from the two points
    let dx = body.point2_x - body.point1_x;
    let dy = body.point2_y - body.point1_y;
    let world_distance_pt = (dx * dx + dy * dy).sqrt();
    let scale_factor = if world_distance_pt > 0.0 {
        body.real_distance / world_distance_pt
    } else {
        0.0
    };

    // Get sheet_id from revision
    let revision = sqlx::query_as::<_, DrawingSheetRevision>(
        "SELECT * FROM drawing_sheet_revisions WHERE id = $1"
    )
    .bind(revision_id)
    .fetch_one(&pool)
    .await
    .expect("Sheet revision not found");

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
    .bind(Uuid::nil()) // TODO: get from auth context
    .fetch_one(&pool)
    .await
    .expect("Failed to create calibration");

    Json(cal)
}

// ============================================================
// Layers (Spec §8)
// ============================================================

/// GET /api/drawing-sets/:drawing_set_id/layers
pub async fn list_layers(
    State(pool): State<PgPool>,
    Path(drawing_set_id): Path<Uuid>,
) -> Json<Vec<TakeoffLayer>> {
    let layers = sqlx::query_as::<_, TakeoffLayer>(
        "SELECT * FROM takeoff_layers WHERE drawing_set_id = $1 ORDER BY sort_order"
    )
    .bind(drawing_set_id)
    .fetch_all(&pool)
    .await
    .unwrap_or_default();

    Json(layers)
}

/// POST /api/drawing-sets/:drawing_set_id/layers
pub async fn create_layer(
    State(pool): State<PgPool>,
    Path(drawing_set_id): Path<Uuid>,
    Json(body): Json<CreateLayerRequest>,
) -> Json<TakeoffLayer> {
    let layer = sqlx::query_as::<_, TakeoffLayer>(
        r#"
        INSERT INTO takeoff_layers (id, drawing_set_id, name, color, cost_code, visible, sort_order, created_at)
        VALUES ($1, $2, $3, $4, $5, true, 0, NOW())
        RETURNING *
        "#,
    )
    .bind(Uuid::new_v4())
    .bind(drawing_set_id)
    .bind(&body.name)
    .bind(&body.color)
    .bind(body.cost_code.as_deref().unwrap_or(""))
    .fetch_one(&pool)
    .await
    .expect("Failed to create layer");

    Json(layer)
}

// ============================================================
// Measurements (Spec §6, §9)
// ============================================================

/// GET /api/layers/:layer_id/measurements
/// Returns only non-deleted measurements.
pub async fn list_measurements(
    State(pool): State<PgPool>,
    Path(layer_id): Path<Uuid>,
) -> Json<Vec<Measurement>> {
    let measurements = sqlx::query_as::<_, Measurement>(
        "SELECT * FROM measurements WHERE layer_id = $1 AND deleted_at IS NULL ORDER BY created_at"
    )
    .bind(layer_id)
    .fetch_all(&pool)
    .await
    .unwrap_or_default();

    Json(measurements)
}

/// POST /api/layers/:layer_id/measurements
/// Creates a measurement + initial version + MEASUREMENT_CREATED event (Spec §9).
pub async fn create_measurement(
    State(pool): State<PgPool>,
    Path(layer_id): Path<Uuid>,
    Json(body): Json<CreateMeasurementRequest>,
) -> Json<Measurement> {
    let measurement_id = Uuid::new_v4();
    let version_id = Uuid::new_v4();
    let user_id = Uuid::nil(); // TODO: get from auth context

    // Compute quantities server-side from WORLD geometry (Spec §6)
    let quantity_raw = compute_quantity_raw(&body.measurement_type, &body.points);
    let quantity_real = compute_quantity_real(
        &pool,
        &body.measurement_type,
        quantity_raw,
        body.calibration_id,
        &body.uom,
    )
    .await;

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
    .fetch_one(&pool)
    .await
    .expect("Failed to create measurement");

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
    .execute(&pool)
    .await
    .ok();

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
    .execute(&pool)
    .await
    .ok();

    Json(measurement)
}

/// PUT /api/measurements/:id — update creates a new version (Spec §9).
pub async fn update_measurement(
    State(pool): State<PgPool>,
    Path(measurement_id): Path<Uuid>,
    Json(body): Json<UpdateMeasurementRequest>,
) -> Json<Option<Measurement>> {
    let user_id = Uuid::nil(); // TODO: get from auth context

    // Get current measurement
    let existing = sqlx::query_as::<_, Measurement>(
        "SELECT * FROM measurements WHERE id = $1 AND deleted_at IS NULL"
    )
    .bind(measurement_id)
    .fetch_optional(&pool)
    .await
    .unwrap_or(None);

    let Some(existing) = existing else {
        return Json(None);
    };

    let new_version_number = existing.version + 1;
    let version_id = Uuid::new_v4();

    // Determine new geometry
    let new_points = body.points.as_ref().unwrap_or(&existing.points.0);
    let new_uom = body.uom.as_deref().unwrap_or(&existing.uom);
    let quantity_raw = compute_quantity_raw(&existing.measurement_type, new_points);
    // Recompute the calibrated quantity for the NEW geometry — a stale
    // quantity_real surviving a geometry edit is silent financial corruption.
    let quantity_real = compute_quantity_real(
        &pool,
        &existing.measurement_type,
        quantity_raw,
        existing.calibration_id,
        new_uom,
    )
    .await;

    // Get previous version id for supersedes link
    let prev_version_id: Option<Uuid> = sqlx::query_scalar(
        "SELECT id FROM measurement_versions WHERE measurement_id = $1 ORDER BY version_number DESC LIMIT 1"
    )
    .bind(measurement_id)
    .fetch_optional(&pool)
    .await
    .unwrap_or(None);

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
    .fetch_optional(&pool)
    .await
    .unwrap_or(None);

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
    .execute(&pool)
    .await
    .ok();

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
    .execute(&pool)
    .await
    .ok();

    Json(updated)
}

/// DELETE /api/measurements/:id — soft delete (Spec §9).
pub async fn soft_delete_measurement(
    State(pool): State<PgPool>,
    Path(measurement_id): Path<Uuid>,
) -> Json<serde_json::Value> {
    sqlx::query("UPDATE measurements SET deleted_at = NOW() WHERE id = $1")
        .bind(measurement_id)
        .execute(&pool)
        .await
        .ok();

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
    .bind(Uuid::nil()) // TODO: get from auth context
    .execute(&pool)
    .await
    .ok();

    Json(serde_json::json!({ "deleted": true }))
}

/// GET /api/measurements/:id/versions — version history (Spec §9).
pub async fn list_measurement_versions(
    State(pool): State<PgPool>,
    Path(measurement_id): Path<Uuid>,
) -> Json<Vec<MeasurementVersion>> {
    let versions = sqlx::query_as::<_, MeasurementVersion>(
        "SELECT * FROM measurement_versions WHERE measurement_id = $1 ORDER BY version_number"
    )
    .bind(measurement_id)
    .fetch_all(&pool)
    .await
    .unwrap_or_default();

    Json(versions)
}

// ============================================================
// Events (Spec §9)
// ============================================================

/// GET /api/projects/:project_id/takeoff-events
pub async fn list_events(
    State(pool): State<PgPool>,
    Path(project_id): Path<Uuid>,
) -> Json<Vec<TakeoffEvent>> {
    let events = sqlx::query_as::<_, TakeoffEvent>(
        "SELECT * FROM takeoff_events WHERE project_id = $1 ORDER BY created_at DESC LIMIT 100"
    )
    .bind(project_id)
    .fetch_all(&pool)
    .await
    .unwrap_or_default();

    Json(events)
}

// ============================================================
// Server-side quantity computation (mirrors pdf-engine logic)
// ============================================================

/// Compute the calibrated real-world quantity (Spec §6), rounded per §10.
/// Counts are unit-independent and never require calibration. Linear scales
/// by scale_factor; area by scale_factor². Returns None when uncalibrated (§5).
async fn compute_quantity_real(
    pool: &PgPool,
    measurement_type: &crate::models::MeasurementType,
    quantity_raw: f64,
    calibration_id: Option<Uuid>,
    uom: &str,
) -> Option<f64> {
    use crate::models::MeasurementType as MT;

    if matches!(measurement_type, MT::Count) {
        return Some(quantity_raw);
    }
    if matches!(measurement_type, MT::Volume) {
        // Volume deferred in MVP (Spec §6 placeholder)
        return None;
    }

    let scale_factor: Option<f64> = match calibration_id {
        Some(id) => sqlx::query_scalar(
            "SELECT scale_factor FROM scale_calibrations WHERE id = $1",
        )
        .bind(id)
        .fetch_optional(pool)
        .await
        .unwrap_or(None),
        None => None,
    };
    let sf = scale_factor.filter(|s| *s > 0.0)?;

    let real = match measurement_type {
        MT::Area => quantity_raw * sf * sf,
        _ => quantity_raw * sf,
    };
    Some(round_quantity(real, uom))
}

/// Round a quantity to the precision defined for its unit of measure (Spec §10).
/// Mirrors UOM_PRECISION in @openbuild/types so app and exports agree.
fn round_quantity(value: f64, uom: &str) -> f64 {
    let precision: i32 = match uom.to_lowercase().as_str() {
        "ea" | "lb" | "gal" | "mm" => 0,
        "m" => 3,
        _ => 2,
    };
    let factor = 10f64.powi(precision);
    (value * factor).round() / factor
}

fn compute_quantity_raw(
    measurement_type: &crate::models::MeasurementType,
    points: &[WorldPoint],
) -> f64 {
    match measurement_type {
        crate::models::MeasurementType::Linear => {
            if points.len() < 2 { return 0.0; }
            let mut total = 0.0;
            for i in 1..points.len() {
                let dx = points[i].x - points[i - 1].x;
                let dy = points[i].y - points[i - 1].y;
                total += (dx * dx + dy * dy).sqrt();
            }
            total
        }
        crate::models::MeasurementType::Area => {
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
        crate::models::MeasurementType::Count => points.len() as f64,
        crate::models::MeasurementType::Volume => 0.0,
    }
}
