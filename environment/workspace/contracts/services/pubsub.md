# Cloud Pub/Sub & Cloud Tasks Contract

- Main Topic (`messaging.topic_id`, `messaging.topic_name`): `google_pubsub_topic` encrypted with `kms.messaging_key_id`.
- Push Subscription (`messaging.subscription_id`): `google_pubsub_subscription` pushing to the `processor` Cloud Function (`workers.processor_id`) with a `dead_letter_policy` targeting `messaging.dlq_topic_id` and `max_delivery_attempts = 5`.
- Dead Letter Topic & Subscription (`messaging.dlq_topic_id`, `messaging.dlq_subscription_id`): `google_pubsub_topic` and pull `google_pubsub_subscription` for dead-letter inspection.
- Rebuild Queue (`messaging.rebuild_tasks_queue`): `google_cloud_tasks_queue` for rate-limited projection rebuild tasks.
