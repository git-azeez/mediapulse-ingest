# Cloud Pub/Sub Contract

- Main Topic: `media-events`.
- Subscription: Push subscription triggering `processor` Cloud Function.
- Dead Letter Policy: Dead Letter Topic configured with `max_delivery_attempts = 3`.
- Encryption: CMEK key via Cloud KMS.
