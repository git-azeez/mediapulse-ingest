# Structured logs retention bucket (30+ day retention) and per-service sinks
resource "google_logging_project_bucket_config" "main" {
  project        = var.project_id
  bucket_id      = local.log_bucket_name
  location       = var.region
  retention_days = 30
}

resource "google_logging_project_sink" "api" {
  project           = var.project_id
  name             = local.log_sink_api
  destination      = "logging.googleapis.com/projects/${var.project_id}/locations/${var.region}/buckets/${local.log_bucket_name}"
  filter           = "resource.type=\"cloud_run_revision\" AND resource.label.service_name=\"${local.run_service_name}\""
  unique_writer_identity = true
}

resource "google_logging_project_sink" "processor" {
  project           = var.project_id
  name             = local.log_sink_proc
  destination      = "logging.googleapis.com/projects/${var.project_id}/locations/${var.region}/buckets/${local.log_bucket_name}"
  filter           = "resource.type=\"cloud_function\" AND resource.label.function_name=\"${local.processor_fn_name}\""
  unique_writer_identity = true
}

resource "google_logging_project_sink" "relay" {
  project           = var.project_id
  name             = local.log_sink_relay
  destination      = "logging.googleapis.com/projects/${var.project_id}/locations/${var.region}/buckets/${local.log_bucket_name}"
  filter           = "resource.type=\"cloud_function\" AND resource.label.function_name=\"${local.relay_fn_name}\""
  unique_writer_identity = true
}

resource "google_logging_project_sink" "archiver" {
  project           = var.project_id
  name             = local.log_sink_archiver
  destination      = "logging.googleapis.com/projects/${var.project_id}/locations/${var.region}/buckets/${local.log_bucket_name}"
  filter           = "resource.type=\"cloud_function\" AND resource.label.function_name=\"${local.archiver_fn_name}\""
  unique_writer_identity = true
}

resource "google_monitoring_notification_channel" "main" {
  project      = var.project_id
  display_name = "MediaPulse Ingest ops alerts"
  type         = "email"
  labels       = merge(local.common_labels, { "email" = "ops@mediapulse.io" })
}
