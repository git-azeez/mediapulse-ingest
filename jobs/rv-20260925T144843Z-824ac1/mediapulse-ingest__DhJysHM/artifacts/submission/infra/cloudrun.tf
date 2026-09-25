locals {
  jwks_url = "${local.ep}/robot/v1/metadata/jwk/securetoken@system.gserviceaccount.com"
}

resource "google_cloud_run_v2_service" "api" {
  name     = "${local.prefix}-api"
  project  = local.project
  location = local.region
  ingress  = "INGRESS_TRAFFIC_ALL"
  labels   = local.labels

  deletion_protection = false

  template {
    service_account = google_service_account.api.email

    scaling {
      min_instance_count = 2
      max_instance_count = 10
    }

    containers {
      name  = "api"
      image = local.config.api_image

      ports {
        container_port = 8080
      }

      env {
        name  = "DATABASE_URL"
        value = local.db_url
      }
      env {
        name  = "DATASTORE_NAMESPACE"
        value = "${local.prefix}-cache"
      }
      env {
        name  = "FIREBASE_AUTH_JWKS_URL"
        value = local.jwks_url
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = local.project
      }
      env {
        name  = "PUBSUB_TOPIC"
        value = google_pubsub_topic.main.name
      }
      env {
        name  = "GCS_BUCKET"
        value = google_storage_bucket.audit.name
      }
      env {
        name  = "FIRESTORE_DATABASE"
        value = google_firestore_database.main.name
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
}
