resource "google_cloudfunctions2_function" "processor" {
  name        = "${var.prefix}-processor"
  location    = var.gcp_region
  description = "Projects Pub/Sub media events into Firestore and invalidates Datastore entity cache"

  service_config {
    max_instance_count             = 4
    min_instance_count             = 1
    available_memory               = "512Mi"
    timeout_seconds                = 30
    service_account_email          = google_service_account.processor.email
    ingress_settings               = "ALLOW_INTERNAL_ONLY"
    all_traffic_on_latest_revision = true

    environment_variables = {
      WORKER_ROLE             = "processor"
      CONTAINER_IMAGE         = var.processor_image
      GCP_PROJECT_ID          = var.gcp_project_id
      GCP_REGION              = var.gcp_region
      GCP_ENDPOINT_URL        = var.gcp_endpoint_url
      PUBSUB_EMULATOR_HOST    = local.pubsub_emulator_host
      FIRESTORE_EMULATOR_HOST = local.firestore_emulator_host
      DATASTORE_EMULATOR_HOST = local.datastore_emulator_host
      FIRESTORE_DATABASE      = google_firestore_database.projections.name
      DATASTORE_NAMESPACE     = "${var.prefix}-cache"
      RUST_LOG                = "info"
    }
  }

  labels = merge(local.common_labels, {
    component = "processor"
  })
}

resource "google_cloudfunctions2_function" "relay" {
  name        = "${var.prefix}-outbox-relay"
  location    = var.gcp_region
  description = "Reconciles unpublished outbox rows from Cloud SQL PostgreSQL to Cloud Pub/Sub"

  service_config {
    max_instance_count             = 2
    min_instance_count             = 0
    available_memory               = "512Mi"
    timeout_seconds                = 30
    service_account_email          = google_service_account.relay.email
    ingress_settings               = "ALLOW_INTERNAL_ONLY"
    all_traffic_on_latest_revision = true

    environment_variables = {
      WORKER_ROLE          = "relay"
      CONTAINER_IMAGE      = var.relay_image
      GCP_PROJECT_ID       = var.gcp_project_id
      GCP_REGION           = var.gcp_region
      GCP_ENDPOINT_URL     = var.gcp_endpoint_url
      PUBSUB_EMULATOR_HOST = local.pubsub_emulator_host
      DATABASE_URL         = local.database_url
      PUBSUB_TOPIC         = google_pubsub_topic.events.name
      BATCH_LIMIT          = "50"
      RUST_LOG             = "info"
    }
  }

  labels = merge(local.common_labels, {
    component = "outbox-relay"
  })
}

resource "google_cloudfunctions2_function" "archiver" {
  name        = "${var.prefix}-audit-archiver"
  location    = var.gcp_region
  description = "Exports published PostgreSQL media events into private GCS NDJSON audit batches"

  service_config {
    max_instance_count             = 2
    min_instance_count             = 0
    available_memory               = "512Mi"
    timeout_seconds                = 60
    service_account_email          = google_service_account.archiver.email
    ingress_settings               = "ALLOW_INTERNAL_ONLY"
    all_traffic_on_latest_revision = true

    environment_variables = {
      WORKER_ROLE           = "archiver"
      CONTAINER_IMAGE       = var.archiver_image
      GCP_PROJECT_ID        = var.gcp_project_id
      GCP_REGION            = var.gcp_region
      GCP_ENDPOINT_URL      = var.gcp_endpoint_url
      STORAGE_EMULATOR_HOST = local.storage_emulator_host
      DATABASE_URL          = local.database_url
      AUDIT_BUCKET          = google_storage_bucket.audit.name
      AUDIT_PREFIX          = "events/"
      BATCH_LIMIT           = "100"
      RUST_LOG              = "info"
    }
  }

  labels = merge(local.common_labels, {
    component = "audit-archiver"
  })
}
