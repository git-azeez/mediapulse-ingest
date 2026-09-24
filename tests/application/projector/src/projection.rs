use crate::handler::Projector;
use anyhow::{Context, Result, bail};
use cinderroute::model::{EventData, EventEnvelope, EventType};
use redis::AsyncCommands;
use serde_json::{json, Value};

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
                let doc_id = format!("SHIPMENT_{}_STATE", event.aggregate_id);
                let firestore_url = format!(
                    "{}/v1/projects/{}/databases/{}/documents/shipments?documentId={}",
                    self.gcp_endpoint, self.project_id, self.database, doc_id
                );

                let payload = json!({
                    "fields": {
                        "PK": { "stringValue": format!("SHIPMENT#{}", event.aggregate_id) },
                        "SK": { "stringValue": "STATE" },
                        "shipment_id": { "stringValue": event.aggregate_id.to_string() },
                        "owner_id": { "stringValue": event.owner_id.clone() },
                        "GSI1PK": { "stringValue": format!("OWNER#{}", event.owner_id) },
                        "GSI1SK": { "stringValue": format!("SHIPMENT#{}", event.aggregate_id) },
                        "reference": { "stringValue": reference.clone() },
                        "origin": { "stringValue": origin.clone() },
                        "destination": { "stringValue": destination.clone() },
                        "status": { "stringValue": "CREATED" },
                        "version": { "integerValue": event.aggregate_version.to_string() },
                        "updated_at": { "stringValue": event.occurred_at.to_rfc3339() }
                    }
                });

                let result = self.http.post(&firestore_url).json(&payload).send().await;
                match result {
                    Ok(resp) if resp.status().is_success() => {}
                    Ok(resp) if resp.status() == 409 => {
                        if self.state_version(event.aggregate_id).await?.is_none() {
                            bail!("create state was rejected but no state projection exists");
                        }
                        tracing::info!("duplicate ShipmentCreated state ignored");
                    }
                    Ok(resp) => return Err(anyhow::anyhow!("create state failed: HTTP {}", resp.status())),
                    Err(error) => return Err(anyhow::anyhow!("create state failed: {error}")),
                }
            }
            (EventType::CheckpointRecorded, EventData::CheckpointRecorded { status, .. }) => {
                let previous_version = event.aggregate_version - 1;
                let doc_id = format!("SHIPMENT_{}_STATE", event.aggregate_id);
                let firestore_url = format!(
                    "{}/v1/projects/{}/databases/{}/documents/shipments/{}?updateMask=status,version,updated_at&currentDocument.exists=true",
                    self.gcp_endpoint, self.project_id, self.database, doc_id
                );

                let current = self.state_version(event.aggregate_id).await?;
                if let Some(version) = current {
                    if version != previous_version {
                        if version >= event.aggregate_version {
                            tracing::info!(
                                current_version = version,
                                event_version = event.aggregate_version,
                                "duplicate_or_stale_state_event_ignored"
                            );
                        } else {
                            bail!(
                                "projection gap: state is at {version:?}, event {} requires previous version {previous_version}",
                                event.aggregate_version
                            );
                        }
                    } else {
                        let payload = json!({
                            "fields": {
                                "status": { "stringValue": status.as_str() },
                                "version": { "integerValue": event.aggregate_version.to_string() },
                                "updated_at": { "stringValue": event.occurred_at.to_rfc3339() }
                            }
                        });

                        let result = self.http.patch(&firestore_url).json(&payload).send().await;
                        match result {
                            Ok(resp) if resp.status().is_success() => {}
                            Ok(resp) => return Err(anyhow::anyhow!("advance state failed: HTTP {}", resp.status())),
                            Err(error) => return Err(anyhow::anyhow!("advance state failed: {error}")),
                        }
                    }
                } else {
                     bail!("projection gap: state not found");
                }
            }
            _ => bail!("eventType and data.kind do not match"),
        }

        let event_json = serde_json::to_string(event)?;
        let doc_id = format!("SHIPMENT_{}_EVENT_{:020}", event.aggregate_id, event.aggregate_version);
        let timeline_url = format!(
            "{}/v1/projects/{}/databases/{}/documents/events?documentId={}",
            self.gcp_endpoint, self.project_id, self.database, doc_id
        );
        let payload = json!({
            "fields": {
                "PK": { "stringValue": format!("SHIPMENT#{}", event.aggregate_id) },
                "SK": { "stringValue": format!("EVENT#{:020}", event.aggregate_version) },
                "shipment_id": { "stringValue": event.aggregate_id.to_string() },
                "event_id": { "stringValue": event.event_id.to_string() },
                "event_type": { "stringValue": event.event_type.as_str() },
                "version": { "integerValue": event.aggregate_version.to_string() },
                "event_json": { "stringValue": event_json }
            }
        });
        
        let timeline_result = self.http.post(&timeline_url).json(&payload).send().await;
        match timeline_result {
            Ok(resp) if resp.status().is_success() || resp.status() == 409 => {}
            Ok(resp) => return Err(anyhow::anyhow!("append timeline failed: HTTP {}", resp.status())),
            Err(error) => return Err(anyhow::anyhow!("append timeline failed: {error}")),
        }

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
        let doc_id = format!("SHIPMENT_{}_STATE", shipment_id);
        let firestore_url = format!(
            "{}/v1/projects/{}/databases/{}/documents/shipments/{}",
            self.gcp_endpoint, self.project_id, self.database, doc_id
        );

        let resp = self.http.get(&firestore_url).send().await.context("read current state version")?;
        
        if resp.status().as_u16() == 404 {
            return Ok(None);
        }
        
        let body: Value = resp.json().await?;
        if let Some(fields) = body.get("fields") {
            if let Some(version_field) = fields.get("version") {
                if let Some(version_str) = version_field.get("integerValue").and_then(|v| v.as_str()) {
                    return Ok(Some(version_str.parse::<i64>()?));
                }
            }
        }
        Ok(None)
    }
}
