provider "google" {
  project               = var.gcp_project_id
  region                = var.gcp_region
  access_token          = "floci-gcp-local-token"
  user_project_override = false

  compute_custom_endpoint           = "${var.gcp_endpoint_url}/compute/v1/"
  storage_custom_endpoint           = "${var.gcp_endpoint_url}/storage/v1/"
  pubsub_custom_endpoint            = "${var.gcp_endpoint_url}/v1/"
  firestore_custom_endpoint         = "${var.gcp_endpoint_url}/v1/"
  sql_custom_endpoint               = "${var.gcp_endpoint_url}/sql/v1beta4/"
  cloud_run_custom_endpoint         = "${var.gcp_endpoint_url}/run/v1/"
  cloud_run_v2_custom_endpoint      = "${var.gcp_endpoint_url}/v2/"
  cloudfunctions2_custom_endpoint   = "${var.gcp_endpoint_url}/v2/"
  cloud_scheduler_custom_endpoint   = "${var.gcp_endpoint_url}/v1/"
  cloud_tasks_custom_endpoint       = "${var.gcp_endpoint_url}/v2/"
  secret_manager_custom_endpoint    = "${var.gcp_endpoint_url}/v1/"
  kms_custom_endpoint               = "${var.gcp_endpoint_url}/v1/"
  iam_custom_endpoint                    = "${var.gcp_endpoint_url}/v1/"
  iam_beta_custom_endpoint               = "${var.gcp_endpoint_url}/v1/"
  iam_credentials_custom_endpoint        = "${var.gcp_endpoint_url}/v1/"
  resource_manager_custom_endpoint       = "${var.gcp_endpoint_url}/v1/"
  resource_manager_v3_custom_endpoint    = "${var.gcp_endpoint_url}/v3/"
  cloud_resource_manager_custom_endpoint = "${var.gcp_endpoint_url}/v1/"
  service_usage_custom_endpoint          = "${var.gcp_endpoint_url}/v1/"
  identity_platform_custom_endpoint      = "${var.gcp_endpoint_url}/v2/"
  logging_custom_endpoint                = "${var.gcp_endpoint_url}/v2/"
  monitoring_custom_endpoint             = "${var.gcp_endpoint_url}/v3/"
  big_query_custom_endpoint              = "${var.gcp_endpoint_url}/bigquery/v2/"
  eventarc_custom_endpoint               = "${var.gcp_endpoint_url}/v1/"

  default_labels = local.common_labels
}

provider "google-beta" {
  project               = var.gcp_project_id
  region                = var.gcp_region
  access_token          = "floci-gcp-local-token"
  user_project_override = false

  compute_custom_endpoint                = "${var.gcp_endpoint_url}/compute/v1/"
  storage_custom_endpoint                = "${var.gcp_endpoint_url}/storage/v1/"
  pubsub_custom_endpoint                 = "${var.gcp_endpoint_url}/v1/"
  firestore_custom_endpoint              = "${var.gcp_endpoint_url}/v1/"
  sql_custom_endpoint                    = "${var.gcp_endpoint_url}/sql/v1beta4/"
  cloud_run_custom_endpoint              = "${var.gcp_endpoint_url}/run/v1/"
  cloud_run_v2_custom_endpoint           = "${var.gcp_endpoint_url}/v2/"
  cloudfunctions2_custom_endpoint        = "${var.gcp_endpoint_url}/v2/"
  cloud_scheduler_custom_endpoint        = "${var.gcp_endpoint_url}/v1/"
  cloud_tasks_custom_endpoint            = "${var.gcp_endpoint_url}/v2/"
  secret_manager_custom_endpoint         = "${var.gcp_endpoint_url}/v1/"
  kms_custom_endpoint                    = "${var.gcp_endpoint_url}/v1/"
  iam_custom_endpoint                    = "${var.gcp_endpoint_url}/v1/"
  iam_beta_custom_endpoint               = "${var.gcp_endpoint_url}/v1/"
  iam_credentials_custom_endpoint        = "${var.gcp_endpoint_url}/v1/"
  resource_manager_custom_endpoint       = "${var.gcp_endpoint_url}/v1/"
  resource_manager_v3_custom_endpoint    = "${var.gcp_endpoint_url}/v3/"
  cloud_resource_manager_custom_endpoint = "${var.gcp_endpoint_url}/v1/"
  service_usage_custom_endpoint          = "${var.gcp_endpoint_url}/v1/"
  identity_platform_custom_endpoint      = "${var.gcp_endpoint_url}/v2/"
  logging_custom_endpoint                = "${var.gcp_endpoint_url}/v2/"
  monitoring_custom_endpoint             = "${var.gcp_endpoint_url}/v3/"
  big_query_custom_endpoint              = "${var.gcp_endpoint_url}/bigquery/v2/"
  eventarc_custom_endpoint               = "${var.gcp_endpoint_url}/v1/"

  default_labels = local.common_labels
}
