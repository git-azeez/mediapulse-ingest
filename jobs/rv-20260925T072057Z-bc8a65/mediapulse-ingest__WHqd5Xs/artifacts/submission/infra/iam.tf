# Runtime service accounts + least-privilege IAM bindings

resource "google_service_account" "api" {
  account_id   = "${local.prefix}-api-sa"
  display_name = "MediaPulse API Cloud Run SA"
  project      = local.project_id
}

resource "google_service_account" "processor" {
  account_id   = "${local.prefix}-processor-sa"
  display_name = "MediaPulse projector Cloud Function SA"
  project      = local.project_id
}

resource "google_service_account" "relay" {
  account_id   = "${local.prefix}-relay-sa"
  display_name = "MediaPulse outbox relay Cloud Function SA"
  project      = local.project_id
}

resource "google_service_account" "archiver" {
  account_id   = "${local.prefix}-archiver-sa"
  display_name = "MediaPulse audit archiver Cloud Function SA"
  project      = local.project_id
}

resource "google_service_account" "scheduler" {
  account_id   = "${local.prefix}-scheduler-sa"
  display_name = "MediaPulse Cloud Scheduler invoker SA"
  project      = local.project_id
}

# ---- API service account roles ----
resource "google_project_iam_member" "api_cloudsql_client" {
  project = local.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_datastore_viewer" {
  project = local.project_id
  role    = "roles/datastore.viewer"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_pubsub_publisher" {
  project = local.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_secret_manager_secret_iam_member" "api_db_url_accessor" {
  project   = local.project_id
  secret_id = google_secret_manager_secret.db_url.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

resource "google_secret_manager_secret_iam_member" "api_db_pw_accessor" {
  project   = local.project_id
  secret_id = google_secret_manager_secret.db_password.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

# ---- Processor service account roles ----
resource "google_project_iam_member" "proc_datastore_user" {
  project = local.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.processor.email}"
}

resource "google_pubsub_subscription_iam_member" "proc_subscriber" {
  project      = local.project_id
  subscription = google_pubsub_subscription.processor_push.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.processor.email}"
}

# ---- Relay service account roles ----
resource "google_project_iam_member" "relay_cloudsql_client" {
  project = local.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.relay.email}"
}

resource "google_pubsub_topic_iam_member" "relay_publisher" {
  project = local.project_id
  topic   = google_pubsub_topic.main.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.relay.email}"
}

# ---- Archiver service account roles ----
resource "google_project_iam_member" "archiver_cloudsql_client" {
  project = local.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.archiver.email}"
}

resource "google_storage_bucket_iam_member" "archiver_object_admin" {
  bucket = google_storage_bucket.audit.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.archiver.email}"
}

# Allow Pub/Sub service agent to publish to DLQ / manage dead letters
resource "google_pubsub_topic_iam_member" "dlq_publisher_api" {
  project = local.project_id
  topic   = google_pubsub_topic.dlq.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.api.email}"
}

# KMS encrypter/decrypter for service agents that use CMEK
resource "google_kms_crypto_key_iam_member" "sql_decrypter" {
  crypto_key_id = google_kms_crypto_key.database.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:service-${data.google_project.this.number}@gcp-sa-cloud-sql.iam.gserviceaccount.com"
}
