resource "google_kms_key_ring" "mediapulse" {
  name     = "${var.prefix}-keyring"
  location = var.gcp_region
}

resource "google_kms_crypto_key" "database" {
  name            = "${var.prefix}-database-cmek"
  key_ring        = google_kms_key_ring.mediapulse.id
  rotation_period = "7776000s"
  purpose         = "ENCRYPT_DECRYPT"

  labels = merge(local.common_labels, {
    key_scope = "cloud-sql"
  })
}

resource "google_kms_crypto_key" "messaging" {
  name            = "${var.prefix}-messaging-cmek"
  key_ring        = google_kms_key_ring.mediapulse.id
  rotation_period = "7776000s"
  purpose         = "ENCRYPT_DECRYPT"

  labels = merge(local.common_labels, {
    key_scope = "pubsub"
  })
}

resource "google_kms_crypto_key" "projection" {
  name            = "${var.prefix}-projection-cmek"
  key_ring        = google_kms_key_ring.mediapulse.id
  rotation_period = "7776000s"
  purpose         = "ENCRYPT_DECRYPT"

  labels = merge(local.common_labels, {
    key_scope = "firestore-datastore"
  })
}

resource "google_kms_crypto_key" "audit" {
  name            = "${var.prefix}-audit-cmek"
  key_ring        = google_kms_key_ring.mediapulse.id
  rotation_period = "7776000s"
  purpose         = "ENCRYPT_DECRYPT"

  labels = merge(local.common_labels, {
    key_scope = "gcs-audit"
  })
}
