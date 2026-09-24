resource "google_cloud_scheduler_job" "relay" {
  name        = "${var.prefix}-relay-job"
  description = "Trigger outbox relay every minute"
  schedule    = "*/1 * * * *"
  time_zone   = "UTC"

  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions2_function.relay.service_config[0].uri

    oidc_token {
      service_account_email = google_service_account.scheduler.email
    }
  }
}

resource "google_cloud_scheduler_job" "archiver" {
  name        = "${var.prefix}-archiver-job"
  description = "Trigger audit archiver every 5 minutes"
  schedule    = "*/5 * * * *"
  time_zone   = "UTC"

  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions2_function.archiver.service_config[0].uri

    oidc_token {
      service_account_email = google_service_account.scheduler.email
    }
  }
}
