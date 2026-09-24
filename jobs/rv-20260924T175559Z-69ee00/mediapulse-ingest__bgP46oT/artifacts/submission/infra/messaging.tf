resource "google_pubsub_topic" "dead_letters" {
  name                       = "${var.prefix}-events-dlq"
  kms_key_name               = google_kms_crypto_key.messaging.id
  message_retention_duration = "1209600s"

  labels = merge(local.common_labels, {
    role = "dead-letter"
  })
}

resource "google_pubsub_subscription" "dead_letters" {
  name                       = "${var.prefix}-events-dlq-sub"
  topic                      = google_pubsub_topic.dead_letters.name
  message_retention_duration = "1209600s"
  retain_acked_messages      = false
  ack_deadline_seconds       = 60

  labels = merge(local.common_labels, {
    role = "dead-letter-archive"
  })
}

resource "google_pubsub_topic" "events" {
  name                       = "${var.prefix}-events"
  kms_key_name               = google_kms_crypto_key.messaging.id
  message_retention_duration = "345600s"

  labels = merge(local.common_labels, {
    role = "domain-events"
  })
}

resource "google_pubsub_subscription" "processor_push" {
  name                       = "${var.prefix}-events-processor-sub"
  topic                      = google_pubsub_topic.events.name
  ack_deadline_seconds       = 20
  message_retention_duration = "345600s"
  enable_message_ordering    = true

  push_config {
    push_endpoint = google_cloudfunctions2_function.processor.url

    oidc_token {
      service_account_email = google_service_account.pubsub_invoker.email
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

  labels = merge(local.common_labels, {
    role = "processor-consumer"
  })
}

resource "google_cloud_tasks_queue" "projection_rebuild" {
  name     = "${var.prefix}-projection-rebuild-q"
  location = var.gcp_region

  rate_limits {
    max_concurrent_dispatches = 10
    max_dispatches_per_second = 25
  }

  retry_config {
    max_attempts = 5
    min_backoff  = "1s"
    max_backoff  = "15s"
  }
}
