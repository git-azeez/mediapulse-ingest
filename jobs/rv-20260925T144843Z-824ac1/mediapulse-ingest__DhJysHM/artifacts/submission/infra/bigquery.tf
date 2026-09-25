resource "google_bigquery_dataset" "audit" {
  dataset_id = replace("${local.prefix}_audit", "-", "_")
  project    = local.project
  location   = local.region
  labels     = local.labels

  access {
    role          = "OWNER"
    special_group = "projectOwners"
  }
}

resource "google_bigquery_table" "events" {
  project    = local.project
  dataset_id = google_bigquery_dataset.audit.dataset_id
  table_id   = "audit_events"
  labels     = local.labels

  deletion_protection = false

  schema = jsonencode([
    { name = "eventId", type = "STRING" },
    { name = "eventType", type = "STRING" },
    { name = "aggregateId", type = "STRING" },
    { name = "aggregateVersion", type = "INTEGER" },
    { name = "ownerId", type = "STRING" },
    { name = "occurredAt", type = "TIMESTAMP" },
    { name = "correlationId", type = "STRING" },
    { name = "batchId", type = "STRING" },
    { name = "batchTimestamp", type = "TIMESTAMP" },
  ])
}
