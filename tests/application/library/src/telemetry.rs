use tracing_subscriber::EnvFilter;

pub fn init(service: &str) {
    let filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new("info,aws_config=warn,sqlx=warn"));

    let _ = tracing_subscriber::fmt()
        .with_env_filter(filter)
        .json()
        .with_current_span(true)
        .with_span_list(false)
        .with_target(false)
        .with_thread_ids(false)
        .with_thread_names(false)
        .with_ansi(false)
        .try_init();

    tracing::info!(
        service,
        fixture_version = env!("CARGO_PKG_VERSION"),
        "service_starting"
    );
}
