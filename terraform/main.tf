terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Enable required APIs
resource "google_project_service" "required_apis" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "firestore.googleapis.com",
  ])

  project = var.project_id
  service = each.value

  disable_on_destroy = false
}

# Artifact Registry repository for Docker images
resource "google_artifact_registry_repository" "docker_repo" {
  location      = var.region
  repository_id = "vibe-trade-mcp"
  description   = "Docker repository for Vibe Trade MCP server"
  format        = "DOCKER"

  depends_on = [google_project_service.required_apis]
}

# Service account for Cloud Run service
resource "google_service_account" "cloud_run_sa" {
  account_id   = "vibe-trade-mcp-runner"
  display_name = "Vibe Trade MCP Cloud Run Service Account"
  description  = "Service account for running the MCP server on Cloud Run"
}

# Firestore database (Native mode)
resource "google_firestore_database" "strategy" {
  project     = var.project_id
  name        = "strategy"
  location_id = var.firestore_location
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.required_apis]
}

# Grant Firestore access to Cloud Run service account
resource "google_project_iam_member" "firestore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"

  depends_on = [google_service_account.cloud_run_sa]
}

# Cloud Run service
resource "google_cloud_run_v2_service" "mcp_server" {
  name     = "vibe-trade-mcp"
  location = var.region

  template {
    service_account = google_service_account.cloud_run_sa.email

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker_repo.repository_id}/vibe-trade-mcp:latest"

      ports {
        container_port = 8080
      }

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "FIRESTORE_DATABASE"
        value = google_firestore_database.strategy.name
      }
      env {
        name  = "MCP_AUTH_TOKEN"
        value = var.mcp_auth_token
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }
  }

  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }

  depends_on = [
    google_project_service.required_apis,
    google_artifact_registry_repository.docker_repo,
    google_firestore_database.strategy,
  ]
}

# Make service publicly accessible (authentication handled by app-level middleware)
# This allows the app to handle auth with static tokens instead of IAM
resource "google_cloud_run_service_iam_member" "public_access" {
  location = google_cloud_run_v2_service.mcp_server.location
  service  = google_cloud_run_v2_service.mcp_server.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

