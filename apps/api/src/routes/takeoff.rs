use axum::{
    extract::{Path, State},
    Json,
};
use sqlx::PgPool;
use uuid::Uuid;

use crate::models::{
    DrawingSet, TakeoffLayer, Measurement,
    CreateDrawingSetRequest, CreateLayerRequest, CreateMeasurementRequest,
};

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

/// GET /api/layers/:layer_id/measurements
pub async fn list_measurements(
    State(pool): State<PgPool>,
    Path(layer_id): Path<Uuid>,
) -> Json<Vec<Measurement>> {
    let measurements = sqlx::query_as::<_, Measurement>(
        "SELECT * FROM measurements WHERE layer_id = $1 ORDER BY created_at"
    )
    .bind(layer_id)
    .fetch_all(&pool)
    .await
    .unwrap_or_default();

    Json(measurements)
}

/// POST /api/layers/:layer_id/measurements
pub async fn create_measurement(
    State(pool): State<PgPool>,
    Path(layer_id): Path<Uuid>,
    Json(body): Json<CreateMeasurementRequest>,
) -> Json<Measurement> {
    let measurement = sqlx::query_as::<_, Measurement>(
        r#"
        INSERT INTO measurements (id, layer_id, sheet_id, measurement_type, points, value, unit, cost_code, label, created_by, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW())
        RETURNING *
        "#,
    )
    .bind(Uuid::new_v4())
    .bind(layer_id)
    .bind(body.sheet_id)
    .bind(&body.measurement_type)
    .bind(sqlx::types::Json(&body.points))
    .bind(body.value)
    .bind(&body.unit)
    .bind(body.cost_code.as_deref().unwrap_or(""))
    .bind(body.label.as_deref())
    .bind(Uuid::nil()) // TODO: get from auth context
    .fetch_one(&pool)
    .await
    .expect("Failed to create measurement");

    Json(measurement)
}
