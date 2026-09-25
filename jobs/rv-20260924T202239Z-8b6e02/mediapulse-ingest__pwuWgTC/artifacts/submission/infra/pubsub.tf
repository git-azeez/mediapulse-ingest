resource "google_pubsub_topic" "main" {
  name   = local.topic_name
  labels = local.common_labels

  kms_key_name = google_kms_crypto_key.messaging.id
}

resource "google_pubsub_topic" "dlq" {
  name   = local.dlq_topic_name
  labels = local.common_labels
}

resource "google_pubsub_subscription" "processor" {
  name   = local.subscription_name
  topic  = google_pubsub_topic.main.name
  labels = local.common_labels

  push_config {
    push_endpoint = google_cloudfunctions2_function.processor.service_config[0].uri
    oidc_token {
      service_account_email = google_service_account.processor.email
      audience              = google_cloudfunctions2_function.processor.service_config[0].uri
    }
    attributes = {
      x-goog-push-format = "json"
    }
  }

  ack_deadline_seconds = 60

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq.id
    max_delivery_attempts = 5
  }

  expiration_policy {
    ttl = ""
  }
}

resource "google_pubsub_subscription" "dlq" {
  name   = local.dlq_sub_name
  topic  = google_pubsub_topic.dlq.name
  labels = local.common_labels

  ack_deadline_seconds = 60

  expiration_policy {
    ttl = ""
  }
}

# Allow the processor SA to acknowledge dead-lettered messages on the DLQ subscription
resource "google_pubsub_subscription_iam_member" "dlq_sub_processor" {
  project      = var.project_id
  subscription = google_pubsub_subscription.dlq.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.processor.email}"
}
