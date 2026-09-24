use crate::state::AppState;
use axum::{
    Json,
    extract::State,
    http::StatusCode,
    response::{IntoResponse, Response},
};
use cinderroute::model::HealthResponse;
use std::collections::BTreeMap;

pub(crate) async fn live(State(state): State<AppState>) -> Json<HealthResponse> {
    Json(HealthResponse {
        status: "UP",
        service: "cinderroute-api",
        instance: state.instance,
        checks: BTreeMap::new(),
    })
}

pub(crate) async fn ready(State(state): State<AppState>) -> Response {
    let mut checks = BTreeMap::new();
    let mut critical_healthy = true;

    if sqlx::query_scalar::<_, i32>("SELECT 1")
        .fetch_one(&state.db)
        .await
        .is_ok()
    {
        checks.insert("postgres", "UP");
    } else {
        checks.insert("postgres", "DOWN");
        critical_healthy = false;
    }

    let pubsub_url = format!(
        "{}/v1/projects/{}/topics/{}",
        state.gcp_endpoint, state.project_id, state.pubsub_topic
    );
    if state
        .http
        .get(&pubsub_url)
        .send()
        .await
        .is_ok()
    {
        checks.insert("pubsub", "UP");
    } else {
        checks.insert("pubsub", "DOWN");
    }

    let firestore_url = format!(
        "{}/v1/projects/{}/databases/{}/documents",
        state.gcp_endpoint, state.project_id, state.firestore_database
    );
    if state
        .http
        .get(&firestore_url)
        .send()
        .await
        .is_ok()
    {
        checks.insert("firestore", "UP");
    } else {
        checks.insert("firestore", "DOWN");
        critical_healthy = false;
    }

    let valkey_healthy = match state.valkey.get_multiplexed_async_connection().await {
        Ok(mut connection) => redis::cmd("PING")
            .query_async::<String>(&mut connection)
            .await
            .is_ok(),
        Err(_) => false,
    };
    if valkey_healthy {
        checks.insert("valkey", "UP");
    } else {
        checks.insert("valkey", "DOWN");
    }

    let body = HealthResponse {
        status: if critical_healthy { "UP" } else { "DOWN" },
        service: "cinderroute-api",
        instance: state.instance,
        checks,
    };
    (
        if critical_healthy {
            StatusCode::OK
        } else {
            StatusCode::SERVICE_UNAVAILABLE
        },
        Json(body),
    )
        .into_response()
}
