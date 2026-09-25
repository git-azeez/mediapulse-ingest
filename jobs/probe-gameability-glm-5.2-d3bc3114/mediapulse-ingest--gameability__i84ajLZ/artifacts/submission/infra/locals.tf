locals {
  sa_prefix = substr(var.prefix, 0, 15)

  common_labels = {
    deployment     = var.prefix
    managed_by     = "terraform"
  }

  gcp_endpoint_host = split(":", split("//", var.gcp_endpoint_url)[1])[0]
}
