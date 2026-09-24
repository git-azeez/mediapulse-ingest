use aws_sdk_dynamodb::Client as DynamoClient;
use aws_sdk_sqs::Client as SqsClient;
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
    pub(crate) sqs: SqsClient,
    pub(crate) dynamo: DynamoClient,
    pub(crate) valkey: redis::Client,
    pub(crate) queue_url: String,
    pub(crate) projection_table: String,
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
        let queue_url = config::required("QUEUE_URL")?;
        let projection_table = config::required("PROJECTION_TABLE")?;
        let valkey_endpoint = config::required("VALKEY_ENDPOINT")?;
        let endpoint = config::aws_endpoint()?;
        let region = config::aws_region();
        let issuer = config::required("COGNITO_ISSUER")?;
        let audiences = config::required("COGNITO_AUDIENCES")?
            .split(',')
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .map(str::to_owned)
            .collect::<Vec<_>>();
        if audiences.is_empty() {
            anyhow::bail!("COGNITO_AUDIENCES must contain at least one client ID");
        }
        let jwks_url = config::optional("COGNITO_JWKS_URL");
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

        let sdk = cloud::sdk_config(&endpoint, &region).await;
        Ok(Self {
            state: AppState {
                db,
                sqs: SqsClient::new(&sdk),
                dynamo: DynamoClient::new(&sdk),
                valkey: redis::Client::open(normalize_valkey_url(&valkey_endpoint))?,
                queue_url,
                projection_table,
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
