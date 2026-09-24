resource "google_identity_platform_tenant" "mediapulse" {
  provider                 = google-beta
  project                  = var.gcp_project_id
  display_name             = "${var.prefix}-tenant"
  allow_password_signup    = true
  enable_email_link_signin = false
}

resource "google_service_account" "client_read" {
  account_id   = "${var.prefix}-client-read"
  display_name = "MediaPulse Read Scope Client (mediapulse/read)"
}

resource "google_service_account" "client_write" {
  account_id   = "${var.prefix}-client-write"
  display_name = "MediaPulse Write Scope Client (mediapulse/write)"
}

resource "google_service_account" "client_admin" {
  account_id   = "${var.prefix}-client-admin"
  display_name = "MediaPulse Admin Scope Client (mediapulse/admin)"
}

resource "google_service_account_key" "client_read" {
  service_account_id = google_service_account.client_read.name
}

resource "google_service_account_key" "client_write" {
  service_account_id = google_service_account.client_write.name
}

resource "google_service_account_key" "client_admin" {
  service_account_id = google_service_account.client_admin.name
}
