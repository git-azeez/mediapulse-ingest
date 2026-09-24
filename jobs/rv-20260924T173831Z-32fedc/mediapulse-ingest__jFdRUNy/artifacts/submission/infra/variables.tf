variable "prefix" {
  description = "Deployment prefix loaded from /workspace/config/config.json."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,22}$", var.prefix))
    error_message = "prefix must be 3 to 23 lowercase letters, digits, or hyphens and start with a letter."
  }
}

variable "gcp_project_id" {
  description = "Target Google Cloud project ID from config.json."
  type        = string
  default     = "example-gcp-project"
}

variable "gcp_region" {
  description = "Target Google Cloud region from config.json."
  type        = string
  default     = "us-central1"
}

variable "gcp_endpoint_url" {
  description = "Floci-GCP local emulator base URL (http://gcp:4588)."
  type        = string
  default     = "http://gcp:4588"
}

variable "db_username" {
  description = "Cloud SQL PostgreSQL username from config.json."
  type        = string
  default     = "mediapulse_user"
}

variable "db_password" {
  description = "Cloud SQL PostgreSQL password from config.json."
  type        = string
  default     = "example-pass"
  sensitive   = true
}

variable "db_name" {
  description = "Cloud SQL PostgreSQL database name from config.json."
  type        = string
  default     = "mediapulse"
}

variable "api_image" {
  description = "Supplied Cloud Run API container image reference."
  type        = string
  default     = "gcr.io/example/api:latest"
}

variable "processor_image" {
  description = "Supplied Cloud Functions event processor container image reference."
  type        = string
  default     = "gcr.io/example/processor:latest"
}

variable "relay_image" {
  description = "Supplied Cloud Functions outbox relay container image reference."
  type        = string
  default     = "gcr.io/example/relay:latest"
}

variable "archiver_image" {
  description = "Supplied Cloud Functions audit archiver container image reference."
  type        = string
  default     = "gcr.io/example/archiver:latest"
}

variable "api_image_id" {
  description = "Optional digest/ID for the API container image."
  type        = string
  default     = ""
}

variable "processor_image_id" {
  description = "Optional digest/ID for the processor container image."
  type        = string
  default     = ""
}

variable "relay_image_id" {
  description = "Optional digest/ID for the outbox relay container image."
  type        = string
  default     = ""
}

variable "archiver_image_id" {
  description = "Optional digest/ID for the audit archiver container image."
  type        = string
  default     = ""
}
