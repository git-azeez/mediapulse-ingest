resource "google_cloud_tasks_queue" "rebuild" {
  name     = local.rebuild_queue_name
  location = var.region

  rate_limits {
    max_concurrent_dispatches = 20
    max_dispatches_per_second  = 10
  }

  retry_config {
    max_attempts       = 10
    max_backoff        = "300s"
    min_backoff        = "10s"
    max_doublings      = 2
  }
}
