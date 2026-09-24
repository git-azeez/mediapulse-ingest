use super::{projection, repository};
use crate::{
    error::{ApiError, ApiResult},
    request,
    state::AppState,
};
use axum::{
    Json,
    extract::{Path, State},
    http::{HeaderValue, StatusCode},
    response::{IntoResponse, Response},
};
use cinderroute::model::{RebuildResponse, ShipmentProjection, TimelineResponse};
use uuid::Uuid;

pub(crate) async fn get(
    State(state): State<AppState>,
    Path(shipment_id): Path<Uuid>,
) -> ApiResult<Response> {
    let (shipment, source) = projection::load_shipment(&state, shipment_id).await?;
    projection_response(&state, shipment, source)
}

pub(crate) async fn timeline(
    State(state): State<AppState>,
    Path(shipment_id): Path<Uuid>,
) -> ApiResult<Response> {
    let events = projection::load_timeline(&state, shipment_id).await?;
    let version = events
        .last()
        .map(|event| event.aggregate_version)
        .unwrap_or(0);
    let mut headers = request::evidence_headers(&state, "projection", version)?;
    headers.insert("content-type", HeaderValue::from_static("application/json"));
    Ok((
        StatusCode::OK,
        headers,
        Json(TimelineResponse {
            shipment_id,
            version,
            events,
        }),
    )
        .into_response())
}

pub(crate) async fn rebuild_projection(
    State(state): State<AppState>,
    Path(shipment_id): Path<Uuid>,
) -> ApiResult<Response> {
    let events = repository::events_for_rebuild(&state.db, shipment_id).await?;
    if events.is_empty() {
        return Err(ApiError::not_found("shipment does not exist"));
    }
    let pubsub_url = format!(
        "{}/v1/projects/{}/topics/{}:publish",
        state.gcp_endpoint, state.project_id, state.pubsub_topic
    );
    for payload in &events {
        use base64::Engine;
        let b64_data =
            base64::engine::general_purpose::STANDARD.encode(payload.to_string().as_bytes());
        let body = serde_json::json!({"messages": [{"data": b64_data}]});
        state
            .http
            .post(&pubsub_url)
            .json(&body)
            .send()
            .await
            .map_err(|e| ApiError::unavailable(format!("rebuild enqueue failed: {e}")))?
            .error_for_status()
            .map_err(|e| ApiError::unavailable(format!("rebuild enqueue failed: {e}")))?;
    }
    projection::invalidate_cache(&state, shipment_id).await;
    Ok((
        StatusCode::ACCEPTED,
        Json(RebuildResponse {
            shipment_id,
            requeued: events.len(),
        }),
    )
        .into_response())
}

fn projection_response(
    state: &AppState,
    projection: ShipmentProjection,
    source: &'static str,
) -> ApiResult<Response> {
    let headers = request::evidence_headers(state, source, projection.version)?;
    Ok((StatusCode::OK, headers, Json(projection)).into_response())
}
