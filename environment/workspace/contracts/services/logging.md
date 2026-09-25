# Cloud Logging Contract

- Structured JSON log formatting for all microservices (`api`, `processor`, `relay`, `archiver`).
- Provision either 4 dedicated `google_logging_project_bucket_config` resources (one per microservice) or a centralized `google_logging_project_bucket_config` accompanied by `google_logging_project_sink` resources covering the 4 microservices.
- Retention: Configure `retention_days >= 14` (e.g. `30` days) on every `google_logging_project_bucket_config`.
