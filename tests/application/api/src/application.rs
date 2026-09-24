use crate::{health, request, shipments, state::ApplicationContext};
use axum::{
    Router,
    middleware::{self, from_fn},
    routing::{get, post},
};
use cinderroute::auth;
use tokio::net::TcpListener;
use tower_http::catch_panic::CatchPanicLayer;

pub(crate) async fn run() -> anyhow::Result<()> {
    let context = ApplicationContext::load().await?;
    let auth_state = context.auth_state;

    let write_routes = Router::new()
        .route("/v1/media", post(shipments::create))
        .route(
            "/v1/media/{id}/checkpoints",
            post(shipments::record_checkpoint),
        )
        .route("/v1/shipments", post(shipments::create))
        .route(
            "/v1/shipments/{id}/checkpoints",
            post(shipments::record_checkpoint),
        )
        .layer(middleware::from_fn_with_state(
            auth_state.clone(),
            auth::require_write,
        ));
    let read_routes = Router::new()
        .route("/v1/media/{id}", get(shipments::get))
        .route("/v1/media/{id}/timeline", get(shipments::timeline))
        .route("/v1/shipments/{id}", get(shipments::get))
        .route("/v1/shipments/{id}/timeline", get(shipments::timeline))
        .layer(middleware::from_fn_with_state(
            auth_state.clone(),
            auth::require_read,
        ));
    let admin_routes = Router::new()
        .route(
            "/v1/admin/projections/{id}/rebuild",
            post(shipments::rebuild_projection),
        )
        .layer(middleware::from_fn_with_state(
            auth_state,
            auth::require_admin,
        ));

    let app = Router::new()
        .route("/health/live", get(health::live))
        .route("/health/ready", get(health::ready))
        .merge(write_routes)
        .merge(read_routes)
        .merge(admin_routes)
        .layer(CatchPanicLayer::new())
        .layer(from_fn(request::correlation_middleware))
        .with_state(context.state);

    let listener = TcpListener::bind(context.bind).await?;
    tracing::info!(bind = %context.bind, "api_listening");
    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown_signal())
        .await?;
    Ok(())
}

async fn shutdown_signal() {
    let ctrl_c = async { tokio::signal::ctrl_c().await.expect("ctrl-c signal") };
    #[cfg(unix)]
    let terminate = async {
        tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
            .expect("terminate signal")
            .recv()
            .await;
    };
    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();
    tokio::select! { _ = ctrl_c => {}, _ = terminate => {} }
}
