locals {
  topic_name    = "${local.prefix}-events"
  dlq_topic     = "${local.prefix}-events-dlq"
  subscription  = "${local.prefix}-events-push"
  dlq_sub       = "${local.prefix}-events-dlq-pull"
}

resource "google_pubsub_topic" "main" {
  name    = local.topic_name
  project = local.project
  labels  = local.labels

  kms_key_name = google_kms_crypto_key.messaging.id
}

resource "google_pubsub_topic" "dlq" {
  name    = local.dlq_topic
  project = local.project
  labels  = local.labels
}

resource "google_pubsub_subscription" "push" {
  name    = local.subscription
  project = local.project
  topic   = google_pubsub_topic.main.name
  labels  = local.labels

  push_config {
    push_endpoint = google_cloudfunctions2_function.processor.url

    oidc_token {
      service_account_email = google_service_account.processor.email
    }
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq.id
    max_delivery_attempts = 5
  }

  ack_deadline_seconds       = 30
  message_retention_duration = "600s"
  expiration_policy {
    ttl = ""
  }
}

resource "google_pubsub_subscription" "dlq_pull" {
  name    = local.dlq_sub
  project = local.project
  topic   = google_pubsub_topic.dlq.name
  labels  = local.labels

  ack_deadline_seconds = 30
  expiration_policy {
    ttl = ""
  }
}

# IAM bindings
resource "google_pubsub_topic_iam_member" "api_publisher" {
  project = local.project
  topic   = google_pubsub_topic.main.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_pubsub_topic_iam_member" "relay_publisher" {
  project = local.project
  topic   = google_pubsub_topic.main.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.relay.email}"
}

resource "google_pubsub_subscription_iam_member" "processor_subscriber" {
  project      = local.project
  subscription = google_pubsub_subscription.push.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.processor.email}"
}

resource "google_pubsub_subscription_iam_member" "dlq_subscriber" {
  project      = local.project
  subscription = google_pubsub_subscription.dlq_pull.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.processor.email}"
}
