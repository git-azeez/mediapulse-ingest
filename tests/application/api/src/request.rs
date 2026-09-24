use crate::{
    error::{ApiError, ApiResult},
    state::AppState,
};
use axum::{
    extract::Request,
    http::{HeaderMap, HeaderName, HeaderValue},
    middleware::Next,
    response::Response,
};
use tracing::{Instrument, info_span};
use uuid::Uuid;

pub(crate) const IDEMPOTENCY_KEY: &str = "idempotency-key";
const CORRELATION_ID: &str = "x-correlation-id";
const SOURCE_HEADER: &str = "x-cinderroute-source";
const VERSION_HEADER: &str = "x-cinderroute-version";
const INSTANCE_HEADER: &str = "x-cinderroute-instance";

pub(crate) async fn correlation_middleware(mut request: Request, next: Next) -> Response {
    let correlation = request
        .headers()
        .get(CORRELATION_ID)
        .and_then(|value| value.to_str().ok())
        .filter(|value| !value.is_empty() && value.len() <= 200)
        .map(str::to_owned)
        .unwrap_or_else(|| Uuid::new_v4().to_string());
    request.headers_mut().insert(
        HeaderName::from_static(CORRELATION_ID),
        HeaderValue::from_str(&correlation).expect("validated or generated correlation ID"),
    );

    let method = request.method().clone();
    let path = request.uri().path().to_owned();
    let span = info_span!("http_request", correlation_id = %correlation, %method, %path);
    async move {
        let mut response = next.run(request).await;
        if let Ok(value) = HeaderValue::from_str(&correlation) {
            response
                .headers_mut()
                .insert(HeaderName::from_static(CORRELATION_ID), value);
        }
        tracing::info!(status = response.status().as_u16(), "http_request_complete");
        response
    }
    .instrument(span)
    .await
}

pub(crate) fn required_header(headers: &HeaderMap, name: &'static str) -> ApiResult<String> {
    let value = headers
        .get(name)
        .and_then(|value| value.to_str().ok())
        .filter(|value| !value.trim().is_empty() && value.len() <= 200)
        .ok_or_else(|| ApiError::bad_request(format!("{name} header is required")))?;
    Ok(value.to_owned())
}

pub(crate) fn correlation_header(headers: &HeaderMap) -> String {
    headers
        .get(CORRELATION_ID)
        .and_then(|value| value.to_str().ok())
        .filter(|value| !value.is_empty() && value.len() <= 200)
        .map(str::to_owned)
        .unwrap_or_else(|| Uuid::new_v4().to_string())
}

pub(crate) fn evidence_headers(
    state: &AppState,
    source: &str,
    version: i64,
) -> ApiResult<HeaderMap> {
    let mut headers = HeaderMap::new();
    headers.insert(
        HeaderName::from_static(SOURCE_HEADER),
        HeaderValue::from_str(source).map_err(ApiError::internal)?,
    );
    headers.insert(
        HeaderName::from_static(VERSION_HEADER),
        HeaderValue::from_str(&version.to_string()).map_err(ApiError::internal)?,
    );
    headers.insert(
        HeaderName::from_static(INSTANCE_HEADER),
        HeaderValue::from_str(&state.instance).map_err(ApiError::internal)?,
    );
    Ok(headers)
}
