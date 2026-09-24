resource "google_service_account" "api" {
  account_id   = "${var.prefix}-api-sa"
  display_name = "MediaPulse API Service Account"
}

resource "google_service_account" "worker" {
  account_id   = "${var.prefix}-worker-sa"
  display_name = "MediaPulse Worker Service Account"
}

resource "google_service_account" "scheduler" {
  account_id   = "${var.prefix}-scheduler-sa"
  display_name = "MediaPulse Scheduler Service Account"
}

resource "google_project_iam_member" "api_datastore" {
  project = var.gcp_project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "worker_datastore" {
  project = var.gcp_project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_project_iam_member" "worker_pubsub" {
  project = var.gcp_project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.worker.email}"
}
