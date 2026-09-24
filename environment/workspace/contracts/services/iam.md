# Cloud IAM & OAuth2 Client Credentials

## Service Accounts

Create distinct GCP Service Accounts (`google_service_account`) for each runtime component and record their emails in `manifest.iam`:

| Component | Manifest field | Required IAM Roles |
|---|---|---|
| Cloud Run API | `iam.api_service_account` | `roles/cloudsql.client`, `roles/datastore.viewer`, `roles/secretmanager.secretAccessor` (on the DB secret), `roles/pubsub.publisher` (on the main topic) |
| Event Processor Function | `iam.processor_service_account` | `roles/pubsub.subscriber` (on the push subscription), `roles/datastore.user` |
| Outbox Relay Function | `iam.relay_service_account` | `roles/cloudsql.client`, `roles/pubsub.publisher` (on the main topic) |
| Audit Archiver Function | `iam.archiver_service_account` | `roles/cloudsql.client`, `roles/storage.objectAdmin` (on the audit GCS bucket) |
| Cloud Scheduler Invoker | `iam.scheduler_service_account` | OIDC invoker service account used by Cloud Scheduler jobs targeting the relay and archiver functions |

Do not grant primitive roles (`roles/owner`, `roles/editor`) or wildcard permissions.

## OAuth2 Client Credentials (`manifest.auth`)

Create an Identity Platform tenant (`google_identity_platform_tenant`) and three client Service Accounts (`google_service_account`) with corresponding user-managed keys (`google_service_account_key`) representing the `mediapulse/read`, `mediapulse/write`, and `mediapulse/admin` scopes:

- `auth.read_client_email` and `auth.read_client_id`: Set to `google_service_account.client_read.email`.
- `auth.write_client_email` and `auth.write_client_id`: Set to `google_service_account.client_write.email`.
- `auth.admin_client_email` and `auth.admin_client_id`: Set to `google_service_account.client_admin.email`.
- `auth.read_client_secret`: Set to `google_service_account_key.client_read.private_key`.
- `auth.write_client_secret`: Set to `google_service_account_key.client_write.private_key`.
- `auth.admin_client_secret`: Set to `google_service_account_key.client_admin.private_key`.
- `auth.token_endpoint`: Set to `<gcp_endpoint_url>/oauth2/v4/token` (where `client_id`, `client_secret`, and `scope` are exchanged via `grant_type=client_credentials` for a signed RS256 JWT).
- `auth.jwks_url`: Set to `<gcp_endpoint_url>/robot/v1/metadata/jwk/securetoken@system.gserviceaccount.com`.
