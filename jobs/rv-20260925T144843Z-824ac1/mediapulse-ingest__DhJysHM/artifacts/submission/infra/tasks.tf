resource "google_cloud_tasks_queue" "rebuild" {
  name     = "${local.prefix}-rebuild-queue"
  project  = local.project
  location = local.region
}
