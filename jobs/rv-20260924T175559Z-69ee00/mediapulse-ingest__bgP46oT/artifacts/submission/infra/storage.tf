resource "google_sql_database_instance" "events" {
  name                = "${var.prefix}-events-pg"
  region              = var.gcp_region
  database_version    = "POSTGRES_16"
  encryption_key_name = google_kms_crypto_key.database.id
  deletion_protection = false

  settings {
    tier              = "db-custom-2-4096"
    availability_type = "ZONAL"
    disk_size         = 20
    disk_type         = "PD_SSD"
    disk_autoresize   = true

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.ingest.id
    }

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
    }

    user_labels = merge(local.common_labels, {
      data_role  = "event-store-outbox"
      encryption = "cmek"
    })
  }
}

resource "google_sql_database" "mediapulse" {
  name     = var.db_name
  instance = google_sql_database_instance.events.name
}

resource "google_sql_user" "app" {
  name     = var.db_username
  instance = google_sql_database_instance.events.name
  password = var.db_password
}

resource "google_secret_manager_secret" "db_credentials" {
  secret_id = "${var.prefix}-db-credentials"

  replication {
    auto {}
  }

  labels = merge(local.common_labels, {
    data_role = "database-secret"
  })
}

resource "google_secret_manager_secret_version" "db_credentials_v1" {
  secret      = google_secret_manager_secret.db_credentials.id
  secret_data = local.database_url
}

resource "google_firestore_database" "projections" {
  project                           = var.gcp_project_id
  name                              = "${var.prefix}-projections"
  location_id                       = var.gcp_region
  type                              = "FIRESTORE_NATIVE"
  concurrency_mode                  = "OPTIMISTIC"
  point_in_time_recovery_enablement = "POINT_IN_TIME_RECOVERY_ENABLED"
  delete_protection_state           = "DELETE_PROTECTION_DISABLED"
  deletion_policy                   = "DELETE"

  cmek_config {
    kms_key_name = google_kms_crypto_key.projection.id
  }
}

resource "google_firestore_index" "media_cache" {
  project    = var.gcp_project_id
  database   = google_firestore_database.projections.name
  collection = "MediaCache"

  fields {
    field_path = "media_id"
    order      = "ASCENDING"
  }

  fields {
    field_path = "expires_at"
    order      = "ASCENDING"
  }
}

resource "google_bigquery_dataset" "audit_analytics" {
  dataset_id                 = replace("${var.prefix}_audit_analytics", "-", "_")
  location                   = var.gcp_region
  delete_contents_on_destroy = true

  default_encryption_configuration {
    kms_key_name = google_kms_crypto_key.audit.id
  }

  labels = merge(local.common_labels, {
    data_role = "audit-analytics"
  })
}

resource "google_bigquery_table" "archived_events" {
  dataset_id          = google_bigquery_dataset.audit_analytics.dataset_id
  table_id            = "archived_events"
  deletion_protection = false

  labels = merge(local.common_labels, {
    data_role = "audit-analytics-table"
  })
}

resource "google_storage_bucket" "audit" {
  name                        = "${var.prefix}-${var.gcp_project_id}-audit"
  location                    = var.gcp_region
  force_destroy               = true
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = true
  }

  encryption {
    default_kms_key_name = google_kms_crypto_key.audit.id
  }

  labels = merge(local.common_labels, {
    data_role = "immutable-audit"
  })
}
