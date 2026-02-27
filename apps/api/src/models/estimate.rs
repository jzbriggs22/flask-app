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

/// Estimate line item with traceability (§11).
/// Line Item → Quantity → Measurement(s) → Sheet Revision → Pixel location.
#[derive(Debug, Clone, Serialize, FromRow)]
pub struct EstimateLineItem {
    pub id: Uuid,
    pub estimate_id: Uuid,
    pub cost_code: String,
    pub description: String,
    pub quantity: f64,
    pub unit: String,
    /// Unit cost in cents. Invariant §3: Money uses integers only.
    pub unit_cost_cents: i64,
    pub measurement_id: Option<Uuid>,
    /// "manual" or "driven" (Spec §11).
    pub source_type: String,
    /// For driven items: quantity snapshot at time of pricing (§11).
    pub quantity_snapshot: Option<f64>,
    pub snapshot_at: Option<DateTime<Utc>>,
    /// True if source measurements changed since snapshot (§11).
    pub is_stale: bool,
    pub sort_order: i32,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

/// Link between a line item and its source measurements (§11).
#[derive(Debug, Clone, Serialize, FromRow)]
pub struct EstimateLineItemSource {
    pub id: Uuid,
    pub line_item_id: Uuid,
    pub measurement_id: Uuid,
    pub measurement_version_id: Uuid,
    pub quantity_snapshot: f64,
    pub uom_snapshot: String,
    pub linked_at: DateTime<Utc>,
    pub linked_by: Uuid,
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
    pub source_type: Option<String>,
    /// For driven items: measurement IDs to link.
    pub measurement_ids: Option<Vec<Uuid>>,
}

#[derive(Debug, Deserialize)]
pub struct UpdateLineItemRequest {
    pub cost_code: Option<String>,
    pub description: Option<String>,
    pub quantity: Option<f64>,
    pub unit: Option<String>,
    pub unit_cost_cents: Option<i64>,
}
