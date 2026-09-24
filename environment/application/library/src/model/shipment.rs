use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ShipmentStatus {
    Created,
    PickedUp,
    InTransit,
    AtHub,
    OutForDelivery,
    Delivered,
    Exception,
}

impl ShipmentStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Created => "CREATED",
            Self::PickedUp => "PICKED_UP",
            Self::InTransit => "IN_TRANSIT",
            Self::AtHub => "AT_HUB",
            Self::OutForDelivery => "OUT_FOR_DELIVERY",
            Self::Delivered => "DELIVERED",
            Self::Exception => "EXCEPTION",
        }
    }
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct CreateShipmentRequest {
    pub shipment_id: Uuid,
    pub owner_id: String,
    pub reference: String,
    pub origin: String,
    pub destination: String,
    pub expected_version: i64,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct RecordCheckpointRequest {
    pub checkpoint_id: Uuid,
    pub status: ShipmentStatus,
    pub location: String,
    pub note: Option<String>,
    pub occurred_at: DateTime<Utc>,
    pub expected_version: i64,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ShipmentProjection {
    pub shipment_id: Uuid,
    pub owner_id: String,
    pub reference: String,
    pub origin: String,
    pub destination: String,
    pub status: ShipmentStatus,
    pub version: i64,
    pub updated_at: DateTime<Utc>,
}
