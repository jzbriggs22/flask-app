use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::FromRow;
use uuid::Uuid;

/// Spec §6: measurement types.
#[derive(Debug, Clone, Serialize, Deserialize, sqlx::Type, PartialEq)]
#[sqlx(type_name = "measurement_type", rename_all = "snake_case")]
#[serde(rename_all = "snake_case")]
pub enum MeasurementType {
    Linear,
    Area,
    Count,
    Volume,
}

/// WORLD coordinate point (PDF_PT). Spec §2.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorldPoint {
    pub x: f64,
    pub y: f64,
}

/// Core measurement entity — materialized current state.
/// Spec §6: every measurement has a calibration reference or is uncalibrated.
/// Spec §9: changes produce new versions; this is the materialized view.
#[derive(Debug, Clone, Serialize, FromRow)]
pub struct Measurement {
    pub id: Uuid,
    pub layer_id: Uuid,
    pub sheet_id: Uuid,
    pub sheet_revision_id: Option<Uuid>,
    #[sqlx(rename = "measurement_type")]
    pub measurement_type: MeasurementType,
    /// Geometry in WORLD (PDF_PT). Rule §2: never in pixels.
    pub points: sqlx::types::Json<Vec<WorldPoint>>,
    pub value: f64,
    pub unit: String,
    pub cost_code: String,
    pub label: Option<String>,
    /// Reference to calibration. Null = uncalibrated (§5).
    pub calibration_id: Option<Uuid>,
    /// Raw quantity from WORLD geometry (PDF_PT units).
    pub quantity_raw: f64,
    /// Real-world quantity after calibration. Null if uncalibrated.
    pub quantity_real: Option<f64>,
    /// Unit of measure for real quantity (ft, sf, ea, etc.).
    pub uom: String,
    pub version: i32,
    pub created_by: Uuid,
    pub created_at: DateTime<Utc>,
    pub deleted_at: Option<DateTime<Utc>>,
}

/// Immutable version record. Spec §9:
/// "Edit measurement" creates a new version; prior versions remain immutable.
#[derive(Debug, Clone, Serialize, FromRow)]
pub struct MeasurementVersion {
    pub id: Uuid,
    pub measurement_id: Uuid,
    pub version_number: i32,
    pub geometry_world: sqlx::types::Json<Vec<WorldPoint>>,
    pub calibration_id: Option<Uuid>,
    pub quantity_raw: f64,
    pub quantity_real: Option<f64>,
    pub uom: String,
    pub metadata: sqlx::types::Json<serde_json::Value>,
    pub created_at: DateTime<Utc>,
    pub created_by: Uuid,
    pub supersedes_version_id: Option<Uuid>,
}

#[derive(Debug, Deserialize)]
pub struct CreateMeasurementRequest {
    pub sheet_id: Uuid,
    pub sheet_revision_id: Uuid,
    pub measurement_type: MeasurementType,
    /// Geometry in WORLD (PDF_PT).
    pub points: Vec<WorldPoint>,
    pub uom: String,
    pub cost_code: Option<String>,
    pub label: Option<String>,
    pub calibration_id: Option<Uuid>,
}

#[derive(Debug, Deserialize)]
pub struct UpdateMeasurementRequest {
    pub points: Option<Vec<WorldPoint>>,
    pub cost_code: Option<String>,
    pub label: Option<String>,
    pub uom: Option<String>,
}
