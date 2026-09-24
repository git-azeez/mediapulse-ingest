use super::shipment::ShipmentStatus;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

pub const EVENT_SCHEMA_VERSION: &str = "1.0";

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct EventEnvelope {
    pub schema_version: String,
    pub event_id: Uuid,
    pub event_type: EventType,
    pub aggregate_id: Uuid,
    pub aggregate_version: i64,
    pub owner_id: String,
    pub occurred_at: DateTime<Utc>,
    pub correlation_id: String,
    pub data: EventData,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum EventType {
    ShipmentCreated,
    CheckpointRecorded,
}

impl EventType {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::ShipmentCreated => "ShipmentCreated",
            Self::CheckpointRecorded => "CheckpointRecorded",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "camelCase", deny_unknown_fields)]
pub enum EventData {
    ShipmentCreated {
        reference: String,
        origin: String,
        destination: String,
    },
    CheckpointRecorded {
        checkpoint_id: Uuid,
        status: ShipmentStatus,
        location: String,
        note: Option<String>,
    },
}

impl EventEnvelope {
    pub fn validate(&self) -> Result<(), String> {
        if self.schema_version != EVENT_SCHEMA_VERSION {
            return Err("unsupported schema version".to_owned());
        }
        if self.aggregate_version <= 0 {
            return Err("aggregate version must be positive".to_owned());
        }
        bounded("ownerId", &self.owner_id, 1, 128)?;
        bounded("correlationId", &self.correlation_id, 1, 200)?;

        match (&self.event_type, &self.data) {
            (
                EventType::ShipmentCreated,
                EventData::ShipmentCreated {
                    reference,
                    origin,
                    destination,
                },
            ) => {
                if self.aggregate_version != 1 {
                    return Err("ShipmentCreated must have aggregateVersion=1".to_owned());
                }
                bounded("reference", reference, 1, 128)?;
                bounded("origin", origin, 1, 256)?;
                bounded("destination", destination, 1, 256)?;
            }
            (
                EventType::CheckpointRecorded,
                EventData::CheckpointRecorded {
                    status,
                    location,
                    note,
                    ..
                },
            ) => {
                if self.aggregate_version < 2 {
                    return Err("CheckpointRecorded requires aggregateVersion>=2".to_owned());
                }
                if *status == ShipmentStatus::Created {
                    return Err("CREATED is not a checkpoint status".to_owned());
                }
                bounded("location", location, 1, 256)?;
                if let Some(note) = note {
                    bounded("note", note, 0, 1000)?;
                }
            }
            _ => return Err("eventType and data.kind do not match".to_owned()),
        }
        Ok(())
    }
}

fn bounded(name: &str, value: &str, min: usize, max: usize) -> Result<(), String> {
    let len = value.chars().count();
    if len < min || len > max {
        return Err(format!("{name} length must be between {min} and {max}"));
    }
    Ok(())
}
