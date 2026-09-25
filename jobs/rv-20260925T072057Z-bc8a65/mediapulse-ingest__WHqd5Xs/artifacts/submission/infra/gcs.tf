# GCS audit bucket + BigQuery audit dataset

resource "google_storage_bucket" "audit" {
  name          = "${local.prefix}-audit-logs"
  project       = local.project_id
  location      = "US-EAST1"
  force_destroy = true

  public_access_prevention = "enforced"

  versioning {
    enabled = true
  }

  encryption {
    default_kms_key_name = google_kms_crypto_key.audit.id
  }

  uniform_bucket_level_access = true
}

resource "google_bigquery_dataset" "audit" {
  dataset_id = "${replace(local.prefix, "-", "_")}_audit"
  project    = local.project_id
  location   = "US"

  default_encryption_configuration {
    kms_key_name = google_kms_crypto_key.audit.id
  }
}

resource "google_bigquery_table" "audit_events" {
  project    = local.project_id
  dataset_id = google_bigquery_dataset.audit.dataset_id
  table_id   = "audit_events"

  schema = jsonencode([
    { name = "eventId",       type = "STRING", mode = "REQUIRED" },
    { name = "eventType",     type = "STRING", mode = "REQUIRED" },
    { name = "aggregateId",   type = "STRING", mode = "REQUIRED" },
    { name = "aggregateVersion", type = "INTEGER", mode = "REQUIRED" },
    { name = "ownerId",        type = "STRING", mode = "REQUIRED" },
    { name = "occurredAt",     type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "correlationId",  type = "STRING" },
    { name = "batch",          type = "STRING" },
  ])
}
