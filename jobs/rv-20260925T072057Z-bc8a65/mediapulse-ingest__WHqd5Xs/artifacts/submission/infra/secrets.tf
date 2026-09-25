# Secret Manager - database connection string

resource "google_secret_manager_secret" "db_url" {
  secret_id  = "${local.prefix}-db-url"
  project    = local.project_id
  labels     = local.common_labels

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "db_url" {
  secret      = google_secret_manager_secret.db_url.id
  secret_data = local.database_url
}

resource "google_secret_manager_secret" "db_password" {
  secret_id  = "${local.prefix}-db-password"
  project    = local.project_id
  labels     = local.common_labels

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = local.db_password
}
