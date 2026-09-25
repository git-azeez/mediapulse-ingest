locals {
  ingress_cidr = "10.10.0.0/20"
  private_cidr = "10.10.32.0/20"
  labels       = { "mediapulse_deployment" = local.prefix }
}

resource "google_compute_network" "vpc" {
  name                    = "${local.prefix}-vpc"
  auto_create_subnetworks = false
  project                 = local.project
}

resource "google_compute_subnetwork" "ingress" {
  name                     = "${local.prefix}-ingress-subnet"
  project                  = local.project
  region                   = local.region
  network                  = google_compute_network.vpc.id
  ip_cidr_range            = local.ingress_cidr
  private_ip_google_access = false
}

resource "google_compute_subnetwork" "private" {
  name                     = "${local.prefix}-private-subnet"
  project                  = local.project
  region                   = local.region
  network                  = google_compute_network.vpc.id
  ip_cidr_range            = local.private_cidr
  private_ip_google_access = true
}

resource "google_compute_firewall" "ingress_http" {
  name    = "${local.prefix}-allow-http"
  project = local.project
  network = google_compute_network.vpc.id

  allow {
    protocol = "tcp"
    ports    = ["80", "8080"]
  }
  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["mediapulse-ingress", "mediapulse-api"]
}

resource "google_compute_firewall" "db_internal" {
  name    = "${local.prefix}-allow-db-internal"
  project = local.project
  network = google_compute_network.vpc.id

  allow {
    protocol = "tcp"
    ports    = ["5432"]
  }
  source_ranges = [local.ingress_cidr, local.private_cidr]
  target_tags   = ["mediapulse-db"]
}
