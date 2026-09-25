resource "google_sql_database_instance" "db" {
  name                = "${var.prefix}-events-pg"
  region              = var.gcp_region
  database_version    = "POSTGRES_15"
  deletion_protection = false

  settings {
    tier              = "db-f1-micro"
    availability_type = "ZONAL"
    disk_size         = 20
    disk_type         = "PD_SSD"
    disk_autoresize   = true

    ip_configuration {
      ipv4_enabled = false
    }
  }
}

resource "google_sql_database" "mediapulse" {
  name     = var.db_name
  instance = google_sql_database_instance.db.name
}

resource "google_sql_user" "app" {
  name     = var.db_username
  instance = google_sql_database_instance.db.name
  password = var.db_password
}

resource "google_secret_manager_secret" "db_credentials" {
  secret_id = "${var.prefix}-db-credentials"

  replication {
    auto {}
  }

  labels = local.common_labels
}

resource "google_secret_manager_secret_version" "db_v1" {
  secret = google_secret_manager_secret.db_credentials.id
  secret_data = "postgresql://${var.db_username}:${var.db_password}@${local.gcp_endpoint_host}:5432/${var.db_name}?sslmode=disable"
}
