use super::{projection, publisher, repository, validation};
use crate::{
    error::{ApiError, ApiResult},
    request::{self, IDEMPOTENCY_KEY},
    state::AppState,
};
use axum::{
    Json,
    extract::{Path, State},
    http::{HeaderMap, StatusCode},
    response::{IntoResponse, Response},
};
use chrono::Utc;
use cinderroute::model::{
    CreateShipmentRequest, EVENT_SCHEMA_VERSION, EventData, EventEnvelope, EventType,
    MutationResponse, RecordCheckpointRequest,
};
use uuid::Uuid;

pub(crate) async fn create(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(input): Json<CreateShipmentRequest>,
) -> ApiResult<Response> {
    validation::create(&input)?;
    if input.expected_version != 0 {
        return Err(ApiError::conflict(
            "a new shipment requires expectedVersion=0",
        ));
    }
    let idempotency = request::required_header(&headers, IDEMPOTENCY_KEY)?;
    let correlation = request::correlation_header(&headers);

    let mut tx = state.db.begin().await.map_err(ApiError::internal)?;
    repository::lock_idempotency(&mut tx, &idempotency).await?;
    if let Some(existing) = repository::find_idempotent(&mut tx, &idempotency).await? {
        tx.commit().await.map_err(ApiError::internal)?;
        if existing.shipment_id != input.shipment_id {
            return Err(ApiError::conflict(
                "idempotency key belongs to another shipment",
            ));
        }
        return Ok(mutation_response(StatusCode::OK, existing, true));
    }

    let now = Utc::now();
    let event = EventEnvelope {
        schema_version: EVENT_SCHEMA_VERSION.to_owned(),
        event_id: Uuid::new_v4(),
        event_type: EventType::ShipmentCreated,
        aggregate_id: input.shipment_id,
        aggregate_version: 1,
        owner_id: input.owner_id.clone(),
        occurred_at: now,
        correlation_id: correlation,
        data: EventData::ShipmentCreated {
            reference: input.reference.clone(),
            origin: input.origin.clone(),
            destination: input.destination.clone(),
        },
    };

    if !repository::insert_shipment(&mut tx, &input, now).await? {
        return Err(ApiError::conflict("shipment already exists"));
    }
    repository::insert_event_and_outbox(&mut tx, &event, &idempotency).await?;
    tx.commit().await.map_err(ApiError::internal)?;
    publisher::publish_after_commit(&state, &event).await;

    Ok(mutation_response(
        StatusCode::CREATED,
        repository::ExistingMutation {
            shipment_id: input.shipment_id,
            event_id: event.event_id,
            version: 1,
        },
        false,
    ))
}

pub(crate) async fn record_checkpoint(
    State(state): State<AppState>,
    Path(shipment_id): Path<Uuid>,
    headers: HeaderMap,
    Json(input): Json<RecordCheckpointRequest>,
) -> ApiResult<Response> {
    validation::checkpoint(&input)?;
    if input.expected_version < 1 {
        return Err(ApiError::conflict(
            "checkpoint expectedVersion must be at least 1",
        ));
    }
    let idempotency = request::required_header(&headers, IDEMPOTENCY_KEY)?;
    let correlation = request::correlation_header(&headers);

    let mut tx = state.db.begin().await.map_err(ApiError::internal)?;
    repository::lock_idempotency(&mut tx, &idempotency).await?;
    if let Some(existing) = repository::find_idempotent(&mut tx, &idempotency).await? {
        tx.commit().await.map_err(ApiError::internal)?;
        if existing.shipment_id != shipment_id {
            return Err(ApiError::conflict(
                "idempotency key belongs to another shipment",
            ));
        }
        return Ok(mutation_response(StatusCode::OK, existing, true));
    }

    let current = repository::lock_shipment(&mut tx, shipment_id)
        .await?
        .ok_or_else(|| ApiError::not_found("shipment does not exist"))?;
    if current.version != input.expected_version {
        return Err(ApiError::conflict(format!(
            "expected version {}, current version is {}",
            input.expected_version, current.version
        )));
    }

    let now = Utc::now();
    let new_version = current.version + 1;
    let event = EventEnvelope {
        schema_version: EVENT_SCHEMA_VERSION.to_owned(),
        event_id: Uuid::new_v4(),
        event_type: EventType::CheckpointRecorded,
        aggregate_id: shipment_id,
        aggregate_version: new_version,
        owner_id: current.owner_id,
        occurred_at: input.occurred_at,
        correlation_id: correlation,
        data: EventData::CheckpointRecorded {
            checkpoint_id: input.checkpoint_id,
            status: input.status,
            location: input.location.clone(),
            note: input.note.clone(),
        },
    };

    repository::advance_shipment(&mut tx, shipment_id, new_version, now).await?;
    repository::insert_event_and_outbox(&mut tx, &event, &idempotency).await?;
    tx.commit().await.map_err(ApiError::internal)?;
    projection::invalidate_cache(&state, shipment_id).await;
    publisher::publish_after_commit(&state, &event).await;

    Ok(mutation_response(
        StatusCode::ACCEPTED,
        repository::ExistingMutation {
            shipment_id,
            event_id: event.event_id,
            version: new_version,
        },
        false,
    ))
}

fn mutation_response(
    status: StatusCode,
    value: repository::ExistingMutation,
    replay: bool,
) -> Response {
    (
        status,
        Json(MutationResponse {
            shipment_id: value.shipment_id,
            event_id: value.event_id,
            version: value.version,
            accepted: true,
            idempotent_replay: replay,
        }),
    )
        .into_response()
}
