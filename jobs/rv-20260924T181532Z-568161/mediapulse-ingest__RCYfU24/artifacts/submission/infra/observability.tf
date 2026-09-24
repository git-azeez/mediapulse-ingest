resource "google_logging_project_bucket_config" "api" {
  project        = var.gcp_project_id
  location       = var.gcp_region
  retention_days = 14
  bucket_id      = "${var.prefix}-api-logs"
  description    = "Cloud Run API structured request and audit logs"
}

resource "google_logging_project_bucket_config" "processor" {
  project        = var.gcp_project_id
  location       = var.gcp_region
  retention_days = 14
  bucket_id      = "${var.prefix}-processor-logs"
  description    = "Cloud Functions event processor execution logs"
}

resource "google_logging_project_bucket_config" "relay" {
  project        = var.gcp_project_id
  location       = var.gcp_region
  retention_days = 14
  bucket_id      = "${var.prefix}-relay-logs"
  description    = "Cloud Functions outbox relay logs"
}

resource "google_logging_project_bucket_config" "archiver" {
  project        = var.gcp_project_id
  location       = var.gcp_region
  retention_days = 14
  bucket_id      = "${var.prefix}-archiver-logs"
  description    = "Cloud Functions audit archiver logs"
}

resource "google_logging_project_sink" "api" {
  name        = "${var.prefix}-api-sink"
  destination = "logging.googleapis.com/projects/${var.gcp_project_id}/locations/${var.gcp_region}/buckets/${google_logging_project_bucket_config.api.bucket_id}"
  filter      = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${google_cloud_run_v2_service.api.name}\""
}

resource "google_monitoring_notification_channel" "ops_email" {
  display_name = "${var.prefix}-ops-alerts"
  type         = "email"

  labels = {
    email_address = "ops@mediapulse.invalid"
  }
}
