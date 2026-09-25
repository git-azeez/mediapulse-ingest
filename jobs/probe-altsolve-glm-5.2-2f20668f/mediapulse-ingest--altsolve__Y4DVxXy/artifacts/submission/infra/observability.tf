# Centralized structured audit log bucket.
#
# The logging contract (services/logging.md) requires "Structured JSON log
# formatting for all microservices" and "Minimum 30 days retention policy for
# audit compliance". A single project-scoped log bucket satisfies both: every
# microservice writes structured JSON, and per-service sinks below route each
# component's logs into this one retention-enforced bucket. The contract does
# not mandate one bucket per service.
resource "google_logging_project_bucket_config" "central" {
  project        = var.gcp_project_id
  location       = var.gcp_region
  retention_days = 30
  bucket_id      = "${var.prefix}-logs"
  description    = "MediaPulse Ingest centralized structured audit log bucket (all microservices)"
}

resource "google_logging_project_sink" "api" {
  name        = "${var.prefix}-api-sink"
  destination = "logging.googleapis.com/projects/${var.gcp_project_id}/locations/${var.gcp_region}/buckets/${google_logging_project_bucket_config.central.bucket_id}"
  filter      = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${google_cloud_run_v2_service.api.name}\""
}

resource "google_logging_project_sink" "processor" {
  name        = "${var.prefix}-processor-sink"
  destination = "logging.googleapis.com/projects/${var.gcp_project_id}/locations/${var.gcp_region}/buckets/${google_logging_project_bucket_config.central.bucket_id}"
  filter      = "resource.type=\"cloud_functions\" AND resource.labels.function_name=\"${google_cloudfunctions2_function.processor.name}\""
}

resource "google_logging_project_sink" "relay" {
  name        = "${var.prefix}-relay-sink"
  destination = "logging.googleapis.com/projects/${var.gcp_project_id}/locations/${var.gcp_region}/buckets/${google_logging_project_bucket_config.central.bucket_id}"
  filter      = "resource.type=\"cloud_functions\" AND resource.labels.function_name=\"${google_cloudfunctions2_function.relay.name}\""
}

resource "google_logging_project_sink" "archiver" {
  name        = "${var.prefix}-archiver-sink"
  destination = "logging.googleapis.com/projects/${var.gcp_project_id}/locations/${var.gcp_region}/buckets/${google_logging_project_bucket_config.central.bucket_id}"
  filter      = "resource.type=\"cloud_functions\" AND resource.labels.function_name=\"${google_cloudfunctions2_function.archiver.name}\""
}

resource "google_monitoring_notification_channel" "ops_email" {
  display_name = "${var.prefix}-ops-alerts"
  type         = "email"

  labels = {
    email_address = "ops@mediapulse.invalid"
  }
}
