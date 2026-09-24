use super::{claims, middleware::AuthError};
use jsonwebtoken::{Algorithm, DecodingKey, Validation, decode, decode_header, jwk::JwkSet};
use serde_json::Value;
use std::{collections::HashMap, sync::Arc};
use tokio::sync::RwLock;

#[derive(Clone)]
pub struct JwtVerifier {
    inner: Arc<JwtVerifierInner>,
}

struct JwtVerifierInner {
    issuer: String,
    audiences: Vec<String>,
    jwks_url: String,
    client: reqwest::Client,
    keys: RwLock<HashMap<String, DecodingKey>>,
}

impl JwtVerifier {
    pub fn new(issuer: String, audiences: Vec<String>, jwks_url: Option<String>) -> Self {
        let jwks_url = jwks_url
            .unwrap_or_else(|| format!("{}/.well-known/jwks.json", issuer.trim_end_matches('/')));
        Self {
            inner: Arc::new(JwtVerifierInner {
                issuer,
                audiences,
                jwks_url,
                client: reqwest::Client::builder()
                    .connect_timeout(std::time::Duration::from_secs(3))
                    .timeout(std::time::Duration::from_secs(5))
                    .build()
                    .expect("static HTTP client configuration must be valid"),
                keys: RwLock::new(HashMap::new()),
            }),
        }
    }

    async fn refresh_keys(&self) -> Result<(), AuthError> {
        let response = self
            .inner
            .client
            .get(&self.inner.jwks_url)
            .send()
            .await
            .map_err(|error| {
                tracing::warn!(%error, jwks_url = %self.inner.jwks_url, "jwks_fetch_failed");
                AuthError::Unavailable
            })?
            .error_for_status()
            .map_err(|error| {
                tracing::warn!(%error, jwks_url = %self.inner.jwks_url, "jwks_fetch_rejected");
                AuthError::Unavailable
            })?;
        let set = response.json::<JwkSet>().await.map_err(|error| {
            tracing::warn!(%error, "jwks_decode_failed");
            AuthError::Unavailable
        })?;

        let mut keys = HashMap::new();
        for jwk in &set.keys {
            if let (Some(kid), Ok(key)) = (&jwk.common.key_id, DecodingKey::from_jwk(jwk)) {
                keys.insert(kid.clone(), key);
            }
        }
        if keys.is_empty() {
            return Err(AuthError::Unavailable);
        }
        *self.inner.keys.write().await = keys;
        Ok(())
    }

    pub(super) async fn verify_scope(
        &self,
        token: &str,
        required_scope: &str,
    ) -> Result<Value, AuthError> {
        let token_header = decode_header(token).map_err(|_| AuthError::Invalid)?;
        if token_header.alg != Algorithm::RS256 {
            return Err(AuthError::Invalid);
        }
        let kid = token_header.kid.ok_or(AuthError::Invalid)?;

        let mut key = self.inner.keys.read().await.get(&kid).cloned();
        if key.is_none() {
            self.refresh_keys().await?;
            key = self.inner.keys.read().await.get(&kid).cloned();
        }
        let key = key.ok_or(AuthError::Invalid)?;

        let mut validation = Validation::new(Algorithm::RS256);
        validation.set_issuer(&[self.inner.issuer.as_str()]);
        validation.validate_aud = false;
        validation.required_spec_claims.insert("exp".to_owned());
        validation.required_spec_claims.insert("iss".to_owned());
        let claims = decode::<Value>(token, &key, &validation)
            .map_err(|error| {
                tracing::info!(%error, "jwt_rejected");
                AuthError::Invalid
            })?
            .claims;

        if self.inner.audiences.is_empty()
            || !self
                .inner
                .audiences
                .iter()
                .any(|expected| claims::audience_matches(&claims, expected))
        {
            return Err(AuthError::Invalid);
        }
        if !claims::has_scope(&claims, required_scope) {
            return Err(AuthError::Forbidden);
        }
        Ok(claims)
    }
}
