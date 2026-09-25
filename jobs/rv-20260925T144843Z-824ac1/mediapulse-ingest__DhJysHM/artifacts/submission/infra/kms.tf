resource "google_kms_key_ring" "kr" {
  name     = "${local.prefix}-keyring"
  project  = local.project
  location = local.region
}

resource "google_kms_crypto_key" "database" {
  name            = "${local.prefix}-database-key"
  key_ring        = google_kms_key_ring.kr.id
  rotation_period = "7776000s"
  labels          = local.labels
}

resource "google_kms_crypto_key" "messaging" {
  name            = "${local.prefix}-messaging-key"
  key_ring        = google_kms_key_ring.kr.id
  rotation_period = "7776000s"
  labels          = local.labels
}

resource "google_kms_crypto_key" "projection" {
  name            = "${local.prefix}-projection-key"
  key_ring        = google_kms_key_ring.kr.id
  rotation_period = "7776000s"
  labels          = local.labels
}

resource "google_kms_crypto_key" "audit" {
  name            = "${local.prefix}-audit-key"
  key_ring        = google_kms_key_ring.kr.id
  rotation_period = "7776000s"
  labels          = local.labels
}
