mod handler;
mod projection;

use aws_sdk_dynamodb::Client as DynamoClient;
use cinderroute::{cloud, config, telemetry};
use handler::Projector;
use lambda_runtime::{Error as LambdaError, service_fn};

#[tokio::main]
async fn main() -> Result<(), LambdaError> {
    telemetry::init("cinderroute-projector");

    let endpoint = config::aws_endpoint()?;
    let region = config::aws_region();
    let table = config::required("PROJECTION_TABLE")?;
    let valkey_endpoint = config::required("VALKEY_ENDPOINT")?;
    let sdk = cloud::sdk_config(&endpoint, &region).await;
    let projector = Projector::new(
        DynamoClient::new(&sdk),
        table,
        redis::Client::open(config::normalize_valkey_url(&valkey_endpoint))?,
    );

    lambda_runtime::run(service_fn(move |event| {
        let projector = projector.clone();
        async move { projector.handle(event).await }
    }))
    .await
}
