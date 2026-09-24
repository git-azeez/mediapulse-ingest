# Cloud KMS

Create a dedicated `google_kms_key_ring` and four distinct customer-managed `google_kms_crypto_key` resources with `rotation_period = "7776000s"` (90 days).

Write the keyring ID and each key ID to the corresponding `manifest.json` field:

| Key purpose | Manifest field |
|---|---|
| KeyRing | `kms.keyring_id` |
| Database | `kms.database_key_id` |
| Messaging | `kms.messaging_key_id` |
| Projection | `kms.projection_key_id` |
| Audit | `kms.audit_key_id` |
