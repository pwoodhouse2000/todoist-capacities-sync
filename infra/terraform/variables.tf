variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region for resources"
  type        = string
  default     = "us-central1"
}

variable "service_name" {
  description = "Name of the Cloud Run service"
  type        = string
  default     = "todoist-capacities-sync"
}

variable "image" {
  description = "Container image for Cloud Run"
  type        = string
}

variable "firestore_namespace" {
  description = "Firestore namespace/collection prefix"
  type        = string
  default     = "todoist-capacities-v1"
}

variable "default_timezone" {
  description = "Default timezone for the application"
  type        = string
  default     = "America/Los_Angeles"
}

variable "pubsub_topic" {
  description = "Pub/Sub topic name"
  type        = string
  default     = "todoist-sync-jobs"
}

variable "pubsub_subscription" {
  description = "Pub/Sub subscription name"
  type        = string
  default     = "todoist-sync-worker"
}

variable "capacities_space_id" {
  description = "Capacities Space ID"
  type        = string
}

variable "reconcile_schedule" {
  description = "Cron schedule for reconciliation (default: hourly)"
  type        = string
  default     = "0 * * * *"
}

