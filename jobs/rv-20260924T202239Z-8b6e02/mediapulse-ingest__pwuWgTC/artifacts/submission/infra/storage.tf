resource "google_storage_bucket" "audit" {
  name                        = local.audit_bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "ENFORCED"
  force_destroy               = true
  labels                      = local.common_labels

  versioning {
    enabled = true
  }

  encryption {
    default_kms_key_name = google_kms_crypto_key.audit.id
  }

  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }
}

resource "google_bigquery_dataset" "audit" {
  dataset_id = local.bq_dataset_id
  location   = var.region
  labels     = local.common_labels
}

resource "google_bigquery_table" "audit_events" {
  dataset_id = google_bigquery_dataset.audit.dataset_id
  table_id   = local.bq_table_id
  labels      = local.common_labels

  schema = jsonencode([
    { name = "eventId", type = "STRING" },
    { name = "eventType", type = "STRING" },
    { name = "aggregateId", type = "STRING" },
    { name = "aggregateVersion", type = "INTEGER" },
    { name = "ownerId", type = "STRING" },
    { name = "occurredAt", type = "TIMESTAMP" },
    { name = "correlationId", type = "STRING" },
    { name = "data", type = "JSON" },
    { name = "batchId", type = "STRING" },
    { name = "ingestedAt", type = "TIMESTAMP" }
  ])
}
