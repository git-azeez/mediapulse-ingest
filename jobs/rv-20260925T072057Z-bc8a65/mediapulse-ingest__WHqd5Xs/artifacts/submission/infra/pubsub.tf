# Cloud Pub/Sub - main topic, push subscription, dead-letter

resource "google_pubsub_topic" "main" {
  name    = "${local.prefix}-events"
  project = local.project_id
  labels  = local.common_labels

  kms_key_name = google_kms_crypto_key.messaging.id
}

resource "google_pubsub_topic" "dlq" {
  name    = "${local.prefix}-events-dlq"
  project = local.project_id
  labels  = local.common_labels
}

resource "google_pubsub_subscription" "processor_push" {
  name    = "${local.prefix}-processor-push"
  project = local.project_id
  topic   = google_pubsub_topic.main.id
  labels  = local.common_labels

  ack_deadline_seconds = 60

  push_config {
    push_endpoint = google_cloudfunctions2_function.processor.service_config[0].uri

    oidc_token {
      service_account_email = google_service_account.processor.email
    }
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq.id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
}

resource "google_pubsub_subscription" "dlq" {
  name    = "${local.prefix}-events-dlq-sub"
  project = local.project_id
  topic   = google_pubsub_topic.dlq.id
  labels  = local.common_labels

  ack_deadline_seconds = 600
}

# Cloud Tasks queue for projection rebuilds

resource "google_cloud_tasks_queue" "rebuild" {
  name    = "${local.prefix}-rebuild-queue"
  project = local.project_id
  location = local.region

  rate_limits {
    max_concurrent_dispatches = 20
    max_dispatches_per_second  = 50
  }
}
