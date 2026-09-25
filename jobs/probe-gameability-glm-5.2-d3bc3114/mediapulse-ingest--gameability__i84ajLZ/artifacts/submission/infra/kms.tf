resource "google_kms_key_ring" "mediapulse" {
  name     = "${var.prefix}-keyring"
  location = var.gcp_region
}

resource "google_kms_crypto_key" "database" {
  name     = "${var.prefix}-database-cmek"
  key_ring = google_kms_key_ring.mediapulse.id
  labels   = local.common_labels
}

resource "google_kms_crypto_key" "messaging" {
  name     = "${var.prefix}-messaging-cmek"
  key_ring = google_kms_key_ring.mediapulse.id
  labels   = local.common_labels
}

resource "google_kms_crypto_key" "projection" {
  name     = "${var.prefix}-projection-cmek"
  key_ring = google_kms_key_ring.mediapulse.id
  labels   = local.common_labels
}

resource "google_kms_crypto_key" "audit" {
  name     = "${var.prefix}-audit-cmek"
  key_ring = google_kms_key_ring.mediapulse.id
  labels   = local.common_labels
}
