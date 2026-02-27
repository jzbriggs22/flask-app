use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::FromRow;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize, sqlx::Type, PartialEq)]
#[sqlx(type_name = "estimate_status", rename_all = "snake_case")]
#[serde(rename_all = "snake_case")]
pub enum EstimateStatus {
    Draft,
    Submitted,
    Approved,
}

#[derive(Debug, Clone, Serialize, FromRow)]
pub struct Estimate {
    pub id: Uuid,
    pub project_id: Uuid,
    pub name: String,
    pub status: EstimateStatus,
    pub created_by: Uuid,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, FromRow)]
pub struct EstimateLineItem {
    pub id: Uuid,
    pub estimate_id: Uuid,
    pub cost_code: String,
    pub description: String,
    pub quantity: f64,
    pub unit: String,
    /// Unit cost in cents. Never floating point for money.
    pub unit_cost_cents: i64,
    pub measurement_id: Option<Uuid>,
    pub sort_order: i32,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

#[derive(Debug, Deserialize)]
pub struct CreateEstimateRequest {
    pub name: String,
}

#[derive(Debug, Deserialize)]
pub struct CreateLineItemRequest {
    pub cost_code: String,
    pub description: String,
    pub quantity: f64,
    pub unit: String,
    pub unit_cost_cents: i64,
    pub measurement_id: Option<Uuid>,
}

#[derive(Debug, Deserialize)]
pub struct UpdateLineItemRequest {
    pub cost_code: Option<String>,
    pub description: Option<String>,
    pub quantity: Option<f64>,
    pub unit: Option<String>,
    pub unit_cost_cents: Option<i64>,
}
