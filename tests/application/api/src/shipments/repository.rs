use crate::error::{ApiError, ApiResult};
use chrono::{DateTime, Utc};
use cinderroute::model::{CreateShipmentRequest, EventEnvelope};
use serde_json::Value;
use sqlx::{PgPool, Row};
use uuid::Uuid;

#[derive(Clone, Copy)]
pub(super) struct ExistingMutation {
    pub(super) shipment_id: Uuid,
    pub(super) event_id: Uuid,
    pub(super) version: i64,
}

pub(super) struct ShipmentVersion {
    pub(super) owner_id: String,
    pub(super) version: i64,
}

pub(super) async fn lock_idempotency(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    key: &str,
) -> ApiResult<()> {
    sqlx::query("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))")
        .bind(key)
        .execute(&mut **tx)
        .await
        .map_err(ApiError::internal)?;
    Ok(())
}

pub(super) async fn find_idempotent(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    key: &str,
) -> ApiResult<Option<ExistingMutation>> {
    let row = sqlx::query(
        "SELECT shipment_id, event_id, aggregate_version
         FROM cinderroute.events WHERE idempotency_key=$1",
    )
    .bind(key)
    .fetch_optional(&mut **tx)
    .await
    .map_err(ApiError::internal)?;
    Ok(row.map(|row| ExistingMutation {
        shipment_id: row.get("shipment_id"),
        event_id: row.get("event_id"),
        version: row.get("aggregate_version"),
    }))
}

pub(super) async fn insert_shipment(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    input: &CreateShipmentRequest,
    now: DateTime<Utc>,
) -> ApiResult<bool> {
    let result = sqlx::query(
        "INSERT INTO cinderroute.shipments
         (shipment_id, owner_id, reference, origin, destination, version, created_at, updated_at)
         VALUES ($1, $2, $3, $4, $5, 1, $6, $6)
         ON CONFLICT (shipment_id) DO NOTHING",
    )
    .bind(input.shipment_id)
    .bind(&input.owner_id)
    .bind(&input.reference)
    .bind(&input.origin)
    .bind(&input.destination)
    .bind(now)
    .execute(&mut **tx)
    .await
    .map_err(ApiError::internal)?;
    Ok(result.rows_affected() == 1)
}

pub(super) async fn lock_shipment(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    shipment_id: Uuid,
) -> ApiResult<Option<ShipmentVersion>> {
    let row = sqlx::query(
        "SELECT owner_id, version FROM cinderroute.shipments
         WHERE shipment_id=$1 FOR UPDATE",
    )
    .bind(shipment_id)
    .fetch_optional(&mut **tx)
    .await
    .map_err(ApiError::internal)?;
    Ok(row.map(|row| ShipmentVersion {
        owner_id: row.get("owner_id"),
        version: row.get("version"),
    }))
}

pub(super) async fn advance_shipment(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    shipment_id: Uuid,
    version: i64,
    now: DateTime<Utc>,
) -> ApiResult<()> {
    sqlx::query("UPDATE cinderroute.shipments SET version=$2, updated_at=$3 WHERE shipment_id=$1")
        .bind(shipment_id)
        .bind(version)
        .bind(now)
        .execute(&mut **tx)
        .await
        .map_err(ApiError::internal)?;
    Ok(())
}

pub(super) async fn insert_event_and_outbox(
    tx: &mut sqlx::Transaction<'_, sqlx::Postgres>,
    event: &EventEnvelope,
    idempotency_key: &str,
) -> ApiResult<()> {
    let payload = serde_json::to_value(event).map_err(ApiError::internal)?;
    let row = sqlx::query(
        "INSERT INTO cinderroute.events
         (event_id, shipment_id, aggregate_version, event_type, idempotency_key,
          correlation_id, payload, created_at)
         VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
         RETURNING sequence_number",
    )
    .bind(event.event_id)
    .bind(event.aggregate_id)
    .bind(event.aggregate_version)
    .bind(event.event_type.as_str())
    .bind(idempotency_key)
    .bind(&event.correlation_id)
    .bind(&payload)
    .bind(event.occurred_at)
    .fetch_one(&mut **tx)
    .await
    .map_err(ApiError::internal)?;
    let sequence: i64 = row.get("sequence_number");

    sqlx::query(
        "INSERT INTO cinderroute.outbox
         (event_id, sequence_number, payload, created_at) VALUES ($1,$2,$3,$4)",
    )
    .bind(event.event_id)
    .bind(sequence)
    .bind(payload)
    .bind(event.occurred_at)
    .execute(&mut **tx)
    .await
    .map_err(ApiError::internal)?;
    Ok(())
}

pub(super) async fn events_for_rebuild(db: &PgPool, shipment_id: Uuid) -> ApiResult<Vec<Value>> {
    let rows = sqlx::query(
        "SELECT payload FROM cinderroute.events
         WHERE shipment_id=$1 ORDER BY aggregate_version",
    )
    .bind(shipment_id)
    .fetch_all(db)
    .await
    .map_err(ApiError::internal)?;
    Ok(rows
        .into_iter()
        .map(|row| row.get::<Value, _>("payload"))
        .collect())
}

pub(super) async fn mark_outbox_published(db: &PgPool, event_id: Uuid) -> Result<(), sqlx::Error> {
    sqlx::query(
        "UPDATE cinderroute.outbox SET published_at=now(), attempts=attempts+1,
         last_error=NULL WHERE event_id=$1 AND published_at IS NULL",
    )
    .bind(event_id)
    .execute(db)
    .await?;
    Ok(())
}

pub(super) async fn record_outbox_failure(
    db: &PgPool,
    event_id: Uuid,
    error: &str,
) -> Result<(), sqlx::Error> {
    sqlx::query(
        "UPDATE cinderroute.outbox SET attempts=attempts+1, last_error=$2
         WHERE event_id=$1 AND published_at IS NULL",
    )
    .bind(event_id)
    .bind(error.chars().take(2000).collect::<String>())
    .execute(db)
    .await?;
    Ok(())
}
