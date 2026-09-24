use crate::{
    error::{ApiError, ApiResult},
    state::AppState,
};
use aws_sdk_dynamodb::types::AttributeValue;
use chrono::Utc;
use cinderroute::model::{EventEnvelope, ShipmentProjection};
use redis::AsyncCommands;
use serde_json::Value;
use std::collections::HashMap;
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

    let output = state
        .dynamo
        .get_item()
        .table_name(&state.projection_table)
        .key("PK", AttributeValue::S(format!("SHIPMENT#{shipment_id}")))
        .key("SK", AttributeValue::S("STATE".to_owned()))
        .consistent_read(true)
        .send()
        .await
        .map_err(|error| ApiError::unavailable(format!("projection read failed: {error}")))?;
    let item = output
        .item()
        .ok_or_else(|| ApiError::not_found("shipment projection is not ready"))?;
    let projection = projection_from_item(item)?;

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
    let output = state
        .dynamo
        .query()
        .table_name(&state.projection_table)
        .key_condition_expression("#pk = :pk AND begins_with(#sk, :event)")
        .expression_attribute_names("#pk", "PK")
        .expression_attribute_names("#sk", "SK")
        .expression_attribute_values(":pk", AttributeValue::S(format!("SHIPMENT#{shipment_id}")))
        .expression_attribute_values(":event", AttributeValue::S("EVENT#".to_owned()))
        .consistent_read(true)
        .send()
        .await
        .map_err(|error| ApiError::unavailable(format!("timeline read failed: {error}")))?;

    let mut events = Vec::new();
    for item in output.items() {
        let raw = string_attribute(item, "event_json")?;
        events.push(serde_json::from_str::<EventEnvelope>(raw).map_err(ApiError::internal)?);
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

fn projection_from_item(item: &HashMap<String, AttributeValue>) -> ApiResult<ShipmentProjection> {
    Ok(ShipmentProjection {
        shipment_id: string_attribute(item, "shipment_id")?
            .parse()
            .map_err(ApiError::internal)?,
        owner_id: string_attribute(item, "owner_id")?.to_owned(),
        reference: string_attribute(item, "reference")?.to_owned(),
        origin: string_attribute(item, "origin")?.to_owned(),
        destination: string_attribute(item, "destination")?.to_owned(),
        status: serde_json::from_value(Value::String(string_attribute(item, "status")?.to_owned()))
            .map_err(ApiError::internal)?,
        version: number_attribute(item, "version")?,
        updated_at: string_attribute(item, "updated_at")?
            .parse::<chrono::DateTime<Utc>>()
            .map_err(ApiError::internal)?,
    })
}

fn string_attribute<'a>(
    item: &'a HashMap<String, AttributeValue>,
    name: &str,
) -> ApiResult<&'a str> {
    item.get(name)
        .and_then(|value| value.as_s().ok())
        .map(String::as_str)
        .ok_or_else(|| ApiError::internal(format!("projection attribute {name} is missing")))
}

fn number_attribute(item: &HashMap<String, AttributeValue>, name: &str) -> ApiResult<i64> {
    item.get(name)
        .and_then(|value| value.as_n().ok())
        .map(String::as_str)
        .ok_or_else(|| ApiError::internal(format!("projection attribute {name} is not numeric")))?
        .parse::<i64>()
        .map_err(ApiError::internal)
}
