resource "google_logging_project_bucket_config" "api" {
  project        = var.gcp_project_id
  location       = var.gcp_region
  retention_days = 14
  bucket_id      = "${var.prefix}-api-logs"
}

resource "google_logging_project_bucket_config" "processor" {
  project        = var.gcp_project_id
  location       = var.gcp_region
  retention_days = 14
  bucket_id      = "${var.prefix}-processor-logs"
}

resource "google_logging_project_bucket_config" "relay" {
  project        = var.gcp_project_id
  location       = var.gcp_region
  retention_days = 14
  bucket_id      = "${var.prefix}-relay-logs"
}

resource "google_logging_project_bucket_config" "archiver" {
  project        = var.gcp_project_id
  location       = var.gcp_region
  retention_days = 14
  bucket_id      = "${var.prefix}-archiver-logs"
}
