# Cloud Scheduler

Create two `google_cloud_scheduler_job` resources in the deployment region:

- `schedules.relay_job_name`: Recurring schedule (`* * * * *`) triggering the Outbox Relay Cloud Function (`workers.relay_id`) via HTTP POST with OIDC token (`iam.scheduler_service_account`).
- `schedules.archiver_job_name`: Recurring schedule (`*/5 * * * *`) triggering the Audit Archiver Cloud Function (`workers.archiver_id`) via HTTP POST with OIDC token (`iam.scheduler_service_account`).
