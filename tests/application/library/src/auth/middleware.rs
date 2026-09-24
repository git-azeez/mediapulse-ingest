use super::verifier::JwtVerifier;
use axum::{
    Json,
    extract::{Request, State},
    http::{HeaderMap, StatusCode, header},
    middleware::Next,
    response::{IntoResponse, Response},
};
use serde_json::json;

#[derive(Clone)]
pub struct AuthState {
    pub verifier: JwtVerifier,
}

#[derive(Debug)]
pub(super) enum AuthError {
    Missing,
    Invalid,
    Forbidden,
    Unavailable,
}

impl IntoResponse for AuthError {
    fn into_response(self) -> Response {
        let (status, code, message) = match self {
            Self::Missing => (
                StatusCode::UNAUTHORIZED,
                "unauthorized",
                "bearer token required",
            ),
            Self::Invalid => (
                StatusCode::UNAUTHORIZED,
                "unauthorized",
                "bearer token is invalid",
            ),
            Self::Forbidden => (
                StatusCode::FORBIDDEN,
                "forbidden",
                "required scope is missing",
            ),
            Self::Unavailable => (
                StatusCode::SERVICE_UNAVAILABLE,
                "auth_unavailable",
                "token verification keys are unavailable",
            ),
        };
        (status, Json(json!({"error": code, "message": message}))).into_response()
    }
}

fn bearer(headers: &HeaderMap) -> Result<&str, AuthError> {
    let value = headers
        .get(header::AUTHORIZATION)
        .and_then(|value| value.to_str().ok())
        .ok_or(AuthError::Missing)?;
    value.strip_prefix("Bearer ").ok_or(AuthError::Missing)
}

async fn require(state: AuthState, request: Request, next: Next, scope: &'static str) -> Response {
    let token = match bearer(request.headers()) {
        Ok(token) => token,
        Err(error) => return error.into_response(),
    };
    match state.verifier.verify_scope(token, scope).await {
        Ok(_) => next.run(request).await,
        Err(error) => error.into_response(),
    }
}

pub async fn require_read(
    State(state): State<AuthState>,
    request: Request,
    next: Next,
) -> Response {
    require(state, request, next, "cinderroute/read").await
}

pub async fn require_write(
    State(state): State<AuthState>,
    request: Request,
    next: Next,
) -> Response {
    require(state, request, next, "cinderroute/write").await
}

pub async fn require_admin(
    State(state): State<AuthState>,
    request: Request,
    next: Next,
) -> Response {
    require(state, request, next, "cinderroute/admin").await
}
