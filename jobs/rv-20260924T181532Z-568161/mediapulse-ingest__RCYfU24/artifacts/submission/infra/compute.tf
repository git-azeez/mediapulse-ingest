resource "google_cloud_run_v2_service" "api" {
  name                = "${var.prefix}-api"
  location            = var.gcp_region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account = google_service_account.api.email

    scaling {
      min_instance_count = local.api_min_instances
      max_instance_count = local.api_max_instances
    }

    containers {
      name  = "api"
      image = var.api_image

      ports {
        name           = "http1"
        container_port = 8080
      }

      env {
        name  = "BIND_ADDR"
        value = "0.0.0.0:8080"
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.gcp_project_id
      }
      env {
        name  = "GCP_REGION"
        value = var.gcp_region
      }
      env {
        name  = "GCP_ENDPOINT_URL"
        value = var.gcp_endpoint_url
      }
      env {
        name  = "PUBSUB_EMULATOR_HOST"
        value = local.pubsub_emulator_host
      }
      env {
        name  = "FIRESTORE_EMULATOR_HOST"
        value = local.firestore_emulator_host
      }
      env {
        name  = "DATASTORE_EMULATOR_HOST"
        value = local.datastore_emulator_host
      }
      env {
        name  = "STORAGE_EMULATOR_HOST"
        value = local.storage_emulator_host
      }
      env {
        name  = "DATABASE_URL"
        value = local.database_url
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
        value = local.auth_issuer
      }
      env {
        name  = "AUTH_AUDIENCES"
        value = local.auth_audiences
      }
      env {
        name  = "AUTH_JWKS_URL"
        value = local.auth_jwks_url
      }
      env {
        name  = "RUST_LOG"
        value = "info"
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

resource "google_compute_region_network_endpoint_group" "api_serverless_neg" {
  name                  = "${var.prefix}-api-neg"
  network_endpoint_type = "SERVERLESS"
  region                = var.gcp_region

  cloud_run {
    service = google_cloud_run_v2_service.api.name
  }
}

resource "google_compute_backend_service" "api" {
  name                  = "${var.prefix}-api-backend"
  protocol              = "HTTP"
  port_name             = "http"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  timeout_sec           = 30

  backend {
    group = google_compute_region_network_endpoint_group.api_serverless_neg.id
  }
}

resource "google_compute_url_map" "api" {
  name            = "${var.prefix}-api-urlmap"
  default_service = google_compute_backend_service.api.id
}

resource "google_compute_target_http_proxy" "api" {
  name    = "${var.prefix}-api-http-proxy"
  url_map = google_compute_url_map.api.id
}

resource "google_compute_global_forwarding_rule" "http" {
  name                  = "${var.prefix}-api-http-fwd"
  ip_protocol           = "TCP"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  port_range            = "80"
  target                = google_compute_target_http_proxy.api.id
  ip_address            = google_compute_global_address.api_ip.id
}
