use crate::{batch::AuditBatch, repository, storage};
use aws_sdk_s3::Client as S3Client;
use lambda_runtime::{Error as LambdaError, LambdaEvent};
use serde_json::{Value, json};
use sqlx::PgPool;

#[derive(Clone)]
pub(crate) struct Archiver {
    db: PgPool,
    s3: S3Client,
    bucket: String,
    prefix: String,
}

impl Archiver {
    pub(crate) fn new(db: PgPool, s3: S3Client, bucket: String, prefix: String) -> Self {
        Self {
            db,
            s3,
            bucket,
            prefix,
        }
    }

    pub(crate) async fn handle(&self, _event: LambdaEvent<Value>) -> Result<Value, LambdaError> {
        let events = repository::find_pending(&self.db).await?;
        if events.is_empty() {
            return Ok(json!({"archived": 0, "objectKey": null}));
        }

        let batch = AuditBatch::from_events(events, &self.prefix)?;
        storage::upload(&self.s3, &self.bucket, &batch).await?;
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
