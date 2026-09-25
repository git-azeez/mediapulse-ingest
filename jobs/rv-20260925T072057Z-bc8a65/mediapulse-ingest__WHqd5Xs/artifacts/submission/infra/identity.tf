# Identity Platform tenant + OAuth2 client service accounts and keys

resource "google_identity_platform_tenant" "main" {
  provider     = google-beta
  project      = local.project_id
  display_name = "MediaPulse Ingest tenants"
}

# Client service accounts (one per scope)
resource "google_service_account" "client_read" {
  account_id   = "${local.prefix}-read-client"
  display_name = "MediaPulse read scope client"
  project      = local.project_id
}

resource "google_service_account" "client_write" {
  account_id   = "${local.prefix}-write-client"
  display_name = "MediaPulse write scope client"
  project      = local.project_id
}

resource "google_service_account" "client_admin" {
  account_id   = "${local.prefix}-admin-client"
  display_name = "MediaPulse admin scope client"
  project      = local.project_id
}

# User-managed keys serving as OAuth2 client secrets
resource "google_service_account_key" "client_read" {
  service_account_id = google_service_account.client_read.name
  public_key_type    = "TYPE_X509_PEM_FILE"
  private_key_type   = "TYPE_GOOGLE_CREDENTIALS_FILE"
}

resource "google_service_account_key" "client_write" {
  service_account_id = google_service_account.client_write.name
  public_key_type    = "TYPE_X509_PEM_FILE"
  private_key_type   = "TYPE_GOOGLE_CREDENTIALS_FILE"
}

resource "google_service_account_key" "client_admin" {
  service_account_id = google_service_account.client_admin.name
  public_key_type    = "TYPE_X509_PEM_FILE"
  private_key_type   = "TYPE_GOOGLE_CREDENTIALS_FILE"
}
