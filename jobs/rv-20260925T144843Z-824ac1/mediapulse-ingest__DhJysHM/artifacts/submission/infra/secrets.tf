resource "google_secret_manager_secret" "db_url" {
  secret_id = "${local.prefix}-db-url"
  project   = local.project
  labels    = local.labels

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "db_url" {
  secret      = google_secret_manager_secret.db_url.id
  secret_data = local.db_url
}

resource "google_secret_manager_secret_iam_member" "api_accessor" {
  secret_id = google_secret_manager_secret.db_url.secret_id
  project   = local.project
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

resource "google_secret_manager_secret_iam_member" "relay_accessor" {
  secret_id = google_secret_manager_secret.db_url.secret_id
  project   = local.project
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.relay.email}"
}

resource "google_secret_manager_secret_iam_member" "archiver_accessor" {
  secret_id = google_secret_manager_secret.db_url.secret_id
  project   = local.project
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.archiver.email}"
}
