# Cloud Run Service Contract

- Must run API image on Cloud Run (gen2) (`google_cloud_run_v2_service`).
- Minimum instances: 2 (`min_instance_count = 2`).
- Ingress settings: Set `ingress = "INGRESS_TRAFFIC_ALL"` on the API Cloud Run v2 service and `ingress = "INGRESS_TRAFFIC_INTERNAL_ONLY"` on worker Cloud Run/Cloud Function v2 services.
- Must use Serverless VPC Access connector (`vpc_access`) with `egress = "ALL_TRAFFIC"` (or `"PRIVATE_RANGES_ONLY"`) to access Cloud SQL and Memorystore.
- Must execute under a dedicated GCP Service Account with least privilege.
- Set `deletion_protection = false` on all `google_cloud_run_v2_service` resources so `./destroy.sh` can cleanly tear down the deployment.
