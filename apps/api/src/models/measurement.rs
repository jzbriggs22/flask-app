use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::FromRow;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, sqlx::Type, PartialEq)]
#[sqlx(type_name = "measurement_type", rename_all = "snake_case")]
#[serde(rename_all = "snake_case")]
pub enum MeasurementType {
    Linear,
    Area,
    Count,
    Volume,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Point2D {
    pub x: f64,
    pub y: f64,
}

#[derive(Debug, Clone, Serialize, FromRow)]
pub struct Measurement {
    pub id: Uuid,
    pub layer_id: Uuid,
    pub sheet_id: Uuid,
    #[sqlx(rename = "measurement_type")]
    pub measurement_type: MeasurementType,
    pub points: sqlx::types::Json<Vec<Point2D>>,
    pub value: f64,
    pub unit: String,
    pub cost_code: String,
    pub label: Option<String>,
    pub created_by: Uuid,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Deserialize)]
pub struct CreateMeasurementRequest {
    pub sheet_id: Uuid,
    pub measurement_type: MeasurementType,
    pub points: Vec<Point2D>,
    pub value: f64,
    pub unit: String,
    pub cost_code: Option<String>,
    pub label: Option<String>,
}
