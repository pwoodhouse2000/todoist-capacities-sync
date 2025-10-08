# Secret for Todoist OAuth token
resource "google_secret_manager_secret" "todoist_token" {
  secret_id = "TODOIST_OAUTH_TOKEN"

  replication {
    auto {}
  }

  depends_on = [google_project_service.required_apis]
}

resource "google_secret_manager_secret_version" "todoist_token" {
  secret = google_secret_manager_secret.todoist_token.id

  # The actual secret value should be provided via terraform.tfvars or environment
  # For initial setup, use the seed_secrets.sh script instead
  secret_data = "PLACEHOLDER_SET_VIA_SCRIPT"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

# Secret for Capacities API key
resource "google_secret_manager_secret" "capacities_key" {
  secret_id = "CAPACITIES_API_KEY"

  replication {
    auto {}
  }

  depends_on = [google_project_service.required_apis]
}

resource "google_secret_manager_secret_version" "capacities_key" {
  secret = google_secret_manager_secret.capacities_key.id

  secret_data = "PLACEHOLDER_SET_VIA_SCRIPT"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

# Secret for internal cron token
resource "google_secret_manager_secret" "cron_token" {
  secret_id = "INTERNAL_CRON_TOKEN"

  replication {
    auto {}
  }

  depends_on = [google_project_service.required_apis]
}

resource "google_secret_manager_secret_version" "cron_token" {
  secret = google_secret_manager_secret.cron_token.id

  secret_data = "PLACEHOLDER_SET_VIA_SCRIPT"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

# Grant service account access to secrets
resource "google_secret_manager_secret_iam_member" "todoist_token_access" {
  secret_id = google_secret_manager_secret.todoist_token.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.sync_service.email}"
}

resource "google_secret_manager_secret_iam_member" "capacities_key_access" {
  secret_id = google_secret_manager_secret.capacities_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.sync_service.email}"
}

resource "google_secret_manager_secret_iam_member" "cron_token_access" {
  secret_id = google_secret_manager_secret.cron_token.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.sync_service.email}"
}

