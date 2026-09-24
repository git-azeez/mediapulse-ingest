use super::repository;
use crate::state::AppState;
use cinderroute::model::EventEnvelope;

pub(super) async fn publish_after_commit(state: &AppState, event: &EventEnvelope) {
    let payload = match serde_json::to_string(event) {
        Ok(payload) => payload,
        Err(error) => {
            tracing::error!(%error, event_id = %event.event_id, "event_encode_failed");
            return;
        }
    };

    match state
        .sqs
        .send_message()
        .queue_url(&state.queue_url)
        .message_body(payload)
        .send()
        .await
    {
        Ok(_) => {
            if let Err(error) = repository::mark_outbox_published(&state.db, event.event_id).await {
                tracing::warn!(%error, event_id = %event.event_id, "outbox_mark_published_failed");
            }
            tracing::info!(
                event_id = %event.event_id,
                event_type = event.event_type.as_str(),
                "event_published"
            );
        }
        Err(error) => {
            let error_text = error.to_string();
            let _ = repository::record_outbox_failure(&state.db, event.event_id, &error_text).await;
            tracing::warn!(%error, event_id = %event.event_id, "event_retained_in_outbox");
        }
    }
}
