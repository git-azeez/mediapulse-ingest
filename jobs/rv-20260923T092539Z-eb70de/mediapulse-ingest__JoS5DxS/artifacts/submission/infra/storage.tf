resource "google_sql_database_instance" "postgres" {
  name             = "${var.prefix}-sql"
  database_version = "POSTGRES_15"
  region           = var.gcp_region

  depends_on = [google_service_networking_connection.private_vpc_connection]

  settings {
    tier = "db-f1-micro"

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.vpc.id
    }
  }

  deletion_protection = false
}

resource "google_sql_database" "database" {
  name     = var.db_name
  instance = google_sql_database_instance.postgres.name
}

resource "google_sql_user" "users" {
  name     = var.db_username
  instance = google_sql_database_instance.postgres.name
  password = var.db_password
}

resource "google_firestore_database" "database" {
  provider                    = google-beta
  project                     = var.gcp_project_id
  name                        = "(default)"
  location_id                 = var.gcp_region
  type                        = "FIRESTORE_NATIVE"
  concurrency_mode            = "OPTIMISTIC"
  app_engine_integration_mode = "DISABLED"
}

resource "google_redis_instance" "cache" {
  name               = "${var.prefix}-redis"
  tier               = "BASIC"
  memory_size_gb     = 1
  region             = var.gcp_region
  authorized_network = google_compute_network.vpc.id

  depends_on = [google_service_networking_connection.private_vpc_connection]
}

resource "google_storage_bucket" "audit" {
  name                        = "${var.prefix}-audit-bucket"
  location                    = var.gcp_region
  force_destroy               = true
  public_access_prevention    = "enforced"
  uniform_bucket_level_access = true

  encryption {
    default_kms_key_name = google_kms_crypto_key.crypto_key.id
  }
}
