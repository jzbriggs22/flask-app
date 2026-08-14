use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::FromRow;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, FromRow)]
pub struct DrawingSet {
    pub id: Uuid,
    pub project_id: Uuid,
    pub name: String,
    pub revision: i32,
    pub file_url: String,
    pub file_size: i64,
    pub sheet_count: i32,
    pub created_by: Uuid,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, FromRow)]
pub struct DrawingSheet {
    pub id: Uuid,
    pub drawing_set_id: Uuid,
    pub sheet_number: String,
    pub title: String,
    pub page_index: i32,
    pub thumbnail_url: Option<String>,
    pub created_by: Uuid,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

/// A specific version of a sheet. Measurements bind to revisions, not sheets.
/// Spec §12: Never silently move measurements across revisions.
#[derive(Debug, Clone, Serialize, FromRow)]
pub struct DrawingSheetRevision {
    pub id: Uuid,
    pub sheet_id: Uuid,
    pub drawing_set_id: Uuid,
    pub revision_number: i32,
    pub file_url: String,
    pub page_index: i32,
    pub uploaded_at: DateTime<Utc>,
    pub uploaded_by: Uuid,
    pub page_width_pt: Option<f64>,
    pub page_height_pt: Option<f64>,
    pub rotation: i32,
}

#[derive(Debug, Deserialize)]
pub struct CreateDrawingSetRequest {
    pub name: String,
}

/// Enriched calibration per spec §5.
/// Maps WORLD (PDF_PT) → Real-world units.
#[derive(Debug, Clone, Serialize, FromRow)]
pub struct ScaleCalibration {
    pub id: Uuid,
    pub sheet_id: Uuid,
    pub sheet_revision_id: Option<Uuid>,
    pub unit_system: String,
    pub display_unit: String,
    pub point1_x: f64,
    pub point1_y: f64,
    pub point2_x: f64,
    pub point2_y: f64,
    pub world_distance_pt: f64,
    pub real_distance: f64,
    pub scale_factor: f64,
    pub method: String,
    pub confidence: String,
    pub unit: String,
    pub created_by: Uuid,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Deserialize)]
pub struct CreateCalibrationRequest {
    pub sheet_revision_id: Uuid,
    pub unit_system: String,
    pub display_unit: String,
    pub point1_x: f64,
    pub point1_y: f64,
    pub point2_x: f64,
    pub point2_y: f64,
    pub real_distance: f64,
    pub method: Option<String>,
    pub confidence: Option<String>,
}

#[derive(Debug, Clone, Serialize, FromRow)]
pub struct TakeoffLayer {
    pub id: Uuid,
    pub drawing_set_id: Uuid,
    pub name: String,
    pub color: String,
    pub cost_code: String,
    pub visible: bool,
    pub sort_order: i32,
    pub created_by: Uuid,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Deserialize)]
pub struct CreateLayerRequest {
    pub name: String,
    pub color: String,
    pub cost_code: Option<String>,
}
