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
  ]
}

# IAM policy: Grant access only to specific users/service accounts
# By default, Cloud Run v2 requires authentication (no public access)
# Only members in allowed_invokers will have access
resource "google_cloud_run_service_iam_member" "invokers" {
  for_each = toset(var.allowed_invokers)

  location = google_cloud_run_v2_service.mcp_server.location
  service  = google_cloud_run_v2_service.mcp_server.name
  role     = "roles/run.invoker"
  member   = each.value
}

