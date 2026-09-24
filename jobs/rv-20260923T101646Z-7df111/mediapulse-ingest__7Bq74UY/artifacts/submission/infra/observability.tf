resource "google_logging_project_sink" "audit_sink" {
  name        = "${var.prefix}-audit-sink"
  destination = "storage.googleapis.com/${google_storage_bucket.audit.name}"
  filter      = "resource.type = cloud_run_revision OR resource.type = cloud_function"

  unique_writer_identity = true
}

resource "google_storage_bucket_iam_member" "sink_writer" {
  bucket = google_storage_bucket.audit.name
  role   = "roles/storage.objectCreator"
  member = google_logging_project_sink.audit_sink.writer_identity
}
