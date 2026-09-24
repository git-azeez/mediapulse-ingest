use crate::{
    error::{ApiError, ApiResult},
    state::AppState,
};
use chrono::Utc;
use cinderroute::model::{EventEnvelope, ShipmentProjection};
use redis::AsyncCommands;
use serde_json::Value;
use uuid::Uuid;

pub(super) async fn load_shipment(
    state: &AppState,
    shipment_id: Uuid,
) -> ApiResult<(ShipmentProjection, &'static str)> {
    let key = cache_key(shipment_id);
    if let Ok(mut connection) = state.valkey.get_multiplexed_async_connection().await {
        let cached: redis::RedisResult<Option<String>> = connection.get(&key).await;
        if let Ok(Some(body)) = cached
            && let Ok(projection) = serde_json::from_str::<ShipmentProjection>(&body)
        {
            return Ok((projection, "cache"));
        }
    }

    let firestore_url = format!(
        "{}/v1/projects/{}/databases/{}/documents/shipments/SHIPMENT_{}_STATE",
        state.gcp_endpoint, state.project_id, state.firestore_database, shipment_id
    );

    let resp = state
        .http
        .get(&firestore_url)
        .send()
        .await
        .map_err(|error| ApiError::unavailable(format!("projection read failed: {error}")))?;
        
    if resp.status().as_u16() == 404 {
        return Err(ApiError::not_found("shipment projection is not ready"));
    }

    let body: Value = resp
        .json()
        .await
        .map_err(|error| ApiError::unavailable(format!("projection read invalid json: {error}")))?;

    let fields = body.get("fields").ok_or_else(|| ApiError::internal("missing fields in firestore document"))?;
    let projection = projection_from_fields(fields)?;

    if let Ok(mut connection) = state.valkey.get_multiplexed_async_connection().await
        && let Ok(value) = serde_json::to_string(&projection)
    {
        let _: redis::RedisResult<()> = connection
            .set_ex(&key, value, state.cache_ttl_seconds)
            .await;
    }
    Ok((projection, "projection"))
}

pub(super) async fn load_timeline(
    state: &AppState,
    shipment_id: Uuid,
) -> ApiResult<Vec<EventEnvelope>> {
    // Queries firestore collections/events using REST
    let query_url = format!(
        "{}/v1/projects/{}/databases/{}/documents:runQuery",
        state.gcp_endpoint, state.project_id, state.firestore_database
    );
    let query_payload = serde_json::json!({
        "structuredQuery": {
            "from": [{"collectionId": "events"}],
            "where": {
                "fieldFilter": {
                    "field": {"fieldPath": "shipment_id"},
                    "op": "EQUAL",
                    "value": {"stringValue": shipment_id.to_string()}
                }
            }
        }
    });

    let resp = state
        .http
        .post(&query_url)
        .json(&query_payload)
        .send()
        .await
        .map_err(|error| ApiError::unavailable(format!("timeline read failed: {error}")))?;

    let docs: Vec<Value> = resp
        .json()
        .await
        .map_err(|error| ApiError::unavailable(format!("timeline read invalid json: {error}")))?;

    let mut events = Vec::new();
    for doc in docs {
        if let Some(document) = doc.get("document") {
            if let Some(fields) = document.get("fields") {
                let raw = string_attribute(fields, "event_json")?;
                events.push(serde_json::from_str::<EventEnvelope>(raw).map_err(ApiError::internal)?);
            }
        }
    }
    if events.is_empty() {
        return Err(ApiError::not_found("shipment timeline is not ready"));
    }
    events.sort_by_key(|event| event.aggregate_version);
    Ok(events)
}

pub(super) async fn invalidate_cache(state: &AppState, shipment_id: Uuid) {
    if let Ok(mut connection) = state.valkey.get_multiplexed_async_connection().await {
        let key = cache_key(shipment_id);
        let result: redis::RedisResult<i64> = connection.del(key).await;
        if let Err(error) = result {
            tracing::warn!(%error, %shipment_id, "cache_invalidation_failed");
        }
    }
}

fn cache_key(shipment_id: Uuid) -> String {
    format!("cinderroute:shipment:{shipment_id}")
}

fn projection_from_fields(fields: &Value) -> ApiResult<ShipmentProjection> {
    Ok(ShipmentProjection {
        shipment_id: string_attribute(fields, "shipment_id")?
            .parse()
            .map_err(ApiError::internal)?,
        owner_id: string_attribute(fields, "owner_id")?.to_owned(),
        reference: string_attribute(fields, "reference")?.to_owned(),
        origin: string_attribute(fields, "origin")?.to_owned(),
        destination: string_attribute(fields, "destination")?.to_owned(),
        status: serde_json::from_value(Value::String(string_attribute(fields, "status")?.to_owned()))
            .map_err(ApiError::internal)?,
        version: number_attribute(fields, "version")?,
        updated_at: string_attribute(fields, "updated_at")?
            .parse::<chrono::DateTime<Utc>>()
            .map_err(ApiError::internal)?,
    })
}

fn string_attribute<'a>(
    fields: &'a Value,
    name: &str,
) -> ApiResult<&'a str> {
    fields.get(name)
        .and_then(|val| val.get("stringValue"))
        .and_then(|val| val.as_str())
        .ok_or_else(|| ApiError::internal(format!("projection attribute {name} is missing")))
}

fn number_attribute(fields: &Value, name: &str) -> ApiResult<i64> {
    fields.get(name)
        .and_then(|val| val.get("integerValue"))
        .and_then(|val| val.as_str())
        .ok_or_else(|| ApiError::internal(format!("projection attribute {name} is not numeric")))?
        .parse::<i64>()
        .map_err(ApiError::internal)
}
