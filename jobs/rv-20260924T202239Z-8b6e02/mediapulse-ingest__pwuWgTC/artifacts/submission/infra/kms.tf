resource "google_kms_key_ring" "main" {
  name     = local.keyring_name
  location = var.region
}

resource "google_kms_crypto_key" "database" {
  name            = local.kms_db_key
  key_ring        = google_kms_key_ring.main.id
  rotation_period = "7776000s"
  labels          = local.common_labels
}

resource "google_kms_crypto_key" "messaging" {
  name            = local.kms_msg_key
  key_ring        = google_kms_key_ring.main.id
  rotation_period = "7776000s"
  labels          = local.common_labels
}

resource "google_kms_crypto_key" "projection" {
  name            = local.kms_proj_key
  key_ring        = google_kms_key_ring.main.id
  rotation_period = "7776000s"
  labels          = local.common_labels
}

resource "google_kms_crypto_key" "audit" {
  name            = local.kms_audit_key
  key_ring        = google_kms_key_ring.main.id
  rotation_period = "7776000s"
  labels          = local.common_labels
}
