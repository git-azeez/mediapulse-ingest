resource "google_cloudfunctions2_function" "processor" {
  name        = "${var.prefix}-processor"
  location    = var.gcp_region
  description = "Processes Pub/Sub media events into Firestore and invalidates Datastore cache"

  service_config {
    max_instance_count             = 4
    min_instance_count             = 1
    available_memory                = "512Mi"
    timeout_seconds                 = 30
    service_account_email           = google_service_account.processor.email
    ingress_settings                = "ALLOW_INTERNAL_ONLY"
    all_traffic_on_latest_revision  = true

    environment_variables = {
      WORKER_ROLE             = "processor"
      CONTAINER_IMAGE         = var.processor_image
      GCP_PROJECT_ID          = var.gcp_project_id
      GCP_REGION              = var.gcp_region
      GCP_ENDPOINT_URL        = var.gcp_endpoint_url
      PUBSUB_EMULATOR_HOST    = "${local.gcp_endpoint_host}:4588"
      FIRESTORE_EMULATOR_HOST = "${local.gcp_endpoint_host}:4588"
      DATASTORE_EMULATOR_HOST = "${local.gcp_endpoint_host}:4588"
      FIRESTORE_DATABASE      = google_firestore_database.projections.name
      DATASTORE_NAMESPACE     = "${var.prefix}-cache"
    }
  }

  labels = merge(local.common_labels, { component = "processor" })
}

resource "google_cloudfunctions2_function" "relay" {
  name        = "${var.prefix}-outbox-relay"
  location    = var.gcp_region
  description = "Reconciles unpublished outbox rows from Cloud SQL to Pub/Sub"

  service_config {
    max_instance_count             = 2
    min_instance_count             = 0
    available_memory                = "512Mi"
    timeout_seconds                 = 30
    service_account_email           = google_service_account.relay.email
    ingress_settings                = "ALLOW_INTERNAL_ONLY"
    all_traffic_on_latest_revision  = true

    environment_variables = {
      WORKER_ROLE          = "relay"
      CONTAINER_IMAGE      = var.relay_image
      GCP_PROJECT_ID       = var.gcp_project_id
      GCP_REGION           = var.gcp_region
      GCP_ENDPOINT_URL     = var.gcp_endpoint_url
      PUBSUB_EMULATOR_HOST = "${local.gcp_endpoint_host}:4588"
      DATABASE_URL         = "postgresql://${var.db_username}:${var.db_password}@${local.gcp_endpoint_host}:5432/${var.db_name}?sslmode=disable"
      PUBSUB_TOPIC         = google_pubsub_topic.events.name
    }
  }

  labels = merge(local.common_labels, { component = "outbox-relay" })
}

resource "google_cloudfunctions2_function" "archiver" {
  name        = "${var.prefix}-audit-archiver"
  location    = var.gcp_region
  description = "Exports published events to GCS NDJSON audit batches"

  service_config {
    max_instance_count             = 2
    min_instance_count             = 0
    available_memory                = "512Mi"
    timeout_seconds                 = 60
    service_account_email           = google_service_account.archiver.email
    ingress_settings                = "ALLOW_INTERNAL_ONLY"
    all_traffic_on_latest_revision  = true

    environment_variables = {
      WORKER_ROLE           = "archiver"
      CONTAINER_IMAGE       = var.archiver_image
      GCP_PROJECT_ID        = var.gcp_project_id
      GCP_REGION            = var.gcp_region
      GCP_ENDPOINT_URL      = var.gcp_endpoint_url
      STORAGE_EMULATOR_HOST = var.gcp_endpoint_url
      DATABASE_URL          = "postgresql://${var.db_username}:${var.db_password}@${local.gcp_endpoint_host}:5432/${var.db_name}?sslmode=disable"
      AUDIT_BUCKET          = google_storage_bucket.audit.name
      AUDIT_PREFIX          = "events/"
    }
  }

  labels = merge(local.common_labels, { component = "audit-archiver" })
}
