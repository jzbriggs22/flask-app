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
}

#[derive(Debug, Deserialize)]
pub struct CreateDrawingSetRequest {
    pub name: String,
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
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Deserialize)]
pub struct CreateLayerRequest {
    pub name: String,
    pub color: String,
    pub cost_code: Option<String>,
}
