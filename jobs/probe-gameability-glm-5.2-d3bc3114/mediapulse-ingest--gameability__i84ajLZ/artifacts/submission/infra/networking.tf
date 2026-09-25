resource "google_compute_network" "vpc" {
  name                    = "${var.prefix}-vpc"
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
}

resource "google_compute_subnetwork" "ingress" {
  name          = "${var.prefix}-subnet-ingress"
  ip_cidr_range = "10.84.0.0/24"
  region        = var.gcp_region
  network       = google_compute_network.vpc.id
}

resource "google_compute_subnetwork" "private" {
  name                     = "${var.prefix}-subnet-private"
  ip_cidr_range            = "10.84.10.0/24"
  region                   = var.gcp_region
  network                  = google_compute_network.vpc.id
  private_ip_google_access = true
}

resource "google_compute_global_address" "ip" {
  name         = "${var.prefix}-api-lb-ip"
  address_type = "EXTERNAL"
}
