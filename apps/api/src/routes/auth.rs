use axum::{extract::State, Json};
use sqlx::PgPool;

use crate::models::{CreateUserRequest, LoginRequest};

/// POST /api/auth/register
pub async fn register(
    State(_pool): State<PgPool>,
    Json(_body): Json<CreateUserRequest>,
) -> Json<serde_json::Value> {
    // TODO: Implement registration
    // 1. Validate email uniqueness
    // 2. Hash password with argon2
    // 3. Create organization if first user
    // 4. Insert user
    // 5. Generate JWT
    Json(serde_json::json!({
        "message": "Registration endpoint — not yet implemented"
    }))
}

/// POST /api/auth/login
pub async fn login(
    State(_pool): State<PgPool>,
    Json(_body): Json<LoginRequest>,
) -> Json<serde_json::Value> {
    // TODO: Implement login
    // 1. Find user by email
    // 2. Verify password with argon2
    // 3. Generate JWT
    Json(serde_json::json!({
        "message": "Login endpoint — not yet implemented"
    }))
}
