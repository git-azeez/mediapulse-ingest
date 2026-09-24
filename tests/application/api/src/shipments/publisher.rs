use super::repository;
use crate::state::AppState;
use cinderroute::model::EventEnvelope;
use serde_json::json;

pub(super) async fn publish_after_commit(state: &AppState, event: &EventEnvelope) {
    let payload = match serde_json::to_string(event) {
        Ok(payload) => payload,
        Err(error) => {
            tracing::error!(%error, event_id = %event.event_id, "event_encode_failed");
            return;
        }
    };

    use base64::Engine;
    let b64_data = base64::engine::general_purpose::STANDARD.encode(payload.as_bytes());
    let pubsub_url = format!(
        "{}/v1/projects/{}/topics/{}:publish",
        state.gcp_endpoint, state.project_id, state.pubsub_topic
    );

    let request_body = json!({
        "messages": [
            {
                "data": b64_data
            }
        ]
    });

    match state.http.post(&pubsub_url).json(&request_body).send().await {
        Ok(resp) if resp.status().is_success() => {
            if let Err(error) = repository::mark_outbox_published(&state.db, event.event_id).await {
                tracing::warn!(%error, event_id = %event.event_id, "outbox_mark_published_failed");
            }
            tracing::info!(
                event_id = %event.event_id,
                event_type = event.event_type.as_str(),
                "event_published"
            );
        }
        Ok(resp) => {
            let error_text = format!("pubsub status {}", resp.status());
            let _ = repository::record_outbox_failure(&state.db, event.event_id, &error_text).await;
            tracing::warn!(%error_text, event_id = %event.event_id, "event_retained_in_outbox");
        }
        Err(error) => {
            let error_text = error.to_string();
            let _ = repository::record_outbox_failure(&state.db, event.event_id, &error_text).await;
            tracing::warn!(%error, event_id = %event.event_id, "event_retained_in_outbox");
        }
    }
}
