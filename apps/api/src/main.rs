use axum::{
    routing::{get, post, put, delete},
    Router,
    Json,
};
use serde::Serialize;
use tower_http::cors::CorsLayer;
use tower_http::trace::TraceLayer;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

mod routes;
mod models;
mod services;

#[derive(Serialize)]
struct HealthResponse {
    status: String,
    version: String,
}

async fn health() -> Json<HealthResponse> {
    Json(HealthResponse {
        status: "ok".to_string(),
        version: env!("CARGO_PKG_VERSION").to_string(),
    })
}

#[tokio::main]
async fn main() {
    // Initialize tracing
    tracing_subscriber::registry()
        .with(tracing_subscriber::EnvFilter::try_from_default_env()
            .unwrap_or_else(|_| "openbuild_api=debug,tower_http=debug".into()))
        .with(tracing_subscriber::fmt::layer())
        .init();

    // Database connection
    let database_url = std::env::var("DATABASE_URL")
        .unwrap_or_else(|_| "postgres://openbuild:openbuild_dev@localhost:5432/openbuild".to_string());

    let pool = sqlx::postgres::PgPoolOptions::new()
        .max_connections(20)
        .connect(&database_url)
        .await
        .expect("Failed to connect to database");

    // Run migrations
    sqlx::migrate!("../../migrations")
        .run(&pool)
        .await
        .expect("Failed to run migrations");

    tracing::info!("Database connected and migrations applied");

    // Build router
    let app = Router::new()
        // Health check
        .route("/api/health", get(health))

        // Auth routes
        .route("/api/auth/register", post(routes::auth::register))
        .route("/api/auth/login", post(routes::auth::login))

        // Project routes
        .route("/api/projects", get(routes::projects::list_projects))
        .route("/api/projects", post(routes::projects::create_project))
        .route("/api/projects/{id}", get(routes::projects::get_project))
        .route("/api/projects/{id}", put(routes::projects::update_project))
        .route("/api/projects/{id}", delete(routes::projects::delete_project))

        // Drawing set routes
        .route("/api/projects/{project_id}/drawing-sets", get(routes::takeoff::list_drawing_sets))
        .route("/api/projects/{project_id}/drawing-sets", post(routes::takeoff::upload_drawing_set))
        .route("/api/projects/{project_id}/drawing-sets/{id}", get(routes::takeoff::get_drawing_set))

        // Takeoff measurement routes
        .route("/api/drawing-sets/{drawing_set_id}/layers", get(routes::takeoff::list_layers))
        .route("/api/drawing-sets/{drawing_set_id}/layers", post(routes::takeoff::create_layer))
        .route("/api/layers/{layer_id}/measurements", get(routes::takeoff::list_measurements))
        .route("/api/layers/{layer_id}/measurements", post(routes::takeoff::create_measurement))

        // Estimate routes
        .route("/api/projects/{project_id}/estimates", get(routes::estimating::list_estimates))
        .route("/api/projects/{project_id}/estimates", post(routes::estimating::create_estimate))
        .route("/api/estimates/{estimate_id}", get(routes::estimating::get_estimate))
        .route("/api/estimates/{estimate_id}/line-items", get(routes::estimating::list_line_items))
        .route("/api/estimates/{estimate_id}/line-items", post(routes::estimating::create_line_item))
        .route("/api/line-items/{item_id}", put(routes::estimating::update_line_item))
        .route("/api/line-items/{item_id}", delete(routes::estimating::delete_line_item))

        // Middleware
        .layer(TraceLayer::new_for_http())
        .layer(CorsLayer::permissive())
        .with_state(pool);

    // Start server
    let addr = std::env::var("LISTEN_ADDR").unwrap_or_else(|_| "0.0.0.0:3000".to_string());
    let listener = tokio::net::TcpListener::bind(&addr).await.unwrap();
    tracing::info!("OpenBuild API listening on {}", addr);
    axum::serve(listener, app).await.unwrap();
}
