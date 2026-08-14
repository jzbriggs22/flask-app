use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::FromRow;
use uuid::Uuid;

/// Takeoff event types (Spec §9).
#[derive(Debug, Clone, Serialize, Deserialize, sqlx::Type, PartialEq)]
#[sqlx(type_name = "takeoff_event_type")]
pub enum TakeoffEventType {
    #[sqlx(rename = "MEASUREMENT_CREATED")]
    MeasurementCreated,
    #[sqlx(rename = "MEASUREMENT_UPDATED")]
    MeasurementUpdated,
    #[sqlx(rename = "MEASUREMENT_DELETED")]
    MeasurementDeleted,
    #[sqlx(rename = "CALIBRATION_SET")]
    CalibrationSet,
    #[sqlx(rename = "CALIBRATION_INVALIDATED")]
    CalibrationInvalidated,
    #[sqlx(rename = "LAYER_CREATED")]
    LayerCreated,
    #[sqlx(rename = "LAYER_UPDATED")]
    LayerUpdated,
    #[sqlx(rename = "LAYER_DELETED")]
    LayerDeleted,
    #[sqlx(rename = "REVISION_UPLOADED")]
    RevisionUploaded,
}

/// Append-only audit log entry (Spec §9).
#[derive(Debug, Clone, Serialize, FromRow)]
pub struct TakeoffEvent {
    pub id: Uuid,
    pub project_id: Uuid,
    pub sheet_revision_id: Option<Uuid>,
    pub event_type: TakeoffEventType,
    pub measurement_id: Option<Uuid>,
    pub measurement_version_id: Option<Uuid>,
    pub calibration_id: Option<Uuid>,
    pub layer_id: Option<Uuid>,
    pub payload: sqlx::types::Json<serde_json::Value>,
    pub created_at: DateTime<Utc>,
    pub created_by: Uuid,
}
