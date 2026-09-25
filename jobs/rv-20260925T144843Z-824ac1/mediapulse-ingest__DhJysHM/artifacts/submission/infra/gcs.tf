resource "google_storage_bucket" "audit" {
  name          = "${local.prefix}-audit-logs"
  project       = local.project
  location      = local.region
  force_destroy = true
  labels        = local.labels

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = true
  }

  encryption {
    default_kms_key_name = google_kms_crypto_key.audit.id
  }
}

resource "google_storage_bucket_iam_member" "archiver_admin" {
  bucket = google_storage_bucket.audit.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.archiver.email}"
}
