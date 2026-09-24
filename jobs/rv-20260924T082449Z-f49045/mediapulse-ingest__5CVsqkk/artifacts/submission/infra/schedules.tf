resource "google_cloud_scheduler_job" "relay" {
  name             = "${var.prefix}-relay-schedule"
  region           = var.gcp_region
  description      = "Triggers Outbox Relay function every minute to flush unpublished PostgreSQL outbox events"
  schedule         = "* * * * *"
  time_zone        = "Etc/UTC"
  attempt_deadline = "30s"

  retry_config {
    retry_count          = 2
    min_backoff_duration = "2s"
    max_backoff_duration = "15s"
  }

  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions2_function.relay.url
    body        = base64encode(jsonencode({ source = "cloud.scheduler", action = "flush_outbox" }))

    headers = {
      "Content-Type" = "application/json"
    }

    oidc_token {
      service_account_email = google_service_account.scheduler.email
      audience              = google_cloudfunctions2_function.relay.url
    }
  }
}

resource "google_cloud_scheduler_job" "archiver" {
  name             = "${var.prefix}-archiver-schedule"
  region           = var.gcp_region
  description      = "Triggers Audit Archiver function every 5 minutes to export published events to GCS"
  schedule         = "*/5 * * * *"
  time_zone        = "Etc/UTC"
  attempt_deadline = "60s"

  retry_config {
    retry_count          = 2
    min_backoff_duration = "5s"
    max_backoff_duration = "30s"
  }

  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions2_function.archiver.url
    body        = base64encode(jsonencode({ source = "cloud.scheduler", action = "archive_events" }))

    headers = {
      "Content-Type" = "application/json"
    }

    oidc_token {
      service_account_email = google_service_account.scheduler.email
      audience              = google_cloudfunctions2_function.archiver.url
    }
  }
}
