resource "google_pubsub_topic" "events" {
  name = "${var.prefix}-events"

  labels = local.common_labels
}

resource "google_pubsub_topic" "dead_letters" {
  name = "${var.prefix}-events-dlq"

  labels = local.common_labels
}

resource "google_pubsub_subscription" "processor" {
  name                 = "${var.prefix}-events-processor-sub"
  topic                = google_pubsub_topic.events.name
  ack_deadline_seconds = 20

  push_config {
    push_endpoint = google_cloudfunctions2_function.processor.url

    oidc_token {
      service_account_email = google_service_account.processor.email
    }
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letters.id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "2s"
    maximum_backoff = "30s"
  }

  labels = local.common_labels
}

resource "google_pubsub_subscription" "dead_letters" {
  name                 = "${var.prefix}-events-dlq-sub"
  topic                = google_pubsub_topic.dead_letters.name
  ack_deadline_seconds = 60

  labels = local.common_labels
}

resource "google_cloud_tasks_queue" "rebuild" {
  name     = "${var.prefix}-projection-rebuild-q"
  location = var.gcp_region

  rate_limits {
    max_concurrent_dispatches = 10
    max_dispatches_per_second  = 25
  }

  retry_config {
    max_attempts = 5
    min_backoff  = "1s"
    max_backoff  = "15s"
  }
}
