# Pub/Sub topic for sync jobs
resource "google_pubsub_topic" "sync_jobs" {
  name = var.pubsub_topic

  message_retention_duration = "86400s" # 24 hours

  depends_on = [google_project_service.required_apis]
}

# Pub/Sub subscription for workers
resource "google_pubsub_subscription" "sync_worker" {
  name  = var.pubsub_subscription
  topic = google_pubsub_topic.sync_jobs.name

  # Message retention
  message_retention_duration = "86400s"
  retain_acked_messages      = false

  # Acknowledgement deadline
  ack_deadline_seconds = 300 # 5 minutes

  # Retry policy
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  # Dead letter policy (optional)
  # dead_letter_policy {
  #   dead_letter_topic     = google_pubsub_topic.sync_jobs_dead_letter.id
  #   max_delivery_attempts = 5
  # }

  expiration_policy {
    ttl = "" # Never expire
  }

  depends_on = [google_project_service.required_apis]
}

# Grant service account permission to publish to topic
resource "google_pubsub_topic_iam_member" "publisher" {
  topic  = google_pubsub_topic.sync_jobs.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.sync_service.email}"
}

# Grant service account permission to subscribe
resource "google_pubsub_subscription_iam_member" "subscriber" {
  subscription = google_pubsub_subscription.sync_worker.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.sync_service.email}"
}

