use lambda_runtime::Error as LambdaError;
use serde_json::Value;
use sha2::{Digest, Sha256};
use uuid::Uuid;

pub(crate) struct PendingEvent {
    pub(crate) sequence_number: i64,
    pub(crate) event_id: Uuid,
    pub(crate) payload: Value,
}

pub(crate) struct AuditBatch {
    pub(crate) event_ids: Vec<Uuid>,
    pub(crate) first_sequence: i64,
    pub(crate) last_sequence: i64,
    pub(crate) ndjson: Vec<u8>,
    pub(crate) checksum: String,
    pub(crate) object_key: String,
}

impl AuditBatch {
    pub(crate) fn from_events(
        events: Vec<PendingEvent>,
        prefix: &str,
    ) -> Result<Self, LambdaError> {
        let first_sequence = events
            .first()
            .ok_or_else(|| std::io::Error::other("cannot archive an empty batch"))?
            .sequence_number;
        let last_sequence = events
            .last()
            .ok_or_else(|| std::io::Error::other("cannot archive an empty batch"))?
            .sequence_number;

        let mut event_ids = Vec::with_capacity(events.len());
        let mut ndjson = Vec::new();
        for event in events {
            event_ids.push(event.event_id);
            serde_json::to_writer(&mut ndjson, &event.payload)?;
            ndjson.push(b'\n');
        }

        let checksum = format!("{:x}", Sha256::digest(&ndjson));
        let object_key = format!(
            "{}batch-{first_sequence:020}-{last_sequence:020}-{}.ndjson",
            prefix.trim_start_matches('/'),
            &checksum[..16]
        );

        Ok(Self {
            event_ids,
            first_sequence,
            last_sequence,
            ndjson,
            checksum,
            object_key,
        })
    }

    pub(crate) fn archived_count(&self) -> usize {
        self.event_ids.len()
    }
}
