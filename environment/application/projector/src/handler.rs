use anyhow::Context;
use axum::{extract::State, Json, http::StatusCode};
use cinderroute::model::EventEnvelope;
use reqwest::Client;
use serde_json::Value;

#[derive(Clone)]
pub(crate) struct Projector {
    pub(crate) http: Client,
    pub(crate) gcp_endpoint: String,
    pub(crate) project_id: String,
    pub(crate) database: String,
    pub(crate) valkey: redis::Client,
}

impl Projector {
    pub(crate) fn new(http: Client, gcp_endpoint: String, project_id: String, database: String, valkey: redis::Client) -> Self {
        Self {
            http,
            gcp_endpoint,
            project_id,
            database,
            valkey,
        }
    }
}

pub(crate) async fn handle_pubsub(
    State(projector): State<Projector>,
    Json(payload): Json<Value>,
) -> Result<StatusCode, (StatusCode, String)> {
    let message = payload
        .get("message")
        .context("Pub/Sub push must contain a message object")
        .map_err(|e| (StatusCode::BAD_REQUEST, e.to_string()))?;
        
    let data = message
        .get("data")
        .and_then(Value::as_str)
        .context("Pub/Sub message must contain base64 data")
        .map_err(|e| (StatusCode::BAD_REQUEST, e.to_string()))?;
        
    let message_id = message
        .get("messageId")
        .and_then(Value::as_str)
        .unwrap_or("unknown");

    use base64::Engine;
    let decoded = base64::engine::general_purpose::STANDARD.decode(data).map_err(|e| {
        (StatusCode::BAD_REQUEST, format!("Invalid base64: {e}"))
    })?;

    let envelope: EventEnvelope = serde_json::from_slice(&decoded).map_err(|e| {
        (StatusCode::BAD_REQUEST, format!("invalid event envelope in message {message_id}: {e}"))
    })?;

    match projector.project(&envelope).await {
        Ok(()) => Ok(StatusCode::NO_CONTENT),
        Err(error) => {
            tracing::warn!(%error, %message_id, "pubsub_record_failed");
            Err((StatusCode::INTERNAL_SERVER_ERROR, error.to_string()))
        }
    }
}
