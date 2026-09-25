terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.4"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 8.4"
    }
  }
}

locals {
  config  = jsondecode(file("/workspace/config/config.json"))
  prefix  = local.config.resource_prefix
  project = local.config.gcp_project_id
  region  = local.config.region
  zone    = "${local.config.region}-a"
  ep      = local.config.gcp_endpoint_url
  db_name = local.config.db_name
  db_user = local.config.db_username
  db_pass = local.config.db_password
}

provider "google" {
  project = local.project
  region  = local.region
  zone    = local.zone

  access_token = "floci-gcp-local-token"

  compute_custom_endpoint            = "${local.ep}/compute/v1/"
  cloud_run_v2_custom_endpoint        = "${local.ep}/v2/"
  cloudfunctions2_custom_endpoint      = "${local.ep}/v2/"
  firestore_custom_endpoint            = "${local.ep}/v1/"
  storage_custom_endpoint              = "${local.ep}/storage/v1/"
  sql_custom_endpoint                  = "${local.ep}/sql/v1beta4/"
  pubsub_custom_endpoint               = "${local.ep}/v1/"
  cloud_tasks_custom_endpoint          = "${local.ep}/v2/"
  cloud_scheduler_custom_endpoint      = "${local.ep}/v1/"
  kms_custom_endpoint                 = "${local.ep}/v1/"
  secret_manager_custom_endpoint       = "${local.ep}/v1/"
  iam_custom_endpoint                  = "${local.ep}/v1/"
  iam_credentials_custom_endpoint     = "${local.ep}/v1/"
  identity_platform_custom_endpoint   = "${local.ep}/v2/"
  big_query_custom_endpoint            = "${local.ep}/bigquery/v2/"
  logging_custom_endpoint              = "${local.ep}/v2/"
  monitoring_custom_endpoint           = "${local.ep}/v3/"
  cloud_resource_manager_custom_endpoint = "${local.ep}/v1/"
  resource_manager_custom_endpoint     = "${local.ep}/v1/"
  service_usage_custom_endpoint        = "${local.ep}/v1/"
  iam_beta_custom_endpoint             = "${local.ep}/v1/"
  service_networking_custom_endpoint   = "${local.ep}/v1/"
  vpc_access_custom_endpoint           = "${local.ep}/v1/"
}

provider "google-beta" {
  project = local.project
  region  = local.region
  zone    = local.zone

  access_token = "floci-gcp-local-token"

  compute_custom_endpoint            = "${local.ep}/compute/v1/"
  cloud_run_v2_custom_endpoint        = "${local.ep}/v2/"
  cloudfunctions2_custom_endpoint      = "${local.ep}/v2/"
  firestore_custom_endpoint            = "${local.ep}/v1/"
  storage_custom_endpoint              = "${local.ep}/storage/v1/"
  sql_custom_endpoint                  = "${local.ep}/sql/v1beta4/"
  pubsub_custom_endpoint               = "${local.ep}/v1/"
  cloud_tasks_custom_endpoint          = "${local.ep}/v2/"
  cloud_scheduler_custom_endpoint      = "${local.ep}/v1/"
  kms_custom_endpoint                 = "${local.ep}/v1/"
  secret_manager_custom_endpoint       = "${local.ep}/v1/"
  iam_custom_endpoint                  = "${local.ep}/v1/"
  iam_credentials_custom_endpoint     = "${local.ep}/v1/"
  identity_platform_custom_endpoint   = "${local.ep}/v2/"
  big_query_custom_endpoint            = "${local.ep}/bigquery/v2/"
  logging_custom_endpoint              = "${local.ep}/v2/"
  monitoring_custom_endpoint           = "${local.ep}/v3/"
  cloud_resource_manager_custom_endpoint = "${local.ep}/v1/"
  resource_manager_custom_endpoint     = "${local.ep}/v1/"
  service_usage_custom_endpoint        = "${local.ep}/v1/"
  iam_beta_custom_endpoint             = "${local.ep}/v1/"
  service_networking_custom_endpoint   = "${local.ep}/v1/"
  vpc_access_custom_endpoint           = "${local.ep}/v1/"
}
