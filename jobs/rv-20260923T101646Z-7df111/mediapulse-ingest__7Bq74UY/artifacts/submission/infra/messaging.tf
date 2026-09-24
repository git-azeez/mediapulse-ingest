resource "google_pubsub_topic" "dead_letter" {
  name         = "${var.prefix}-events-dlq"
  kms_key_name = google_kms_crypto_key.crypto_key.id
}

resource "google_pubsub_topic" "events" {
  name         = "${var.prefix}-events"
  kms_key_name = google_kms_crypto_key.crypto_key.id
}

resource "google_pubsub_subscription" "processor" {
  name  = "${var.prefix}-processor-sub"
  topic = google_pubsub_topic.events.name

  ack_deadline_seconds = 20

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter.id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
}
