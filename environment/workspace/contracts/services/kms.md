# KMS

Create four distinct customer managed KMS keys. Enable rotation on every key,
configure a deletion window of at least seven days and create one alias that
targets each key.

Write each key ARN to the corresponding `manifest.json` field:

| Key purpose | Manifest field |
|---|---|
| Database | `kms.database_arn` |
| Messaging | `kms.messaging_arn` |
| Projection | `kms.projection_arn` |
| Audit | `kms.audit_arn` |
