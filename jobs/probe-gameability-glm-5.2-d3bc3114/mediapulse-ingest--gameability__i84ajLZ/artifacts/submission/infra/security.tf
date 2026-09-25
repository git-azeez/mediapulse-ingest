resource "google_service_account" "api" {
  account_id   = "${local.sa_prefix}-api-sa"
  display_name = "MediaPulse API Service Account"
}

resource "google_service_account" "processor" {
  account_id   = "${local.sa_prefix}-proc-sa"
  display_name = "MediaPulse Processor Service Account"
}

resource "google_service_account" "relay" {
  account_id   = "${local.sa_prefix}-relay-sa"
  display_name = "MediaPulse Relay Service Account"
}

resource "google_service_account" "archiver" {
  account_id   = "${local.sa_prefix}-arch-sa"
  display_name = "MediaPulse Archiver Service Account"
}

resource "google_service_account" "scheduler" {
  account_id   = "${local.sa_prefix}-sched-sa"
  display_name = "MediaPulse Scheduler Service Account"
}

resource "google_service_account" "client_read" {
  account_id   = "${local.sa_prefix}-read-sa"
  display_name = "MediaPulse Read Client"
}

resource "google_service_account" "client_write" {
  account_id   = "${local.sa_prefix}-write-sa"
  display_name = "MediaPulse Write Client"
}

resource "google_service_account" "client_admin" {
  account_id   = "${local.sa_prefix}-admin-sa"
  display_name = "MediaPulse Admin Client"
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
