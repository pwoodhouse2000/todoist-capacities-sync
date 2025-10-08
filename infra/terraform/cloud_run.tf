# Service account for Cloud Run
resource "google_service_account" "sync_service" {
  account_id   = "${var.service_name}-sa"
  display_name = "Todoist-Capacities Sync Service Account"
  description  = "Service account for the Todoist-Capacities sync service"
}

# Grant necessary permissions to service account
resource "google_project_iam_member" "service_account_permissions" {
  for_each = toset([
    "roles/secretmanager.secretAccessor",
    "roles/datastore.user",
    "roles/pubsub.publisher",
    "roles/pubsub.subscriber",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.sync_service.email}"
}

# Cloud Run service
resource "google_cloud_run_service" "sync_service" {
  name     = var.service_name
  location = var.region

  template {
    spec {
      service_account_name = google_service_account.sync_service.email

      containers {
        image = var.image

        env {
          name  = "GCP_PROJECT_ID"
          value = var.project_id
        }

        env {
          name  = "FIRESTORE_NAMESPACE"
          value = var.firestore_namespace
        }

        env {
          name  = "DEFAULT_TIMEZONE"
          value = var.default_timezone
        }

        env {
          name  = "PUBSUB_TOPIC"
          value = var.pubsub_topic
        }

        env {
          name  = "PUBSUB_SUBSCRIPTION"
          value = var.pubsub_subscription
        }

        env {
          name  = "LOG_LEVEL"
          value = "INFO"
        }

        env {
          name  = "CAPACITIES_SPACE_ID"
          value = var.capacities_space_id
        }

        # Secrets from Secret Manager
        env {
          name = "TODOIST_OAUTH_TOKEN"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.todoist_token.secret_id
              key  = "latest"
            }
          }
        }

        env {
          name = "CAPACITIES_API_KEY"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.capacities_key.secret_id
              key  = "latest"
            }
          }
        }

        env {
          name = "INTERNAL_CRON_TOKEN"
          value_from {
            secret_key_ref {
              name = google_secret_manager_secret.cron_token.secret_id
              key  = "latest"
            }
          }
        }

        resources {
          limits = {
            cpu    = "1000m"
            memory = "512Mi"
          }
        }
      }
    }

    metadata {
      annotations = {
        "autoscaling.knative.dev/maxScale" = "10"
        "autoscaling.knative.dev/minScale" = "0"
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  depends_on = [
    google_project_service.required_apis,
    google_secret_manager_secret_version.todoist_token,
    google_secret_manager_secret_version.capacities_key,
    google_secret_manager_secret_version.cron_token,
  ]
}

# Allow public access to Cloud Run service
resource "google_cloud_run_service_iam_member" "public_access" {
  service  = google_cloud_run_service.sync_service.name
  location = google_cloud_run_service.sync_service.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

