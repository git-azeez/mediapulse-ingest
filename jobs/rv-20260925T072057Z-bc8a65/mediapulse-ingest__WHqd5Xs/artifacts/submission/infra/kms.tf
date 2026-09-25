# Cloud KMS CMEK keys

resource "google_kms_key_ring" "ring" {
  name     = "${local.prefix}-keyring"
  project  = local.project_id
  location = local.region
}

resource "google_kms_crypto_key" "database" {
  name            = "${local.prefix}-db-key"
  key_ring        = google_kms_key_ring.ring.id
  rotation_period = "7776000s"
  purpose         = "ENCRYPT_DECRYPT"
}

resource "google_kms_crypto_key" "messaging" {
  name            = "${local.prefix}-messaging-key"
  key_ring        = google_kms_key_ring.ring.id
  rotation_period = "7776000s"
  purpose         = "ENCRYPT_DECRYPT"
}

resource "google_kms_crypto_key" "projection" {
  name            = "${local.prefix}-projection-key"
  key_ring        = google_kms_key_ring.ring.id
  rotation_period = "7776000s"
  purpose         = "ENCRYPT_DECRYPT"
}

resource "google_kms_crypto_key" "audit" {
  name            = "${local.prefix}-audit-key"
  key_ring        = google_kms_key_ring.ring.id
  rotation_period = "7776000s"
  purpose         = "ENCRYPT_DECRYPT"
}
