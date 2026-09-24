use anyhow::Result;
use aws_config::{BehaviorVersion, Region, SdkConfig};
use aws_credential_types::Credentials;

pub async fn sdk_config(endpoint: &str, region: &str) -> SdkConfig {
    aws_config::defaults(BehaviorVersion::latest())
        .region(Region::new(region.to_owned()))
        .endpoint_url(endpoint)
        .credentials_provider(Credentials::new(
            std::env::var("AWS_ACCESS_KEY_ID").unwrap_or_else(|_| "test".to_owned()),
            std::env::var("AWS_SECRET_ACCESS_KEY").unwrap_or_else(|_| "test".to_owned()),
            None,
            None,
            "cinderroute-fixture",
        ))
        .load()
        .await
}

pub async fn open_valkey(endpoint: &str) -> Result<redis::aio::ConnectionManager> {
    let client = redis::Client::open(crate::config::normalize_valkey_url(endpoint))?;

    Ok(redis::aio::ConnectionManager::new(client).await?)
}
