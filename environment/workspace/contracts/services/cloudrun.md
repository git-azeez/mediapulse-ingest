# Cloud Run Service Contract

- Must run API image on Cloud Run (gen2).
- Minimum instances: 2.
- Ingress settings: Internal and Cloud Load Balancing (`all`).
- Must use Serverless VPC Access connector to access Cloud SQL and Memorystore.
- Must execute under a dedicated GCP Service Account with least privilege.
