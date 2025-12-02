variable "project_id" {
  description = "GCP Project ID"
  type        = string
  default     = "vibe-trade-475704"
}

variable "region" {
  description = "GCP Region for Cloud Run and Artifact Registry"
  type        = string
  default     = "us-central1"
}

variable "firestore_location" {
  description = "Firestore location. For Native mode, use multi-region IDs: nam5 (US), eur3 (Europe), asia1 (Asia). Or single regions like us-central1, us-east1, etc."
  type        = string
  default     = "nam5"

  validation {
    condition     = can(regex("^(nam5|eur3|asia1|us-central1|us-east1|us-west1|europe-west1|asia-northeast1)$", var.firestore_location))
    error_message = "Firestore location must be a valid location: nam5, eur3, asia1 (multi-region) or us-central1, us-east1, us-west1, europe-west1, asia-northeast1 (single region)"
  }
}

variable "mcp_auth_token" {
  description = "Static authentication token for MCP server. If empty, authentication is disabled. Set this to a secure random string."
  type        = string
  default     = ""
  sensitive   = true
}

