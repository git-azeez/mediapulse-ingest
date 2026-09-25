# Google Cloud Storage (GCS) Contract

- Bucket Name: Derived from resource prefix (e.g., `<prefix>-audit-logs`).
- Public Access: Prevented (`public_access_prevention = "enforced"`, `uniform_bucket_level_access = true`).
- Encryption: Customer-Managed Encryption Key (CMEK) via Cloud KMS (`encryption.default_kms_key_name`).
- Prefix Structure: `events/YYYY/MM/DD/batch-<uuid>.ndjson`.
- Lifecycle: Set `force_destroy = true` on `google_storage_bucket` so `./destroy.sh` can delete the bucket after audit objects are written.
