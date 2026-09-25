# Cloud Logging & Monitoring

resource "google_logging_project_bucket_config" "main" {
  project    = local.project_id
  bucket_id  = "${local.prefix}-logs-bucket"
  location   = "global"
  description = "MediaPulse Ingest structured logs (30-day retention)"

  retention_days = 30
}

resource "google_logging_project_sink" "main" {
  project     = local.project_id
  name        = "${local.prefix}-log-sink"
  description = "MediaPulse structured log sink"
  destination = "logging.googleapis.com/projects/${local.project_id}/locations/global/buckets/${google_logging_project_bucket_config.main.name}"
  filter      = "resource.labels.mediapulse_deployment=\"${local.prefix}\""

  unique_writer_identity = true
}

resource "google_monitoring_notification_channel" "main" {
  project      = local.project_id
  display_name = "MediaPulse ops alerts"
  type         = "email"
  labels = {
    email_address = "ops@mediapulse.io"
  }
}
