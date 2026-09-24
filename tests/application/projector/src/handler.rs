use anyhow::Context;
use aws_sdk_dynamodb::Client as DynamoClient;
use cinderroute::model::EventEnvelope;
use lambda_runtime::{Error as LambdaError, LambdaEvent};
use serde_json::{Value, json};

#[derive(Clone)]
pub(crate) struct Projector {
    pub(crate) dynamo: DynamoClient,
    pub(crate) table: String,
    pub(crate) valkey: redis::Client,
}

impl Projector {
    pub(crate) fn new(dynamo: DynamoClient, table: String, valkey: redis::Client) -> Self {
        Self {
            dynamo,
            table,
            valkey,
        }
    }

    pub(crate) async fn handle(&self, event: LambdaEvent<Value>) -> Result<Value, LambdaError> {
        let records = event
            .payload
            .get("Records")
            .and_then(Value::as_array)
            .context("SQS event must contain a Records array")?;
        let mut processed = 0usize;
        let mut batch_item_failures = Vec::new();

        for record in records {
            let message_id = record
                .get("messageId")
                .and_then(Value::as_str)
                .context("SQS record must contain a messageId")?
                .to_owned();
            let result = async {
                let body = record
                    .get("body")
                    .and_then(Value::as_str)
                    .context("SQS record body must be a string")?;
                let envelope: EventEnvelope = serde_json::from_str(body).with_context(|| {
                    format!("invalid event envelope in SQS message {message_id}")
                })?;
                self.project(&envelope).await
            }
            .await;

            match result {
                Ok(()) => processed += 1,
                Err(error) => {
                    tracing::warn!(%error, %message_id, "sqs_record_failed");
                    batch_item_failures.push(json!({"itemIdentifier": message_id}));
                }
            }
        }

        Ok(json!({
            "processed": processed,
            "failed": batch_item_failures.len(),
            "batchItemFailures": batch_item_failures
        }))
    }
}
