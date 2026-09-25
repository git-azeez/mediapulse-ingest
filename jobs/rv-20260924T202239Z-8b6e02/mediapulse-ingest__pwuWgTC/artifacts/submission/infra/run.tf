resource "google_cloud_run_v2_service" "api" {
  name     = local.run_service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.api.email

    scaling {
      min_instance_count = 2
      max_instance_count = 10
    }

    labels = local.common_labels

    containers {
      image = var.api_image
      ports {
        container_port = 8080
      }
      resources {
        limits = {
          cpu    = "1000m"
          memory = "512Mi"
        }
      }
      env {
        name  = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.db_url.secret_id
            version = "1"
          }
        }
      }
      env {
        name  = "DATASTORE_NAMESPACE"
        value = local.datastore_namespace
      }
      env {
        name  = "FIREBASE_AUTH_JWKS_URL"
        value = "${var.gcp_endpoint_url}/robot/v1/metadata/jwk/securetoken@system.gserviceaccount.com"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
    }
  }

  depends_on = [
    google_sql_database_instance.main,
    google_secret_manager_secret_version.db_url,
  ]
}
