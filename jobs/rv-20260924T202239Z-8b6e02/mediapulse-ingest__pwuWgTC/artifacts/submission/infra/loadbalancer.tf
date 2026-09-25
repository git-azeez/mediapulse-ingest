# Global External Application Load Balancer fronting the Cloud Run API via Serverless NEG

resource "google_compute_global_address" "lb" {
  name       = local.lb_ip_name
  ip_version = "IPV4"
}

resource "google_compute_region_network_endpoint_group" "serverless" {
  name                  = local.neg_name
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.api.name
  }

}

resource "google_compute_backend_service" "api" {
  name                  = local.backend_name
  protocol              = "HTTP"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  port_name             = "http"
  enable_cdn            = false

  backend {
    group = google_compute_region_network_endpoint_group.serverless.id
  }

  log_config {
    enable = true
  }
}

resource "google_compute_url_map" "api" {
  name            = local.urlmap_name
  default_service = google_compute_backend_service.api.id
}

resource "google_compute_target_http_proxy" "api" {
  name    = local.proxy_name
  url_map = google_compute_url_map.api.id
}

resource "google_compute_global_forwarding_rule" "api" {
  name       = local.fr_name
  target     = google_compute_target_http_proxy.api.id
  port_range = "80"
  ip_address = google_compute_global_address.lb.id
}
