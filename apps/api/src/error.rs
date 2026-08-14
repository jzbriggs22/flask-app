use axum::{
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};

/// Structured API error (CLAUDE.md: all routes return JSON errors with
/// error codes). Serialized shape matches ApiErrorResponse in
/// @openbuild/types: { "code": "...", "message": "..." }.
#[derive(Debug)]
pub struct ApiError {
    pub status: StatusCode,
    pub code: &'static str,
    pub message: String,
}

impl ApiError {
    pub fn not_found(what: &str) -> Self {
        Self {
            status: StatusCode::NOT_FOUND,
            code: "NOT_FOUND",
            message: format!("{what} not found"),
        }
    }

    pub fn unprocessable(code: &'static str, message: impl Into<String>) -> Self {
        Self {
            status: StatusCode::UNPROCESSABLE_ENTITY,
            code,
            message: message.into(),
        }
    }

    pub fn internal(message: impl Into<String>) -> Self {
        Self {
            status: StatusCode::INTERNAL_SERVER_ERROR,
            code: "INTERNAL",
            message: message.into(),
        }
    }
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        if self.status.is_server_error() {
            tracing::error!(code = self.code, "{}", self.message);
        }
        let body = Json(serde_json::json!({
            "code": self.code,
            "message": self.message,
        }));
        (self.status, body).into_response()
    }
}

impl From<sqlx::Error> for ApiError {
    fn from(err: sqlx::Error) -> Self {
        match err {
            sqlx::Error::RowNotFound => Self::not_found("Resource"),
            other => Self::internal(format!("database error: {other}")),
        }
    }
}

/// Handler result alias: Ok(Json<T>) or a structured JSON error.
pub type ApiResult<T> = Result<Json<T>, ApiError>;
