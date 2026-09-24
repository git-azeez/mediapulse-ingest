# Cloud SQL PostgreSQL Contract

- Engine: PostgreSQL 15+.
- Connectivity: Private IP via VPC Private Service Access.
- Encryption: Must use Customer-Managed Encryption Key (CMEK) via Cloud KMS.
- Tables required: `media`, `events`, `outbox`.
