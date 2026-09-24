use anyhow::Result;
use aws_sdk_sqs::Client as SqsClient;
use lambda_runtime::{Error as LambdaError, LambdaEvent};
use serde_json::{Value, json};
use sqlx::{PgPool, Row};
use uuid::Uuid;

#[derive(Clone)]
pub(crate) struct Relay {
    db: PgPool,
    sqs: SqsClient,
    queue_url: String,
}

impl Relay {
    pub(crate) fn new(db: PgPool, sqs: SqsClient, queue_url: String) -> Self {
        Self { db, sqs, queue_url }
    }

    pub(crate) async fn handle(&self, _event: LambdaEvent<Value>) -> Result<Value, LambdaError> {
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
            match self
                .sqs
                .send_message()
                .queue_url(&self.queue_url)
                .message_body(payload.to_string())
                .send()
                .await
            {
                Ok(_) => {
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
                    return Err(anyhow::anyhow!(error)
                        .context("publish pending outbox event")
                        .into());
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
