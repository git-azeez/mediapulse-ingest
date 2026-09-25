resource "google_sql_database_instance" "main" {
  name                = "${local.prefix}-db"
  project             = local.project
  region              = local.region
  database_version    = "POSTGRES_15"
  deletion_protection = false
  encryption_key_name  = google_kms_crypto_key.database.id

  settings {
    tier              = "db-custom-2-4096"
    availability_type = "ZONAL"
    user_labels       = local.labels

    ip_configuration {
      ipv4_enabled = true
    }
  }
}

resource "google_sql_database" "db" {
  name     = local.db_name
  project  = local.project
  instance = google_sql_database_instance.main.name
}

resource "google_sql_user" "user" {
  name     = local.db_user
  project  = local.project
  instance = google_sql_database_instance.main.name
  password = local.db_pass
}

locals {
  db_host = google_sql_database_instance.main.public_ip_address
  db_url  = "postgresql://${local.db_user}:${urlencode(local.db_pass)}@${local.db_host}:5432/${local.db_name}?sslmode=disable"
}
