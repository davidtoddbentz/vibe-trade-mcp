output "service_url" {
  description = "URL of the Cloud Run service"
  value       = google_cloud_run_v2_service.mcp_server.uri
}

output "mcp_endpoint" {
  description = "MCP endpoint URL"
  value       = "${google_cloud_run_v2_service.mcp_server.uri}/mcp"
}

output "artifact_registry_url" {
  description = "Artifact Registry repository URL for pushing images"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker_repo.repository_id}"
}

output "service_name" {
  description = "Cloud Run service name"
  value       = google_cloud_run_v2_service.mcp_server.name
}

output "service_location" {
  description = "Cloud Run service location"
  value       = google_cloud_run_v2_service.mcp_server.location
}

output "project_id" {
  description = "GCP Project ID"
  value       = var.project_id
}

output "region" {
  description = "GCP Region"
  value       = var.region
}

output "firestore_location" {
  description = "Firestore database location"
  value       = google_firestore_database.strategy.location_id
}

output "firestore_database_name" {
  description = "Firestore database name"
  value       = google_firestore_database.strategy.name
}

