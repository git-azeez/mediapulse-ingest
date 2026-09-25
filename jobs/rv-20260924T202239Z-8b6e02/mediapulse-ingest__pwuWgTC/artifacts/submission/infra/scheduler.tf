resource "google_cloud_scheduler_job" "relay" {
  name     = local.relay_job_name
  region   = var.region
  schedule = "* * * * *"
  time_zone = "Etc/UTC"

  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions2_function.relay.service_config[0].uri

    oidc_token {
      service_account_email = google_service_account.scheduler.email
      audience              = google_cloudfunctions2_function.relay.service_config[0].uri
    }
  }

  attempt_deadline = "320s"
}

resource "google_cloud_scheduler_job" "archiver" {
  name     = local.archiver_job_name
  region   = var.region
  schedule = "*/5 * * * *"
  time_zone = "Etc/UTC"

  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions2_function.archiver.service_config[0].uri

    oidc_token {
      service_account_email = google_service_account.scheduler.email
      audience              = google_cloudfunctions2_function.archiver.service_config[0].uri
    }
  }

  attempt_deadline = "320s"
}
