# Cloud SQL PostgreSQL Contract

- Engine: PostgreSQL 15+ (`POSTGRES_15`).
- Connectivity: Private IP via VPC Private Service Access.
- Encryption: Must use Customer-Managed Encryption Key (CMEK) via Cloud KMS (`encryption_key_name`).
- Tables required: `media`, `events`, `outbox`.
- Set `deletion_protection = false` on `google_sql_database_instance` so `./destroy.sh` can cleanly tear down the instance.
