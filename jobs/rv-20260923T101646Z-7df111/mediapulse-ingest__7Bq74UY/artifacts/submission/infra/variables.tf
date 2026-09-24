variable "prefix" {
  type        = string
  description = "Unique resource prefix for all GCP resources."
}

variable "gcp_project_id" {
  type        = string
  description = "GCP Project ID."
}

variable "gcp_region" {
  type        = string
  description = "GCP Region for regional resources."
  default     = "us-central1"
}

variable "api_image" {
  type        = string
  description = "Docker image reference for API service."
}

variable "processor_image" {
  type        = string
  description = "Image reference for processor Cloud Function."
}

variable "relay_image" {
  type        = string
  description = "Image reference for relay Cloud Function."
}

variable "archiver_image" {
  type        = string
  description = "Image reference for archiver Cloud Function."
}

variable "db_name" {
  type        = string
  description = "PostgreSQL Database name."
  default     = "mediapulse"
}

variable "db_username" {
  type        = string
  description = "PostgreSQL User name."
  default     = "mediapulse_user"
}

variable "db_password" {
  type        = string
  sensitive   = true
  description = "PostgreSQL Password."
}
