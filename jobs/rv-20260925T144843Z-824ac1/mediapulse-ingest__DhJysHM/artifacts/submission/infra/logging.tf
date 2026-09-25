# Centralized log bucket (30-day retention) + per-microservice sinks
resource "google_logging_project_bucket_config" "main" {
  project        = local.project
  bucket_id      = "${local.prefix}-logs-bucket"
  location       = "global"
  retention_days = 30
}

resource "google_logging_project_sink" "api" {
  name        = "${local.prefix}-api-sink"
  project     = local.project
  filter      = "resource.type=\"cloud_run_revision\" AND resource.label.service_name=\"${google_cloud_run_v2_service.api.name}\""
  destination = "logging.googleapis.com/projects/${local.project}/locations/global/buckets/${google_logging_project_bucket_config.main.bucket_id}"
}

resource "google_logging_project_sink" "processor" {
  name        = "${local.prefix}-processor-sink"
  project     = local.project
  filter      = "resource.type=\"cloud_function\" AND resource.label.function_name=\"${google_cloudfunctions2_function.processor.name}\""
  destination = "logging.googleapis.com/projects/${local.project}/locations/global/buckets/${google_logging_project_bucket_config.main.bucket_id}"
}

resource "google_logging_project_sink" "relay" {
  name        = "${local.prefix}-relay-sink"
  project     = local.project
  filter      = "resource.type=\"cloud_function\" AND resource.label.function_name=\"${google_cloudfunctions2_function.relay.name}\""
  destination = "logging.googleapis.com/projects/${local.project}/locations/global/buckets/${google_logging_project_bucket_config.main.bucket_id}"
}

resource "google_logging_project_sink" "archiver" {
  name        = "${local.prefix}-archiver-sink"
  project     = local.project
  filter      = "resource.type=\"cloud_function\" AND resource.label.function_name=\"${google_cloudfunctions2_function.archiver.name}\""
  destination = "logging.googleapis.com/projects/${local.project}/locations/global/buckets/${google_logging_project_bucket_config.main.bucket_id}"
}

resource "google_monitoring_notification_channel" "ops" {
  project      = local.project
  display_name = "MediaPulse Ops"
  type         = "email"
  labels = {
    email = "ops@mediapulse.invalid"
  }
}
