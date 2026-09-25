resource "google_cloud_scheduler_job" "relay" {
  name     = "${local.prefix}-relay-job"
  project  = local.project
  region   = local.region

  schedule  = "* * * * *"
  time_zone = "UTC"

  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions2_function.relay.url

    oidc_token {
      service_account_email = google_service_account.scheduler.email
      audience              = google_cloudfunctions2_function.relay.url
    }
  }
}

resource "google_cloud_scheduler_job" "archiver" {
  name     = "${local.prefix}-archiver-job"
  project  = local.project
  region   = local.region

  schedule  = "*/5 * * * *"
  time_zone = "UTC"

  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions2_function.archiver.url

    oidc_token {
      service_account_email = google_service_account.scheduler.email
      audience              = google_cloudfunctions2_function.archiver.url
    }
  }
}
