provider "google" {
  project = var.project_id
  region  = var.region

  compute_custom_endpoint           = "${var.gcp_endpoint_url}/compute/v1/"
  cloud_run_v2_custom_endpoint       = "${var.gcp_endpoint_url}/v2/"
  sql_custom_endpoint                = "${var.gcp_endpoint_url}/sql/v1beta4/"
  storage_custom_endpoint            = "${var.gcp_endpoint_url}/storage/v1/"
  pubsub_custom_endpoint             = "${var.gcp_endpoint_url}/v1/"
  cloud_tasks_custom_endpoint        = "${var.gcp_endpoint_url}/v2/"
  cloudfunctions2_custom_endpoint    = "${var.gcp_endpoint_url}/v2/"
  firestore_custom_endpoint          = "${var.gcp_endpoint_url}/v1/"
  big_query_custom_endpoint           = "${var.gcp_endpoint_url}/bigquery/v2/"
  cloud_scheduler_custom_endpoint    = "${var.gcp_endpoint_url}/v1/"
  identity_platform_custom_endpoint  = "${var.gcp_endpoint_url}/v2/"
  kms_custom_endpoint                = "${var.gcp_endpoint_url}/v1/"
  secret_manager_custom_endpoint     = "${var.gcp_endpoint_url}/v1/"
  iam_custom_endpoint                = "${var.gcp_endpoint_url}/v1/"
  iam_credentials_custom_endpoint    = "${var.gcp_endpoint_url}/v1/"
  logging_custom_endpoint            = "${var.gcp_endpoint_url}/v2/"
  monitoring_custom_endpoint         = "${var.gcp_endpoint_url}/v3/"
  service_usage_custom_endpoint      = "${var.gcp_endpoint_url}/v1/"
  resource_manager_custom_endpoint   = "${var.gcp_endpoint_url}/v1/"
  vpc_access_custom_endpoint         = "${var.gcp_endpoint_url}/v1/"
  eventarc_custom_endpoint           = "${var.gcp_endpoint_url}/v1/"
}

provider "google-beta" {
  project = var.project_id
  region  = var.region

  compute_custom_endpoint           = "${var.gcp_endpoint_url}/compute/v1/"
  cloud_run_v2_custom_endpoint      = "${var.gcp_endpoint_url}/v2/"
  cloudfunctions2_custom_endpoint    = "${var.gcp_endpoint_url}/v2/"
  firestore_custom_endpoint          = "${var.gcp_endpoint_url}/v1/"
  identity_platform_custom_endpoint  = "${var.gcp_endpoint_url}/v2/"
  kms_custom_endpoint                = "${var.gcp_endpoint_url}/v1/"
  pubsub_custom_endpoint             = "${var.gcp_endpoint_url}/v1/"
  sql_custom_endpoint                = "${var.gcp_endpoint_url}/sql/v1beta4/"
  storage_custom_endpoint            = "${var.gcp_endpoint_url}/storage/v1/"
  secret_manager_custom_endpoint     = "${var.gcp_endpoint_url}/v1/"
  iam_custom_endpoint                = "${var.gcp_endpoint_url}/v1/"
  logging_custom_endpoint            = "${var.gcp_endpoint_url}/v2/"
  monitoring_custom_endpoint         = "${var.gcp_endpoint_url}/v3/"
  big_query_custom_endpoint           = "${var.gcp_endpoint_url}/bigquery/v2/"
  cloud_scheduler_custom_endpoint    = "${var.gcp_endpoint_url}/v1/"
  cloud_tasks_custom_endpoint        = "${var.gcp_endpoint_url}/v2/"
  resource_manager_custom_endpoint   = "${var.gcp_endpoint_url}/v1/"
  service_usage_custom_endpoint      = "${var.gcp_endpoint_url}/v1/"
}
