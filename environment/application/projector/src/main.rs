mod handler;
mod projection;

use axum::{routing::post, Router};
use cinderroute::{cloud, config, telemetry};
use handler::Projector;
use std::net::SocketAddr;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    telemetry::init("cinderroute-projector");

    let endpoint = config::gcp_endpoint()?;
    let project_id = config::gcp_project_id();
    let database = config::required("FIRESTORE_DATABASE")?;
    let valkey_endpoint = config::required("VALKEY_ENDPOINT")?;
    
    let projector = Projector::new(
        cloud::http_client()?,
        endpoint,
        project_id,
        database,
        redis::Client::open(config::normalize_valkey_url(&valkey_endpoint))?,
    );

    let app = Router::new()
        .route("/", post(handler::handle_pubsub))
        .with_state(projector);

    let port = std::env::var("PORT").unwrap_or_else(|_| "8080".to_string());
    let addr: SocketAddr = format!("0.0.0.0:{}", port).parse()?;
    
    tracing::info!("listening on {}", addr);
    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;
    
    Ok(())
}
