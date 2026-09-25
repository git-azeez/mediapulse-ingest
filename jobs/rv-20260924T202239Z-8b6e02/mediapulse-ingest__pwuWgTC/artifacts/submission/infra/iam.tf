# Runtime component service accounts
resource "google_service_account" "api" {
  account_id   = local.api_sa
  display_name = "MediaPulse API Cloud Run runtime SA"
  description  = "Least-privilege SA for the MediaPulse Ingest API Cloud Run service"
}

resource "google_service_account" "processor" {
  account_id   = local.proc_sa
  display_name = "MediaPulse Processor function SA"
}

resource "google_service_account" "relay" {
  account_id   = local.relay_sa
  display_name = "MediaPulse Outbox Relay function SA"

}

resource "google_service_account" "archiver" {
  account_id   = local.archiver_sa
  display_name = "MediaPulse Audit Archiver function SA"
}

resource "google_service_account" "scheduler" {
  account_id   = local.sched_sa
  display_name = "MediaPulse Cloud Scheduler invoker SA"
}

# OAuth2 client service accounts for read/write/admin scopes
resource "google_service_account" "client_read" {
  account_id   = local.read_sa
  display_name = "MediaPulse OAuth2 read-scope client"
}

resource "google_service_account" "client_write" {
  account_id   = local.write_sa
  display_name = "MediaPulse OAuth2 write-scope client"
}

resource "google_service_account" "client_admin" {
  account_id   = local.admin_sa
  display_name = "MediaPulse OAuth2 admin-scope client"
}

# User-managed keys serve as OAuth2 client secrets
resource "google_service_account_key" "client_read" {
  service_account_id = google_service_account.client_read.name
}

resource "google_service_account_key" "client_write" {
  service_account_id = google_service_account.client_write.name
}

resource "google_service_account_key" "client_admin" {
  service_account_id = google_service_account.client_admin.name
}

# Identity Platform tenant for scoped JWT auth
resource "google_identity_platform_tenant" "main" {
  provider     = google-beta
  project      = var.project_id
  display_name = "MediaPulse Ingest tenant"
}

# ---- IAM role bindings (least privilege) ----

# API service account
resource "google_project_iam_member" "api_cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_datastore_viewer" {
  project = var.project_id
  role    = "roles/datastore.viewer"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.api.email}"
}

# Processor service account
resource "google_project_iam_member" "proc_pubsub_subscriber" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.processor.email}"
}

resource "google_project_iam_member" "proc_datastore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.processor.email}"
}

resource "google_cloudfunctions2_function_iam_member" "proc_invoker_pubsub" {
  project       = var.project_id
  location      = var.region
  cloud_function = google_cloudfunctions2_function.processor.name
  role          = "roles/cloudfunctions.invoker"
  member        = "serviceAccount:${google_service_account.processor.email}"
}

# Relay service account
resource "google_project_iam_member" "relay_cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.relay.email}"
}

resource "google_pubsub_topic_iam_member" "relay_publisher" {
  project = var.project_id
  topic   = google_pubsub_topic.main.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.relay.email}"
}

# Archiver service account
resource "google_project_iam_member" "archiver_cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.archiver.email}"
}

resource "google_storage_bucket_iam_member" "archiver_object_admin" {
  bucket = google_storage_bucket.audit.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.archiver.email}"
}

# Scheduler invoker SA -> invoker on relay and archiver functions
resource "google_cloudfunctions2_function_iam_member" "relay_invoker" {
  project        = var.project_id
  location       = var.region
  cloud_function = google_cloudfunctions2_function.relay.name
  role           = "roles/cloudfunctions.invoker"
  member         = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_cloudfunctions2_function_iam_member" "archiver_invoker" {
  project        = var.project_id
  location       = var.region
  cloud_function = google_cloudfunctions2_function.archiver.name
  role           = "roles/cloudfunctions.invoker"
  member         = "serviceAccount:${google_service_account.scheduler.email}"
}

# Allow the API service account to read the DB connection secret
resource "google_secret_manager_secret_iam_member" "api_secret_accessor" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.db_url.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

# KMS encrypter/decrypter for the runtime SAs that use CMEK-backed resources
resource "google_kms_crypto_key_iam_member" "api_kms" {
  crypto_key_id = google_kms_crypto_key.database.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:${google_service_account.api.email}"
}
