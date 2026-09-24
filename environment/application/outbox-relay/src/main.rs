mod relay;

use axum::{routing::post, Router};
use cinderroute::{cloud, config, telemetry};
use relay::Relay;
use sqlx::postgres::PgPoolOptions;
use std::{net::SocketAddr, time::Duration};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    telemetry::init("cinderroute-outbox-relay");

    let database_url = config::required("DATABASE_URL")?;
    let gcp_endpoint = config::gcp_endpoint()?;
    let project_id = config::gcp_project_id();
    let pubsub_topic = config::required("PUBSUB_TOPIC")?;
    
    let db = PgPoolOptions::new()
        .max_connections(3)
        .acquire_timeout(Duration::from_secs(5))
        .connect(&database_url)
        .await?;
        
    let relay = Relay::new(db, cloud::http_client()?, gcp_endpoint, project_id, pubsub_topic);

    let app = Router::new()
        .route("/", post(relay::handle_trigger))
        .with_state(relay);

    let port = std::env::var("PORT").unwrap_or_else(|_| "8080".to_string());
    let addr: SocketAddr = format!("0.0.0.0:{}", port).parse()?;
    
    tracing::info!("listening on {}", addr);
    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;
    
    Ok(())
}
