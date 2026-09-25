# Cloud Run (v2) API service

resource "google_cloud_run_v2_service" "api" {
  name     = "${local.prefix}-api"
  project  = local.project_id
  location = local.region

  ingress = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.api.email
    max_instance_request_concurrency = 100

    scaling {
      min_instance_count = 2
      max_instance_count = 10
    }

    containers {
      image = local.cfg.api_image
      name  = "api"
      ports {
        container_port = 8080
      }

      env {
        name  = "DATABASE_URL"
        value = local.database_url
      }
      env {
        name  = "DATASTORE_NAMESPACE"
        value = local.datastore_namespace
      }
      env {
        name  = "FIREBASE_AUTH_JWKS_URL"
        value = "${local.gcp_endpoint}/robot/v1/metadata/jwk/securetoken@system.gserviceaccount.com"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = local.project_id
      }
      env {
        name  = "PUBSUB_TOPIC"
        value = google_pubsub_topic.main.name
      }
      env {
        name  = "FIRESTORE_DATABASE"
        value = google_firestore_database.main.name
      }
    }
  }
}
