use anyhow::Result;
use axum::{extract::State, Json, http::StatusCode, response::IntoResponse};
use reqwest::Client;
use serde_json::{Value, json};
use sqlx::{PgPool, Row};
use uuid::Uuid;

#[derive(Clone)]
pub(crate) struct Relay {
    db: PgPool,
    http: Client,
    gcp_endpoint: String,
    project_id: String,
    pubsub_topic: String,
}

impl Relay {
    pub(crate) fn new(db: PgPool, http: Client, gcp_endpoint: String, project_id: String, pubsub_topic: String) -> Self {
        Self { db, http, gcp_endpoint, project_id, pubsub_topic }
    }
}

pub(crate) async fn handle_trigger(State(relay): State<Relay>) -> impl IntoResponse {
    match relay.process_outbox().await {
        Ok(result) => (StatusCode::OK, Json(result)),
        Err(error) => {
            tracing::error!(%error, "outbox_processing_failed");
            (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({"error": error.to_string()})))
        }
    }
}

impl Relay {
    async fn process_outbox(&self) -> Result<Value> {
        let mut tx = self.db.begin().await?;
        let rows = sqlx::query(
            "SELECT event_id, payload FROM cinderroute.outbox
             WHERE published_at IS NULL ORDER BY sequence_number LIMIT 100
             FOR UPDATE SKIP LOCKED",
        )
        .fetch_all(&mut *tx)
        .await?;

        let mut published = 0usize;
        for row in rows {
            let event_id: Uuid = row.get("event_id");
            let payload: Value = row.get("payload");
            
            use base64::Engine;
            let b64_data = base64::engine::general_purpose::STANDARD.encode(payload.to_string().as_bytes());
            
            let pubsub_url = format!(
                "{}/v1/projects/{}/topics/{}:publish",
                self.gcp_endpoint, self.project_id, self.pubsub_topic
            );
            let request_body = json!({
                "messages": [
                    {
                        "data": b64_data
                    }
                ]
            });

            match self.http.post(&pubsub_url).json(&request_body).send().await {
                Ok(resp) if resp.status().is_success() => {
                    sqlx::query(
                        "UPDATE cinderroute.outbox SET published_at=now(), attempts=attempts+1,
                         last_error=NULL WHERE event_id=$1 AND published_at IS NULL",
                    )
                    .bind(event_id)
                    .execute(&mut *tx)
                    .await?;
                    tracing::info!(%event_id, "outbox_event_published");
                    published += 1;
                }
                Ok(resp) => {
                    let error_text = format!("pubsub status {}", resp.status());
                    sqlx::query(
                        "UPDATE cinderroute.outbox SET attempts=attempts+1, last_error=$2
                         WHERE event_id=$1 AND published_at IS NULL",
                    )
                    .bind(event_id)
                    .bind(error_text.chars().take(2000).collect::<String>())
                    .execute(&mut *tx)
                    .await?;
                    tx.commit().await?;
                    return Err(anyhow::anyhow!("publish pending outbox event HTTP error").context(error_text));
                }
                Err(error) => {
                    let error_text = error.to_string();
                    sqlx::query(
                        "UPDATE cinderroute.outbox SET attempts=attempts+1, last_error=$2
                         WHERE event_id=$1 AND published_at IS NULL",
                    )
                    .bind(event_id)
                    .bind(error_text.chars().take(2000).collect::<String>())
                    .execute(&mut *tx)
                    .await?;
                    tx.commit().await?;
                    return Err(anyhow::anyhow!(error).context("publish pending outbox event"));
                }
            }
        }
        tx.commit().await?;
        let remaining: i64 = sqlx::query_scalar(
            "SELECT count(*) FROM cinderroute.outbox WHERE published_at IS NULL",
        )
        .fetch_one(&self.db)
        .await?;
        Ok(json!({"published": published, "remaining": remaining}))
    }
}
