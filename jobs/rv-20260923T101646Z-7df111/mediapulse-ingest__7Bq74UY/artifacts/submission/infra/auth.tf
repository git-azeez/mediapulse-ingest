resource "google_identity_platform_config" "default" {
  provider = google-beta
  project  = var.gcp_project_id
}
