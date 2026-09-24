resource "google_kms_key_ring" "keyring" {
  name     = "${var.prefix}-keyring"
  location = var.gcp_region
}

resource "google_kms_crypto_key" "crypto_key" {
  name            = "${var.prefix}-cmek-key"
  key_ring        = google_kms_key_ring.keyring.id
  rotation_period = "7776000s" # 90 days

  lifecycle {
    prevent_destroy = false
  }
}
