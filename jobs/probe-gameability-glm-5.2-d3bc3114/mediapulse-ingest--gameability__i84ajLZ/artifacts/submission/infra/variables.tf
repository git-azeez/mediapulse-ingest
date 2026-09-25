variable "prefix" {
  type = string
}

variable "gcp_project_id" {
  type = string
}

variable "gcp_region" {
  type = string
}

variable "gcp_endpoint_url" {
  type = string
}

variable "api_image" {
  type = string
}

variable "processor_image" {
  type = string
}

variable "relay_image" {
  type = string
}

variable "archiver_image" {
  type = string
}

variable "api_image_id" {
  type    = string
  default = ""
}

variable "processor_image_id" {
  type    = string
  default = ""
}

variable "relay_image_id" {
  type    = string
  default = ""
}

variable "archiver_image_id" {
  type    = string
  default = ""
}

variable "db_name" {
  type = string
}

variable "db_username" {
  type = string
}

variable "db_password" {
  type      = string
  sensitive = true
}
