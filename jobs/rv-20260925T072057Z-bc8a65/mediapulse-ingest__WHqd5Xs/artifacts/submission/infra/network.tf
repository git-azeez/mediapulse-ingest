# VPC, subnets, firewall, and Global External Load Balancer

resource "google_compute_network" "vpc" {
  name                    = "${local.prefix}-vpc"
  project                 = local.project_id
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
}

resource "google_compute_subnetwork" "ingress" {
  name                     = "${local.prefix}-ingress-subnet"
  project                  = local.project_id
  region                   = local.region
  network                  = google_compute_network.vpc.id
  ip_cidr_range            = "10.10.0.0/20"
  private_ip_google_access = true
}

resource "google_compute_subnetwork" "private" {
  name                     = "${local.prefix}-private-subnet"
  project                  = local.project_id
  region                   = local.region
  network                  = google_compute_network.vpc.id
  ip_cidr_range            = "10.10.16.0/20"
  private_ip_google_access = true
}

resource "google_compute_firewall" "ingress_http" {
  name    = "${local.prefix}-fw-ingress-http"
  project = local.project_id
  network = google_compute_network.vpc.id
  direction = "INGRESS"
  priority  = 1000

  allow {
    protocol = "tcp"
    ports    = ["80", "8080"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["mediapulse-ingress", "mediapulse-api"]
}

resource "google_compute_firewall" "db_internal" {
  name    = "${local.prefix}-fw-db-internal"
  project = local.project_id
  network = google_compute_network.vpc.id
  direction = "INGRESS"
  priority  = 1000

  allow {
    protocol = "tcp"
    ports    = ["5432"]
  }

  source_ranges = [
    google_compute_subnetwork.ingress.ip_cidr_range,
    google_compute_subnetwork.private.ip_cidr_range,
  ]
  target_tags = ["mediapulse-db"]
}

# Global external load balancer fronting the Cloud Run API via a Serverless NEG

resource "google_compute_global_address" "lb_ip" {
  name    = "${local.prefix}-lb-ip"
  project = local.project_id
}

resource "google_compute_region_network_endpoint_group" "api_neg" {
  name                  = "${local.prefix}-api-neg"
  project               = local.project_id
  region                = local.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.api.name
  }
}

resource "google_compute_backend_service" "api_backend" {
  name                  = "${local.prefix}-api-backend"
  project               = local.project_id
  protocol              = "HTTPS"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  session_affinity      = "NONE"
  timeout_sec           = 60

  backend {
    group           = google_compute_region_network_endpoint_group.api_neg.id
    capacity_scaler = 1.0
  }
}

resource "google_compute_url_map" "api_url_map" {
  name            = "${local.prefix}-api-url-map"
  project         = local.project_id
  default_service = google_compute_backend_service.api_backend.id
}

resource "google_compute_target_http_proxy" "api_proxy" {
  name    = "${local.prefix}-api-http-proxy"
  project = local.project_id
  url_map = google_compute_url_map.api_url_map.id
}

resource "google_compute_global_forwarding_rule" "api_fr" {
  name       = "${local.prefix}-api-fr"
  project    = local.project_id
  target     = google_compute_target_http_proxy.api_proxy.id
  ip_address = google_compute_global_address.lb_ip.address
  port_range = "80"
}
