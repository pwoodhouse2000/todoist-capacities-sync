# Service account for Cloud Scheduler
resource "google_service_account" "scheduler" {
  account_id   = "${var.service_name}-scheduler"
  display_name = "Cloud Scheduler for Todoist-Capacities Sync"
}

# Grant scheduler permission to invoke Cloud Run
resource "google_cloud_run_service_iam_member" "scheduler_invoker" {
  service  = google_cloud_run_service.sync_service.name
  location = google_cloud_run_service.sync_service.location
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

# Cloud Scheduler job for hourly reconciliation
resource "google_cloud_scheduler_job" "reconcile" {
  name             = "${var.service_name}-reconcile"
  description      = "Hourly reconciliation of Todoist @capsync tasks"
  schedule         = var.reconcile_schedule
  time_zone        = var.default_timezone
  attempt_deadline = "600s" # 10 minutes

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_service.sync_service.status[0].url}/reconcile"

    headers = {
      "Content-Type" = "application/json"
    }

    # Authorization header with internal token
    oidc_token {
      service_account_email = google_service_account.scheduler.email
    }

    # Note: The INTERNAL_CRON_TOKEN will need to be passed in the Authorization header
    # This requires the scheduler to have access to the secret
  }

  retry_config {
    retry_count          = 3
    max_retry_duration   = "0s"
    min_backoff_duration = "5s"
    max_backoff_duration = "3600s"
    max_doublings        = 5
  }

  depends_on = [
    google_project_service.required_apis,
    google_cloud_run_service.sync_service,
  ]
}

