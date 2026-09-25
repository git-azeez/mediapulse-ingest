resource "google_sql_database_instance" "main" {
  name             = local.sql_instance_name
  database_version = "POSTGRES_16"
  region           = var.region

  settings {
    tier              = "db-f1-micro"
    availability_type = "ZONAL"
    disk_size         = 20
    disk_type         = "PD_SSD"

    ip_configuration {
      ipv4_enabled = false
      private_network = google_compute_network.vpc.id
    }


    backup_configuration {
      enabled = true
    }
  }

  depends_on = [google_compute_network.vpc]
  deletion_protection = false
}

resource "google_sql_database" "main" {
  name     = var.db_name
  instance = google_sql_database_instance.main.name
}

resource "google_sql_user" "main" {
  name     = var.db_username
  instance = google_sql_database_instance.main.name
  password = var.db_password
}

# DATABASE_URL connection string stored in Secret Manager
locals {
  database_url = "postgresql://${var.db_username}:${var.db_password}@${google_sql_database_instance.main.private_ip_address}:5432/${var.db_name}?sslmode=disable"
}

resource "google_secret_manager_secret" "db_url" {
  secret_id = local.db_secret_name

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "db_url" {
  secret      = google_secret_manager_secret.db_url.id
  secret_data = local.database_url
}
