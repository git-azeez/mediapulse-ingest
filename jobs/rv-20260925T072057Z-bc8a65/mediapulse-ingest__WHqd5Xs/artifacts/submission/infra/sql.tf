# Cloud SQL for PostgreSQL (event store + transactional outbox)

resource "google_sql_database_instance" "main" {
  name             = "${local.prefix}-pg"
  project          = local.project_id
  region           = local.region
  database_version = "POSTGRES_16"
  encryption_key_name = google_kms_crypto_key.database.id

  settings {
    tier = "db-custom-1-3840"
    availability_type = "ZONAL"

    ip_configuration {
      ipv4_enabled = false
      private_network = "projects/${local.project_id}/global/networks/${google_compute_network.vpc.name}"
    }
  }
}

resource "google_sql_database" "db" {
  name     = local.db_name
  project  = local.project_id
  instance = google_sql_database_instance.main.name
}

resource "google_sql_user" "user" {
  name     = local.db_username
  project  = local.project_id
  instance = google_sql_database_instance.main.name
  password = local.db_password
}

locals {
  db_host        = coalesce(google_sql_database_instance.main.private_ip_address, "gcp")
  database_url   = "postgresql://${local.db_username}:${urlencode(local.db_password)}@${local.db_host}:5432/${local.db_name}?sslmode=disable"
}
