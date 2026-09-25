locals {
  prefix      = var.resource_prefix
  common_labels = {
    mediapulse_deployment = var.resource_prefix
    managed_by            = "terraform"
  }

  # Network
  vpc_name             = "${var.resource_prefix}-vpc"
  ingress_subnet_name  = "${var.resource_prefix}-ingress-subnet"
  private_subnet_name  = "${var.resource_prefix}-private-subnet"
  ingress_subnet_cidr  = "10.10.0.0/20"
  private_subnet_cidr  = "10.20.0.0/20"

  # KMS
  keyring_name      = "${var.resource_prefix}-keyring"
  kms_db_key       = "${var.resource_prefix}-db-key"
  kms_msg_key      = "${var.resource_prefix}-msg-key"
  kms_proj_key     = "${var.resource_prefix}-proj-key"
  kms_audit_key    = "${var.resource_prefix}-audit-key"

  # Cloud SQL
  sql_instance_name = "${var.resource_prefix}-pg"

  # Secret
  db_secret_name    = "${var.resource_prefix}-db-url"

  # Pub/Sub
  topic_name        = "${var.resource_prefix}-events"
  subscription_name = "${var.resource_prefix}-proc-sub"
  dlq_topic_name    = "${var.resource_prefix}-events-dlq"
  dlq_sub_name      = "${var.resource_prefix}-dlq-sub"

  # Cloud Tasks
  rebuild_queue_name = "${var.resource_prefix}-rebuild-queue"

  # Firestore / Datastore
  firestore_db_name = "${var.resource_prefix}-fs"
  datastore_namespace = "${var.resource_prefix}-cache"

  # GCS / BigQuery
  audit_bucket_name = "${var.resource_prefix}-audit-logs"
  bq_dataset_id      = "${replace(var.resource_prefix, "-", "_")}_audit"
  bq_table_id        = "audit_events"

  # Cloud Run
  run_service_name   = "${var.resource_prefix}-api-svc"
  vpc_connector_name = "${var.resource_prefix}-vpc-conn"

  # Cloud Functions
  processor_fn_name = "${var.resource_prefix}-processor"
  relay_fn_name     = "${var.resource_prefix}-relay"
  archiver_fn_name  = "${var.resource_prefix}-archiver"

  # Scheduler
  relay_job_name    = "${var.resource_prefix}-relay-job"
  archiver_job_name = "${var.resource_prefix}-archiver-job"

  # Identity Platform
  tenant_name = "${var.resource_prefix}-tenant"

  # Service accounts
  api_sa       = "${var.resource_prefix}-api-sa"
  proc_sa      = "${var.resource_prefix}-proc-sa"
  relay_sa     = "${var.resource_prefix}-relay-sa"
  archiver_sa  = "${var.resource_prefix}-archiver-sa"
  sched_sa     = "${var.resource_prefix}-sched-sa"
  read_sa      = "${var.resource_prefix}-read-sa"
  write_sa     = "${var.resource_prefix}-write-sa"
  admin_sa     = "${var.resource_prefix}-admin-sa"

  # Load Balancer
  lb_ip_name        = "${var.resource_prefix}-lb-ip"
  neg_name         = "${var.resource_prefix}-neg"
  backend_name      = "${var.resource_prefix}-backend"
  urlmap_name       = "${var.resource_prefix}-urlmap"
  proxy_name        = "${var.resource_prefix}-http-proxy"
  fr_name           = "${var.resource_prefix}-fr"

  # Logging
  log_bucket_name   = "${var.resource_prefix}-logs-bucket"
  log_sink_api      = "${var.resource_prefix}-sink-api"
  log_sink_proc     = "${var.resource_prefix}-sink-proc"
  log_sink_relay    = "${var.resource_prefix}-sink-relay"
  log_sink_archiver = "${var.resource_prefix}-sink-archiver"
  notify_channel    = "${var.resource_prefix}-notify"
}
