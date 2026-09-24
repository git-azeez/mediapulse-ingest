resource "google_compute_firewall" "allow_lb_to_api" {
  name      = "${var.prefix}-allow-lb-to-api"
  network   = google_compute_network.ingest.name
  direction = "INGRESS"
  priority  = 1000

  source_ranges = ["35.191.0.0/16", "130.211.0.0/22", local.ingress_subnet_cidr]
  target_tags   = ["${var.prefix}-api"]

  allow {
    protocol = "tcp"
    ports    = ["8080"]
  }
}

resource "google_compute_firewall" "allow_workloads_to_postgres" {
  name      = "${var.prefix}-allow-workloads-pg"
  network   = google_compute_network.ingest.name
  direction = "INGRESS"
  priority  = 1010

  source_ranges = [local.private_subnet_cidr]
  target_tags   = ["${var.prefix}-database"]

  allow {
    protocol = "tcp"
    ports    = ["5432"]
  }
}

resource "google_compute_firewall" "deny_external_ingress" {
  name      = "${var.prefix}-deny-external-ingress"
  network   = google_compute_network.ingest.name
  direction = "INGRESS"
  priority  = 65500

  source_ranges = ["0.0.0.0/0"]

  deny {
    protocol = "all"
  }
}
