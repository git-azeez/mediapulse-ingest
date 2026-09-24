locals {
  project = "mediapulse-ingest"

  common_labels = {
    project    = local.project
    deployment = var.prefix
    managed_by = "terraform"
  }

  vpc_name = "${var.prefix}-vpc"
  subnet_cidr = "10.100.0.0/20"
  connector_cidr = "10.100.16.0/28"
}
