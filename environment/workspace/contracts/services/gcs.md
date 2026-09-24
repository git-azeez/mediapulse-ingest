# Google Cloud Storage (GCS) Contract

- Bucket Name: Derived from resource prefix (e.g., `<prefix>-audit-logs`).
- Public Access: Prevented (`public_access_prevention = "enforced"`).
- Encryption: Customer-Managed Encryption Key (CMEK) via Cloud KMS.
- Prefix Structure: `events/YYYY/MM/DD/batch-<uuid>.ndjson`.
