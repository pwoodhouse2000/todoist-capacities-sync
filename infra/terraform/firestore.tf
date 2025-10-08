# Firestore database (in Native mode)
# Note: Firestore must be enabled manually in the console first
# or using gcloud: gcloud firestore databases create --region=us-central

# Grant service account Firestore access
resource "google_project_iam_member" "firestore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.sync_service.email}"
}

# Note: Firestore collections are created automatically when first used
# No explicit resource creation needed for collections

