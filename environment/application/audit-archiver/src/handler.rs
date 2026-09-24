use crate::{batch::AuditBatch, repository, storage};
use axum::{extract::State, Json, http::StatusCode, response::IntoResponse};
use reqwest::Client;
use serde_json::{Value, json};
use sqlx::PgPool;

#[derive(Clone)]
pub(crate) struct Archiver {
    db: PgPool,
    pub(crate) http: Client,
    pub(crate) gcp_endpoint: String,
    pub(crate) bucket: String,
    pub(crate) prefix: String,
}

impl Archiver {
    pub(crate) fn new(db: PgPool, http: Client, gcp_endpoint: String, bucket: String, prefix: String) -> Self {
        Self {
            db,
            http,
            gcp_endpoint,
            bucket,
            prefix,
        }
    }
}

pub(crate) async fn handle_trigger(State(archiver): State<Archiver>) -> impl IntoResponse {
    match archiver.archive().await {
        Ok(result) => (StatusCode::OK, Json(result)),
        Err(error) => {
            tracing::error!(%error, "archive_processing_failed");
            (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({"error": error.to_string()})))
        }
    }
}

impl Archiver {
    async fn archive(&self) -> anyhow::Result<Value> {
        let events = repository::find_pending(&self.db).await?;
        if events.is_empty() {
            return Ok(json!({"archived": 0, "objectKey": null}));
        }

        let batch = AuditBatch::from_events(events, &self.prefix)?;
        storage::upload(&self, &batch).await?;
        repository::mark_archived(&self.db, &batch.event_ids, &batch.object_key).await?;

        tracing::info!(
            archived = batch.archived_count(),
            object_key = %batch.object_key,
            sha256 = %batch.checksum,
            "audit_batch_archived"
        );
        Ok(json!({
            "archived": batch.archived_count(),
            "objectKey": batch.object_key,
            "sha256": batch.checksum,
            "firstSequence": batch.first_sequence,
            "lastSequence": batch.last_sequence
        }))
    }
}
