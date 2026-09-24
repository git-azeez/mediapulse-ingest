use crate::handler::Projector;
use anyhow::{Context, Result, bail};
use aws_sdk_dynamodb::types::AttributeValue;
use cinderroute::model::{EventData, EventEnvelope, EventType};
use redis::AsyncCommands;

impl Projector {
    pub(crate) async fn project(&self, event: &EventEnvelope) -> Result<()> {
        event.validate().map_err(anyhow::Error::msg)?;
        match (&event.event_type, &event.data) {
            (
                EventType::ShipmentCreated,
                EventData::ShipmentCreated {
                    reference,
                    origin,
                    destination,
                },
            ) => {
                let result = self
                    .dynamo
                    .put_item()
                    .table_name(&self.table)
                    .item(
                        "PK",
                        AttributeValue::S(format!("SHIPMENT#{}", event.aggregate_id)),
                    )
                    .item("SK", AttributeValue::S("STATE".to_owned()))
                    .item(
                        "shipment_id",
                        AttributeValue::S(event.aggregate_id.to_string()),
                    )
                    .item("owner_id", AttributeValue::S(event.owner_id.clone()))
                    .item(
                        "GSI1PK",
                        AttributeValue::S(format!("OWNER#{}", event.owner_id)),
                    )
                    .item(
                        "GSI1SK",
                        AttributeValue::S(format!("SHIPMENT#{}", event.aggregate_id)),
                    )
                    .item("reference", AttributeValue::S(reference.clone()))
                    .item("origin", AttributeValue::S(origin.clone()))
                    .item("destination", AttributeValue::S(destination.clone()))
                    .item("status", AttributeValue::S("CREATED".to_owned()))
                    .item(
                        "version",
                        AttributeValue::N(event.aggregate_version.to_string()),
                    )
                    .item(
                        "updated_at",
                        AttributeValue::S(event.occurred_at.to_rfc3339()),
                    )
                    .condition_expression("attribute_not_exists(PK) AND attribute_not_exists(SK)")
                    .send()
                    .await;
                match result {
                    Ok(_) => {}
                    Err(error) if is_conditional_failure(&error) => {
                        if self.state_version(event.aggregate_id).await?.is_none() {
                            bail!("create state was rejected but no state projection exists");
                        }
                        tracing::info!("duplicate ShipmentCreated state ignored");
                    }
                    Err(error) => return Err(anyhow::anyhow!("create state failed: {error}")),
                }
            }
            (EventType::CheckpointRecorded, EventData::CheckpointRecorded { status, .. }) => {
                let previous_version = event.aggregate_version - 1;
                let result = self
                    .dynamo
                    .update_item()
                    .table_name(&self.table)
                    .key(
                        "PK",
                        AttributeValue::S(format!("SHIPMENT#{}", event.aggregate_id)),
                    )
                    .key("SK", AttributeValue::S("STATE".to_owned()))
                    .update_expression(
                        "SET #status=:status, #version=:version, updated_at=:updated",
                    )
                    .condition_expression("attribute_exists(PK) AND #version = :previous")
                    .expression_attribute_names("#status", "status")
                    .expression_attribute_names("#version", "version")
                    .expression_attribute_values(
                        ":status",
                        AttributeValue::S(status.as_str().to_owned()),
                    )
                    .expression_attribute_values(
                        ":version",
                        AttributeValue::N(event.aggregate_version.to_string()),
                    )
                    .expression_attribute_values(
                        ":previous",
                        AttributeValue::N(previous_version.to_string()),
                    )
                    .expression_attribute_values(
                        ":updated",
                        AttributeValue::S(event.occurred_at.to_rfc3339()),
                    )
                    .send()
                    .await;
                match result {
                    Ok(_) => {}
                    Err(error) if is_conditional_failure(&error) => {
                        let current = self.state_version(event.aggregate_id).await?;
                        if current.is_some_and(|version| version >= event.aggregate_version) {
                            tracing::info!(
                                current_version = current,
                                event_version = event.aggregate_version,
                                "duplicate_or_stale_state_event_ignored"
                            );
                        } else {
                            bail!(
                                "projection gap: state is at {current:?}, event {} requires previous version {previous_version}",
                                event.aggregate_version
                            );
                        }
                    }
                    Err(error) => return Err(anyhow::anyhow!("advance state failed: {error}")),
                }
            }
            _ => bail!("eventType and data.kind do not match"),
        }

        let event_json = serde_json::to_string(event)?;
        let timeline_result = self
            .dynamo
            .put_item()
            .table_name(&self.table)
            .item(
                "PK",
                AttributeValue::S(format!("SHIPMENT#{}", event.aggregate_id)),
            )
            .item(
                "SK",
                AttributeValue::S(format!("EVENT#{:020}", event.aggregate_version)),
            )
            .item("event_id", AttributeValue::S(event.event_id.to_string()))
            .item(
                "event_type",
                AttributeValue::S(event.event_type.as_str().to_owned()),
            )
            .item(
                "version",
                AttributeValue::N(event.aggregate_version.to_string()),
            )
            .item("event_json", AttributeValue::S(event_json))
            .condition_expression("attribute_not_exists(PK) AND attribute_not_exists(SK)")
            .send()
            .await;
        ignore_conditional(timeline_result, "append timeline")?;

        let key = format!("cinderroute:shipment:{}", event.aggregate_id);
        match self.valkey.get_multiplexed_async_connection().await {
            Ok(mut connection) => {
                if let Err(error) = connection.del::<_, i64>(&key).await {
                    tracing::warn!(%error, %key, "projection_cache_invalidation_failed");
                }
            }
            Err(error) => {
                tracing::warn!(%error, %key, "projection_cache_unavailable");
            }
        }
        tracing::info!(
            event_id = %event.event_id,
            shipment_id = %event.aggregate_id,
            event_type = event.event_type.as_str(),
            version = event.aggregate_version,
            "event_projected"
        );
        Ok(())
    }

    async fn state_version(&self, shipment_id: uuid::Uuid) -> Result<Option<i64>> {
        let output = self
            .dynamo
            .get_item()
            .table_name(&self.table)
            .key("PK", AttributeValue::S(format!("SHIPMENT#{shipment_id}")))
            .key("SK", AttributeValue::S("STATE".to_owned()))
            .consistent_read(true)
            .send()
            .await
            .context("read current state version")?;
        output.item().map(state_version_from_item).transpose()
    }
}

fn state_version_from_item(
    item: &std::collections::HashMap<String, AttributeValue>,
) -> Result<i64> {
    item.get("version")
        .and_then(|value| value.as_n().ok())
        .context("state projection version must be a DynamoDB number")?
        .parse::<i64>()
        .context("state projection version must be an integer")
}

fn is_conditional_failure(error: &impl std::fmt::Display) -> bool {
    error.to_string().contains("ConditionalCheckFailed")
}

fn ignore_conditional<T, E: std::fmt::Display>(
    result: Result<T, E>,
    operation: &str,
) -> Result<()> {
    match result {
        Ok(_) => Ok(()),
        Err(error) if is_conditional_failure(&error) => {
            tracing::info!(%operation, "duplicate_or_stale_event_ignored");
            Ok(())
        }
        Err(error) => Err(anyhow::anyhow!("{operation} failed: {error}")),
    }
}
