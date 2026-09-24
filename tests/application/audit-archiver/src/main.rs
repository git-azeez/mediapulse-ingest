mod batch;
mod handler;
mod repository;
mod storage;

use anyhow::Result;
use aws_sdk_s3::{Client as S3Client, config::Builder as S3ConfigBuilder};
use cinderroute::{cloud, config, telemetry};
use handler::Archiver;
use lambda_runtime::{Error as LambdaError, service_fn};
use sqlx::postgres::PgPoolOptions;
use std::time::Duration;

#[tokio::main]
async fn main() -> Result<(), LambdaError> {
    telemetry::init("cinderroute-audit-archiver");

    let endpoint = config::aws_endpoint()?;
    let region = config::aws_region();
    let bucket = config::required("AUDIT_BUCKET")?;
    let prefix = config::optional("AUDIT_PREFIX").unwrap_or_else(|| "events/".to_owned());
    let database_url = config::required("DATABASE_URL")?;

    let sdk = cloud::sdk_config(&endpoint, &region).await;
    let s3_config = S3ConfigBuilder::from(&sdk).force_path_style(true).build();
    let db = PgPoolOptions::new()
        .max_connections(3)
        .acquire_timeout(Duration::from_secs(5))
        .connect(&database_url)
        .await?;
    let archiver = Archiver::new(db, S3Client::from_conf(s3_config), bucket, prefix);

    lambda_runtime::run(service_fn(move |event| {
        let archiver = archiver.clone();
        async move { archiver.handle(event).await }
    }))
    .await
}
