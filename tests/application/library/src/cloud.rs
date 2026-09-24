use anyhow::Result;
use reqwest::{Client, ClientBuilder};
use std::time::Duration;

pub fn http_client() -> Result<Client> {
    ClientBuilder::new()
        .timeout(Duration::from_secs(30))
        .pool_idle_timeout(Duration::from_secs(90))
        .build()
        .map_err(Into::into)
}

pub async fn open_valkey(endpoint: &str) -> Result<redis::aio::ConnectionManager> {
    let client = redis::Client::open(crate::config::normalize_valkey_url(endpoint))?;
    Ok(redis::aio::ConnectionManager::new(client).await?)
}
