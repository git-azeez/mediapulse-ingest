mod batch;
mod handler;
mod repository;
mod storage;

use axum::{routing::post, Router};
use cinderroute::{cloud, config, telemetry};
use handler::Archiver;
use sqlx::postgres::PgPoolOptions;
use std::{net::SocketAddr, time::Duration};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    telemetry::init("cinderroute-audit-archiver");

    let database_url = config::required("DATABASE_URL")?;
    let gcp_endpoint = config::gcp_endpoint()?;
    let bucket = config::required("AUDIT_BUCKET")?;
    let prefix = config::optional("AUDIT_PREFIX").unwrap_or_else(|| "events/".to_owned());

    let db = PgPoolOptions::new()
        .max_connections(3)
        .acquire_timeout(Duration::from_secs(5))
        .connect(&database_url)
        .await?;
        
    let archiver = Archiver::new(db, cloud::http_client()?, gcp_endpoint, bucket, prefix);

    let app = Router::new()
        .route("/", post(handler::handle_trigger))
        .with_state(archiver);

    let port = std::env::var("PORT").unwrap_or_else(|_| "8080".to_string());
    let addr: SocketAddr = format!("0.0.0.0:{}", port).parse()?;
    
    tracing::info!("listening on {}", addr);
    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;
    
    Ok(())
}
