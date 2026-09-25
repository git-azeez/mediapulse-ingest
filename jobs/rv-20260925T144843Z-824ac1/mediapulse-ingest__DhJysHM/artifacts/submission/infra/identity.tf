resource "google_identity_platform_tenant" "main" {
  project      = local.project
  display_name = "MediaPulse Ingest"
}

# OAuth2 client service accounts (read/write/admin scopes)
resource "google_service_account" "client_read" {
  account_id   = "${local.prefix}-read-client"
  display_name = "MediaPulse read client"
  project      = local.project
}

resource "google_service_account" "client_write" {
  account_id   = "${local.prefix}-write-client"
  display_name = "MediaPulse write client"
  project      = local.project
}

resource "google_service_account" "client_admin" {
  account_id   = "${local.prefix}-admin-client"
  display_name = "MediaPulse admin client"
  project      = local.project
}

resource "google_service_account_key" "client_read" {
  service_account_id = google_service_account.client_read.name
  public_key_type    = "TYPE_NONE"
}

resource "google_service_account_key" "client_write" {
  service_account_id = google_service_account.client_write.name
  public_key_type    = "TYPE_NONE"
}

resource "google_service_account_key" "client_admin" {
  service_account_id = google_service_account.client_admin.name
  public_key_type    = "TYPE_NONE"
}
