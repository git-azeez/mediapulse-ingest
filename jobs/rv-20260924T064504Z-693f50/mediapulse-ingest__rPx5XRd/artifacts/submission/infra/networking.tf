resource "google_compute_network" "ingest" {
  name                    = "${var.prefix}-vpc"
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
}

resource "google_compute_subnetwork" "ingress" {
  name          = "${var.prefix}-subnet-ingress"
  ip_cidr_range = local.ingress_subnet_cidr
  region        = var.gcp_region
  network       = google_compute_network.ingest.id
}

resource "google_compute_subnetwork" "private" {
  name                     = "${var.prefix}-subnet-private"
  ip_cidr_range            = local.private_subnet_cidr
  region                   = var.gcp_region
  network                  = google_compute_network.ingest.id
  private_ip_google_access = true
}

resource "google_compute_global_address" "api_ip" {
  name         = "${var.prefix}-api-lb-ip"
  address_type = "EXTERNAL"
}
