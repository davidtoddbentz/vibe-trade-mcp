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

variable "allowed_invokers" {
  description = "List of IAM members (users/service accounts) allowed to invoke the Cloud Run service. Format: 'user:email@example.com' or 'serviceAccount:sa@project.iam.gserviceaccount.com'. If empty, only project owners/admins can access."
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for invoker in var.allowed_invokers : can(regex("^(user|serviceAccount|group|domain):", invoker))])
    error_message = "Each invoker must start with 'user:', 'serviceAccount:', 'group:', or 'domain:'"
  }
}

variable "firestore_location" {
  description = "Firestore location (e.g., us-central, us-east1). Must be a multi-region location for Firestore Native mode."
  type        = string
  default     = "us-central"

  validation {
    condition     = can(regex("^(us-central|us-east1|us-west1|europe-west1|asia-northeast1)$", var.firestore_location))
    error_message = "Firestore location must be a valid multi-region location: us-central, us-east1, us-west1, europe-west1, or asia-northeast1"
  }
}

