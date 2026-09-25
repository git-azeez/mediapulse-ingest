resource "google_cloud_scheduler_job" "relay" {
  name             = "${var.prefix}-relay-schedule"
  region           = var.gcp_region
  schedule         = "* * * * *"
  time_zone        = "Etc/UTC"
  attempt_deadline = "30s"

  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions2_function.relay.url
    body        = base64encode(jsonencode({ source = "cloud.scheduler", action = "flush_outbox" }))
    headers = {
      "Content-Type" = "application/json"
    }
    oidc_token {
      service_account_email = google_service_account.scheduler.email
    }
  }
}

resource "google_cloud_scheduler_job" "archiver" {
  name             = "${var.prefix}-archiver-schedule"
  region           = var.gcp_region
  schedule         = "*/5 * * * *"
  time_zone        = "Etc/UTC"
  attempt_deadline = "60s"

  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions2_function.archiver.url
    body        = base64encode(jsonencode({ source = "cloud.scheduler", action = "archive_events" }))
    headers = {
      "Content-Type" = "application/json"
    }
    oidc_token {
      service_account_email = google_service_account.scheduler.email
    }
  }
}
