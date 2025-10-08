output "cloud_run_url" {
  description = "URL of the deployed Cloud Run service"
  value       = google_cloud_run_service.sync_service.status[0].url
}

output "pubsub_topic" {
  description = "Pub/Sub topic name"
  value       = google_pubsub_topic.sync_jobs.name
}

output "pubsub_subscription" {
  description = "Pub/Sub subscription name"
  value       = google_pubsub_subscription.sync_worker.name
}

output "webhook_url" {
  description = "Todoist webhook URL"
  value       = "${google_cloud_run_service.sync_service.status[0].url}/todoist/webhook"
}

output "reconcile_url" {
  description = "Reconcile endpoint URL"
  value       = "${google_cloud_run_service.sync_service.status[0].url}/reconcile"
}

output "service_account_email" {
  description = "Service account email"
  value       = google_service_account.sync_service.email
}

