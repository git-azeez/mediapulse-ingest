# Global External Application Load Balancer -> Serverless NEG -> Cloud Run API

resource "google_compute_global_address" "lb" {
  name    = "${local.prefix}-lb-ip"
  project = local.project
  labels  = local.labels
}

resource "google_compute_region_network_endpoint_group" "serverless_neg" {
  name                  = "${local.prefix}-api-neg"
  project               = local.project
  region                = local.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.api.name
  }
}

resource "google_compute_backend_service" "api" {
  name    = "${local.prefix}-api-backend"
  project = local.project

  backend {
    group = google_compute_region_network_endpoint_group.serverless_neg.id
  }

  enable_cdn = false
}

resource "google_compute_url_map" "api" {
  name            = "${local.prefix}-api-urlmap"
  project         = local.project
  default_service = google_compute_backend_service.api.id
}

resource "google_compute_target_http_proxy" "api" {
  name    = "${local.prefix}-api-proxy"
  project = local.project
  url_map = google_compute_url_map.api.id
}

resource "google_compute_global_forwarding_rule" "api" {
  name       = "${local.prefix}-api-fr"
  project    = local.project
  target     = google_compute_target_http_proxy.api.self_link
  port_range = "80"
  ip_address = google_compute_global_address.lb.address
  labels     = local.labels
}

locals {
  lb_ip  = google_compute_global_address.lb.address
  lb_url = "http://${local.lb_ip}"
}
