resource "google_firestore_database" "projections" {
  project                           = var.gcp_project_id
  name                              = "${var.prefix}-projections"
  location_id                       = var.gcp_region
  type                              = "FIRESTORE_NATIVE"
  concurrency_mode                  = "OPTIMISTIC"
  delete_protection_state           = "DELETE_PROTECTION_DISABLED"
  deletion_policy                   = "DELETE"
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

resource "google_storage_bucket" "audit" {
  name                        = "${var.prefix}-${var.gcp_project_id}-audit"
  location                    = var.gcp_region
  force_destroy               = true
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = true
  }

  labels = merge(local.common_labels, { data_role = "audit" })
}

resource "google_bigquery_dataset" "audit_analytics" {
  dataset_id                 = replace("${var.prefix}_audit_analytics", "-", "_")
  location                   = var.gcp_region
  delete_contents_on_destroy = true

  labels = local.common_labels
}
