# Runtime

This file defines the required runtime behavior, service connections and
environment-specific GCP behavior for MediaPulse Ingest. Resource
topology, ports, network attachments, IAM and encryption are defined in
`infrastructure.md` and its files under `services/`.

## Supplied Images

| Component | Provided image tag | Runtime entrypoint |
|---|---|---|
| API | `mediapulse/api:1.0.0` | `/app/api` |
| Projector | `mediapulse/projector:1.0.0` | `/app/projector` |
| Outbox relay | `mediapulse/relay:1.0.0` | `/app/relay` |
| Audit archiver | `mediapulse/archiver:1.0.0` | `/app/archiver` |

The tags are provided local application images. Exact image URIs are provided as the flat `*_image` fields in `/workspace/config/config.json`.

## Configuration

Read the actual runtime values from `/workspace/config/config.json`. It is a
flat, snake_case JSON object.

| Field | Meaning and required use |
|---|---|
| `resource_prefix` | Prefix assigned to this deployment. Use this exact value in the name or tags of every managed resource. |
| `region` | GCP region. |
| `gcp_project_id` | GCP Project ID. |
| `gcp_endpoint_url` | GCP API endpoint. |
| `api_image` | Exact image reference for the Cloud Run API. |
| `projector_image` | Exact image reference for the projector Cloud Function. |
| `relay_image` | Exact image reference for the outbox relay Cloud Function. |
| `archiver_image` | Exact image reference for the audit archiver Cloud Function. |
| `db_name` | PostgreSQL database name used by the application. |
| `db_username` | PostgreSQL username used by the application. |
| `db_password` | PostgreSQL password used by the application. Treat it as a secret and never emit it in logs or `manifest.json`. |

## API

The API runs on Cloud Run (v2).

Required variables:
- `DATABASE_URL`: `postgresql://<user>:<password>@<host>:5432/<database>?sslmode=disable`
- `DATASTORE_NAMESPACE`: Cloud Datastore namespace for caching.
- `FIREBASE_AUTH_JWKS_URL`: URL to fetch Identity Platform JWKS.
- `GOOGLE_CLOUD_PROJECT`: Exact `gcp_project_id` value from `config.json`.

## Projector Worker

Triggered by Cloud Pub/Sub Push Subscription.

Required variables:
- `FIRESTORE_DATABASE`: Cloud Firestore database identifier.
- `DATASTORE_NAMESPACE`: Cloud Datastore namespace for caching.
- `GOOGLE_CLOUD_PROJECT`: Exact `gcp_project_id` value from `config.json`.

## Outbox Relay Worker

Triggered by Cloud Scheduler (1-minute).

Required variables:
- `DATABASE_URL`: PostgreSQL connection string.
- `PUBSUB_TOPIC`: Exact name of the main Pub/Sub topic.
- `GOOGLE_CLOUD_PROJECT`: Exact `gcp_project_id` value from `config.json`.

## Audit Archiver Worker

Triggered by Cloud Scheduler (5-minute).

Required variables:
- `DATABASE_URL`: PostgreSQL connection string.
- `GCS_BUCKET`: Exact name of the GCS audit bucket.
- `GOOGLE_CLOUD_PROJECT`: Exact `gcp_project_id` value from `config.json`.
