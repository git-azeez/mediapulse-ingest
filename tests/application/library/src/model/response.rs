use super::event::EventEnvelope;
use serde::Serialize;
use std::collections::BTreeMap;
use uuid::Uuid;

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct MutationResponse {
    pub shipment_id: Uuid,
    pub event_id: Uuid,
    pub version: i64,
    pub accepted: bool,
    pub idempotent_replay: bool,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TimelineResponse {
    pub shipment_id: Uuid,
    pub version: i64,
    pub events: Vec<EventEnvelope>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RebuildResponse {
    pub shipment_id: Uuid,
    pub requeued: usize,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct HealthResponse {
    pub status: &'static str,
    pub service: &'static str,
    pub instance: String,
    pub checks: BTreeMap<&'static str, &'static str>,
}
