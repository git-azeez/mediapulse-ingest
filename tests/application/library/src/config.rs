use anyhow::{Context, Result, bail};
use std::env;

pub fn required(name: &str) -> Result<String> {
    if let Ok(value) = env::var(name) {
        if !value.trim().is_empty() {
            return Ok(value);
        }
    }
    let gcp_alias = match name {
        "QUEUE_URL" => Some("PUBSUB_TOPIC"),
        "PROJECTION_TABLE" => Some("FIRESTORE_DATABASE"),
        "VALKEY_ENDPOINT" => Some("DATASTORE_EMULATOR_HOST"),
        "COGNITO_ISSUER" => Some("AUTH_ISSUER"),
        "COGNITO_AUDIENCES" => Some("AUTH_AUDIENCES"),
        "COGNITO_JWKS_URL" => Some("AUTH_JWKS_URL"),
        "AWS_ENDPOINT_URL" => Some("GCP_ENDPOINT_URL"),
        "AWS_REGION" | "AWS_DEFAULT_REGION" => Some("GCP_REGION"),
        _ => None,
    };
    if let Some(alias) = gcp_alias {
        if let Ok(value) = env::var(alias) {
            if !value.trim().is_empty() {
                return Ok(value);
            }
        }
    }
    bail!("required environment variable {name} is missing or empty")
}

pub fn optional(name: &str) -> Option<String> {
    env::var(name).ok().filter(|value| !value.trim().is_empty())
}

pub fn parse_u64(name: &str, default: u64) -> Result<u64> {
    optional(name)
        .map(|value| {
            value
                .parse::<u64>()
                .with_context(|| format!("{name} must be an unsigned integer"))
        })
        .unwrap_or(Ok(default))
}

pub fn aws_region() -> String {
    optional("GCP_REGION")
        .or_else(|| optional("AWS_REGION"))
        .or_else(|| optional("AWS_DEFAULT_REGION"))
        .unwrap_or_else(|| "us-central1".to_owned())
}

pub fn aws_endpoint() -> Result<String> {
    optional("GCP_ENDPOINT_URL")
        .or_else(|| optional("AWS_ENDPOINT_URL"))
        .ok_or_else(|| anyhow::anyhow!("required environment variable GCP_ENDPOINT_URL is missing or empty"))
}

pub fn normalize_valkey_url(raw: &str) -> String {
    if raw.starts_with("redis://") || raw.starts_with("rediss://") {
        raw.to_owned()
    } else {
        format!("redis://{raw}")
    }
}
