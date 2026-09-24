mod relay;

use aws_sdk_sqs::Client as SqsClient;
use cinderroute::{cloud, config, telemetry};
use lambda_runtime::{Error as LambdaError, service_fn};
use relay::Relay;
use sqlx::postgres::PgPoolOptions;
use std::time::Duration;

#[tokio::main]
async fn main() -> Result<(), LambdaError> {
    telemetry::init("cinderroute-outbox-relay");

    let endpoint = config::aws_endpoint()?;
    let region = config::aws_region();
    let queue_url = config::required("QUEUE_URL")?;
    let database_url = config::required("DATABASE_URL")?;
    let sdk = cloud::sdk_config(&endpoint, &region).await;
    let db = PgPoolOptions::new()
        .max_connections(3)
        .acquire_timeout(Duration::from_secs(5))
        .connect(&database_url)
        .await?;
    let relay = Relay::new(db, SqsClient::new(&sdk), queue_url);

    lambda_runtime::run(service_fn(move |event| {
        let relay = relay.clone();
        async move { relay.handle(event).await }
    }))
    .await
}
