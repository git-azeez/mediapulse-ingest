mod application;
mod error;
mod health;
mod request;
mod shipments;
mod state;

use cinderroute::telemetry;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    telemetry::init("cinderroute-api");
    application::run().await
}
