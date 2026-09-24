locals {
  project_slug = "mediapulse-ingest"

  # GCP service account IDs must be ≤ 30 chars total.
  # Longest suffix used is "-pubsub-push-sa" (15 chars), leaving 15 chars for the prefix.
  sa_prefix = substr(var.prefix, 0, 15)

  common_labels = {
    project               = local.project_slug
    deployment            = var.prefix
    mediapulse_deployment = var.prefix
    managed_by            = "terraform"
  }

  ingress_subnet_cidr = "10.84.0.0/24"
  private_subnet_cidr = "10.84.10.0/24"

  api_min_instances = 2
  api_max_instances = 6

  gcp_endpoint_without_scheme = trimprefix(trimprefix(var.gcp_endpoint_url, "http://"), "https://")
  gcp_endpoint_host           = split(":", local.gcp_endpoint_without_scheme)[0]

  database_host = coalesce(google_sql_database_instance.events.private_ip_address, local.gcp_endpoint_host)
  database_port = 5432
  database_url  = nonsensitive("postgresql://${urlencode(var.db_username)}:${urlencode(var.db_password)}@${local.database_host}:${local.database_port}/${var.db_name}?sslmode=disable")

  datastore_emulator_host = "${local.gcp_endpoint_host}:4588"
  firestore_emulator_host = "${local.gcp_endpoint_host}:4588"
  pubsub_emulator_host    = "${local.gcp_endpoint_host}:4588"
  storage_emulator_host   = var.gcp_endpoint_url

  auth_resource_server = "mediapulse"
  auth_issuer          = "${var.gcp_endpoint_url}/identitytoolkit.googleapis.com/v1/projects/${var.gcp_project_id}"
  auth_jwks_url        = "${var.gcp_endpoint_url}/robot/v1/metadata/jwk/securetoken@system.gserviceaccount.com"
  auth_audiences = join(",", [
    google_service_account.client_read.unique_id,
    google_service_account.client_write.unique_id,
    google_service_account.client_admin.unique_id,
  ])
}
