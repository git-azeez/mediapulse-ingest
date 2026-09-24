use reqwest::Client as HttpClient;
use cinderroute::{
    auth::{AuthState, JwtVerifier},
    cloud,
    config::{self, normalize_valkey_url},
};
use sqlx::{PgPool, postgres::PgPoolOptions};
use std::{net::SocketAddr, time::Duration};
use uuid::Uuid;

#[derive(Clone)]
pub(crate) struct AppState {
    pub(crate) db: PgPool,
    pub(crate) http: HttpClient,
    pub(crate) valkey: redis::Client,
    pub(crate) project_id: String,
    pub(crate) pubsub_topic: String,
    pub(crate) firestore_database: String,
    pub(crate) gcp_endpoint: String,
    pub(crate) cache_ttl_seconds: u64,
    pub(crate) instance: String,
}

pub(crate) struct ApplicationContext {
    pub(crate) state: AppState,
    pub(crate) auth_state: AuthState,
    pub(crate) bind: SocketAddr,
}

impl ApplicationContext {
    pub(crate) async fn load() -> anyhow::Result<Self> {
        let database_url = config::required("DATABASE_URL")?;
        let pubsub_topic = config::optional("PUBSUB_TOPIC").unwrap_or_else(|| "mediapulse-events".to_owned());
        let firestore_database = config::optional("FIRESTORE_DATABASE").unwrap_or_else(|| "default".to_owned());
        let valkey_endpoint = config::optional("VALKEY_ENDPOINT")
            .or_else(|| config::optional("DATASTORE_NAMESPACE"))
            .unwrap_or_else(|| "redis://127.0.0.1:6379".to_owned());
        let gcp_endpoint = config::gcp_endpoint()?;
        let project_id = config::gcp_project_id();
        let issuer = config::optional("COGNITO_ISSUER")
            .or_else(|| config::optional("FIREBASE_AUTH_JWKS_URL"))
            .unwrap_or_else(|| "https://securetoken.google.com/mediapulse".to_owned());
        let audiences = config::optional("COGNITO_AUDIENCES")
            .unwrap_or_else(|| "mediapulse".to_owned())
            .split(',')
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .map(str::to_owned)
            .collect::<Vec<_>>();
        let jwks_url = config::optional("FIREBASE_AUTH_JWKS_URL")
            .or_else(|| config::optional("COGNITO_JWKS_URL"));
        let cache_ttl_seconds = config::parse_u64("CACHE_TTL_SECONDS", 60)?;
        let instance = config::optional("INSTANCE_ID")
            .or_else(|| config::optional("HOSTNAME"))
            .unwrap_or_else(|| Uuid::new_v4().to_string());
        let bind = config::optional("BIND_ADDR")
            .unwrap_or_else(|| "0.0.0.0:8080".to_owned())
            .parse()?;

        let db = PgPoolOptions::new()
            .max_connections(12)
            .acquire_timeout(Duration::from_secs(5))
            .connect(&database_url)
            .await?;
        run_migrations(&db).await?;

        Ok(Self {
            state: AppState {
                db,
                http: cloud::http_client()?,
                valkey: redis::Client::open(normalize_valkey_url(&valkey_endpoint))?,
                project_id,
                pubsub_topic,
                firestore_database,
                gcp_endpoint,
                cache_ttl_seconds,
                instance,
            },
            auth_state: AuthState {
                verifier: JwtVerifier::new(issuer, audiences, jwks_url),
            },
            bind,
        })
    }
}

async fn run_migrations(pool: &PgPool) -> anyhow::Result<()> {
    let mut lock = pool.acquire().await?;
    sqlx::query("SELECT pg_advisory_lock(1473412201)")
        .execute(&mut *lock)
        .await?;
    let result = sqlx::migrate!("./migrations").run(pool).await;
    let unlock = sqlx::query("SELECT pg_advisory_unlock(1473412201)")
        .execute(&mut *lock)
        .await;
    result?;
    unlock?;
    tracing::info!("database_migrations_complete");
    Ok(())
}
