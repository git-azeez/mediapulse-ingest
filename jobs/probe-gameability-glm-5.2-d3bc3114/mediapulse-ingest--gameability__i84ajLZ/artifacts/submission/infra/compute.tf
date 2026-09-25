resource "google_cloud_run_v2_service" "api" {
  name                = "${var.prefix}-api"
  location            = var.gcp_region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account = google_service_account.api.email

    scaling {
      min_instance_count = 2
      max_instance_count = 6
    }

    containers {
      name  = "api"
      image = var.api_image
      ports {
        name           = "http1"
        container_port = 8080
      }
      env {
        name  = "GCP_ENDPOINT_URL"
        value = var.gcp_endpoint_url
      }
      env {
        name  = "DATABASE_URL"
        value = "postgresql://${var.db_username}:${var.db_password}@${local.gcp_endpoint_host}:5432/${var.db_name}?sslmode=disable"
      }
      env {
        name  = "PUBSUB_TOPIC"
        value = google_pubsub_topic.events.name
      }
      env {
        name  = "FIRESTORE_DATABASE"
        value = google_firestore_database.projections.name
      }
      env {
        name  = "DATASTORE_NAMESPACE"
        value = "${var.prefix}-cache"
      }
      env {
        name  = "AUTH_ISSUER"
        value = "${var.gcp_endpoint_url}/identitytoolkit.googleapis.com/v1/projects/${var.gcp_project_id}"
      }
      env {
        name  = "AUTH_JWKS_URL"
        value = "${var.gcp_endpoint_url}/robot/v1/metadata/jwk/securetoken@system.gserviceaccount.com"
      }

      startup_probe {
        http_get {
          path = "/health/ready"
          port = 8080
        }
        initial_delay_seconds = 2
        period_seconds        = 5
        timeout_seconds       = 3
        failure_threshold     = 6
      }

      liveness_probe {
        http_get {
          path = "/health/ready"
          port = 8080
        }
        period_seconds    = 10
        timeout_seconds   = 3
        failure_threshold = 3
      }
    }
  }

  labels = merge(local.common_labels, {
    component = "api"
  })
}

resource "google_compute_region_network_endpoint_group" "neg" {
  name                  = "${var.prefix}-api-neg"
  network_endpoint_type = "SERVERLESS"
  region                = var.gcp_region

  cloud_run {
    service = google_cloud_run_v2_service.api.name
  }
}

resource "google_compute_backend_service" "backend" {
  name                  = "${var.prefix}-api-backend"
  protocol              = "HTTP"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  timeout_sec           = 30

  backend {
    group = google_compute_region_network_endpoint_group.neg.id
  }
}

resource "google_compute_url_map" "urlmap" {
  name            = "${var.prefix}-api-urlmap"
  default_service = google_compute_backend_service.backend.id
}

resource "google_compute_target_http_proxy" "proxy" {
  name    = "${var.prefix}-api-proxy"
  url_map = google_compute_url_map.urlmap.id
}

resource "google_compute_global_forwarding_rule" "fr" {
  name                  = "${var.prefix}-api-fr"
  ip_protocol           = "TCP"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  port_range            = "80"
  target                = google_compute_target_http_proxy.proxy.id
}
