terraform {
  required_version = ">= 1.6"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 6.0"
    }
  }
}

locals {
  cfg = jsondecode(file("/workspace/config/config.json"))

  prefix        = local.cfg.resource_prefix
  project_id    = local.cfg.gcp_project_id
  region        = local.cfg.region
  gcp_endpoint  = local.cfg.gcp_endpoint_url
  db_name       = local.cfg.db_name
  db_username   = local.cfg.db_username
  db_password   = local.cfg.db_password

  datastore_namespace = "${local.prefix}-cache"

  common_labels = {
    mediapulse_deployment = local.prefix
  }
}

provider "google" {
  access_token = "mock-access-token"
  project      = local.project_id
  region       = local.region

  compute_custom_endpoint               = "${local.gcp_endpoint}/compute/v1/"
  storage_custom_endpoint                = "${local.gcp_endpoint}/storage/v1/"
  sql_custom_endpoint                    = "${local.gcp_endpoint}/sql/v1beta4/"
  big_query_custom_endpoint              = "${local.gcp_endpoint}/bigquery/v2/"
  pubsub_custom_endpoint                 = "${local.gcp_endpoint}/"
  cloud_run_v2_custom_endpoint           = "${local.gcp_endpoint}/"
  cloudfunctions2_custom_endpoint         = "${local.gcp_endpoint}/"
  cloud_scheduler_custom_endpoint        = "${local.gcp_endpoint}/"
  cloud_tasks_custom_endpoint            = "${local.gcp_endpoint}/"
  kms_custom_endpoint                    = "${local.gcp_endpoint}/"
  iam_custom_endpoint                    = "${local.gcp_endpoint}/"
  firestore_custom_endpoint              = "${local.gcp_endpoint}/"
  secret_manager_custom_endpoint         = "${local.gcp_endpoint}/"
  identity_platform_custom_endpoint      = "${local.gcp_endpoint}/"
  logging_custom_endpoint                 = "${local.gcp_endpoint}/"
  monitoring_custom_endpoint              = "${local.gcp_endpoint}/"
  cloud_resource_manager_custom_endpoint = "${local.gcp_endpoint}/"
  service_usage_custom_endpoint           = "${local.gcp_endpoint}/"
}

provider "google-beta" {
  access_token = "mock-access-token"
  project      = local.project_id
  region       = local.region

  compute_custom_endpoint               = "${local.gcp_endpoint}/compute/v1/"
  storage_custom_endpoint                = "${local.gcp_endpoint}/storage/v1/"
  sql_custom_endpoint                    = "${local.gcp_endpoint}/sql/v1beta4/"
  big_query_custom_endpoint              = "${local.gcp_endpoint}/bigquery/v2/"
  pubsub_custom_endpoint                 = "${local.gcp_endpoint}/"
  cloud_run_v2_custom_endpoint           = "${local.gcp_endpoint}/"
  cloudfunctions2_custom_endpoint        = "${local.gcp_endpoint}/"
  cloud_scheduler_custom_endpoint        = "${local.gcp_endpoint}/"
  cloud_tasks_custom_endpoint            = "${local.gcp_endpoint}/"
  kms_custom_endpoint                    = "${local.gcp_endpoint}/"
  iam_custom_endpoint                    = "${local.gcp_endpoint}/"
  firestore_custom_endpoint              = "${local.gcp_endpoint}/"
  secret_manager_custom_endpoint         = "${local.gcp_endpoint}/"
  identity_platform_custom_endpoint      = "${local.gcp_endpoint}/"
  logging_custom_endpoint                 = "${local.gcp_endpoint}/"
  monitoring_custom_endpoint              = "${local.gcp_endpoint}/"
  cloud_resource_manager_custom_endpoint = "${local.gcp_endpoint}/"
  service_usage_custom_endpoint          = "${local.gcp_endpoint}/"
}
