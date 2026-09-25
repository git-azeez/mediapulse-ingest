resource "google_identity_platform_tenant" "mediapulse" {
  provider             = google-beta
  project              = var.gcp_project_id
  display_name         = "${var.prefix}-tenant"
  allow_password_signup = true
}
