resource "google_compute_network" "vpc" {
  name                    = local.vpc_name
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "ingress" {
  name                     = local.ingress_subnet_name
  region                   = var.region
  network                  = google_compute_network.vpc.id
  ip_cidr_range            = local.ingress_subnet_cidr
  private_ip_google_access = true
}

resource "google_compute_subnetwork" "private" {
  name                     = local.private_subnet_name
  region                   = var.region
  network                  = google_compute_network.vpc.id
  ip_cidr_range            = local.private_subnet_cidr
  private_ip_google_access = true
}

resource "google_compute_firewall" "allow_http" {
  name        = "${var.resource_prefix}-allow-http"
  network      = google_compute_network.vpc.id
  description  = "Allow HTTP/8080 ingress to mediapulse ingress and api targets"
  target_tags  = ["mediapulse-ingress", "mediapulse-api"]
  source_tags  = ["mediapulse-ingress"]
  allow {
    protocol = "tcp"
    ports    = ["80", "8080"]
  }
}

resource "google_compute_firewall" "allow_db" {
  name        = "${var.resource_prefix}-allow-db"
  network      = google_compute_network.vpc.id
  description  = "Allow TCP 5432 from ingress and private subnets to db targets"
  target_tags  = ["mediapulse-db"]
  source_ranges = [local.ingress_subnet_cidr, local.private_subnet_cidr]
  allow {
    protocol = "tcp"
    ports    = ["5432"]
  }
}

# Cloud SQL private IP is configured directly on the instance via private_network.
# The Floci-GCP control plane allocates a private IP without a separate peering connection.
