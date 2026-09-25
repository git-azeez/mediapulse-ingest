variable "resource_prefix" {
  type        = string
  description = "Prefix assigned to this deployment, used in every managed resource name/label."
}

variable "project_id" {
  type        = string
  description = "GCP project id (gcp_project_id from config.json)."
}

variable "region" {
  type        = string
  description = "GCP region."
}

variable "zone" {
  type        = string
  description = "GCP zone derived from region."
  default     = "us-west1-a"
}

variable "gcp_endpoint_url" {
  type        = string
  description = "Floci-GCP control plane endpoint URL."
}

variable "api_image" {
  type    = string
  default = ""
}

variable "processor_image" {
  type    = string
  default = ""
}

variable "relay_image" {
  type    = string
  default = ""
}

variable "archiver_image" {
  type    = string
  default = ""
}

variable "db_name" {
  type    = string
  default = ""
}

variable "db_username" {
  type    = string
  default = ""
}

variable "db_password" {
  type      = string
  sensitive = true
  default   = ""
}
