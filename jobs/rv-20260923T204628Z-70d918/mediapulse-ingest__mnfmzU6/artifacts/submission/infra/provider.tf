provider "google" {
  project                     = var.gcp_project_id
  region                      = var.gcp_region
  access_token                = "floci-gcp-local-token"
  user_project_override       = false

  compute_custom_endpoint        = "${var.gcp_endpoint_url}/compute/v1/"
  storage_custom_endpoint        = "${var.gcp_endpoint_url}/storage/v1/"
  pubsub_custom_endpoint         = "${var.gcp_endpoint_url}/v1/"
  firestore_custom_endpoint      = "${var.gcp_endpoint_url}/v1/"
  datastore_custom_endpoint      = "${var.gcp_endpoint_url}/v1/"
  sql_custom_endpoint            = "${var.gcp_endpoint_url}/"
  run_custom_endpoint            = "${var.gcp_endpoint_url}/"
  cloudfunctions2_custom_endpoint = "${var.gcp_endpoint_url}/"
  cloud_scheduler_custom_endpoint = "${var.gcp_endpoint_url}/"
  cloud_tasks_custom_endpoint    = "${var.gcp_endpoint_url}/"
  secret_manager_custom_endpoint = "${var.gcp_endpoint_url}/"
  kms_custom_endpoint            = "${var.gcp_endpoint_url}/"
  iam_custom_endpoint            = "${var.gcp_endpoint_url}/"
  logging_custom_endpoint        = "${var.gcp_endpoint_url}/"
  monitoring_custom_endpoint     = "${var.gcp_endpoint_url}/"
  bigquery_custom_endpoint       = "${var.gcp_endpoint_url}/bigquery/v2/"
  eventarc_custom_endpoint       = "${var.gcp_endpoint_url}/"

  default_labels = local.common_labels
}

provider "google-beta" {
  project                     = var.gcp_project_id
  region                      = var.gcp_region
  access_token                = "floci-gcp-local-token"
  user_project_override       = false

  compute_custom_endpoint        = "${var.gcp_endpoint_url}/compute/v1/"
  storage_custom_endpoint        = "${var.gcp_endpoint_url}/storage/v1/"
  pubsub_custom_endpoint         = "${var.gcp_endpoint_url}/v1/"
  firestore_custom_endpoint      = "${var.gcp_endpoint_url}/v1/"
  datastore_custom_endpoint      = "${var.gcp_endpoint_url}/v1/"
  sql_custom_endpoint            = "${var.gcp_endpoint_url}/"
  run_custom_endpoint            = "${var.gcp_endpoint_url}/"
  cloudfunctions2_custom_endpoint = "${var.gcp_endpoint_url}/"
  cloud_scheduler_custom_endpoint = "${var.gcp_endpoint_url}/"
  cloud_tasks_custom_endpoint    = "${var.gcp_endpoint_url}/"
  secret_manager_custom_endpoint = "${var.gcp_endpoint_url}/"
  kms_custom_endpoint            = "${var.gcp_endpoint_url}/"
  iam_custom_endpoint            = "${var.gcp_endpoint_url}/"
   identity_platform_custom_endpoint = "${var.gcp_endpoint_url}/"
  logging_custom_endpoint        = "${var.gcp_endpoint_url}/"
  monitoring_custom_endpoint     = "${var.gcp_endpoint_url}/"
  bigquery_custom_endpoint       = "${var.gcp_endpoint_url}/bigquery/v2/"
  eventarc_custom_endpoint       = "${var.gcp_endpoint_url}/"

  default_labels = local.common_labels
}
