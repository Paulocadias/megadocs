# Cloud Armor Security Policy
resource "google_compute_security_policy" "policy" {
  name    = "megadoc-security-policy"
  project = var.project_id

  # Rule 1: Allow specific IPs (e.g., corporate VPN)
  rule {
    action   = "allow"
    priority = "1000"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["0.0.0.0/0"] # Replace with specific IPs in prod
      }
    }
    description = "Allow access"
  }

  # Rule 2: Rate Limiting (Throttle excessive requests)
  rule {
    action   = "rate_based_ban"
    priority = "2000"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["0.0.0.0/0"]
      }
    }
    rate_limit_options {
      rate_limit_threshold {
        count        = 1000
        interval_sec = 60
      }
      ban_duration_sec = 300
    }
    description = "Rate limit to 1000 req/min"
  }

  # Default Rule: Deny everything else (if not allowed above)
  # For this demo, we default allow, but in strict zero-trust, this would be deny(403)
  rule {
    action   = "allow"
    priority = "2147483647"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    description = "Default rule"
  }
}

# IAM Service Account for GKE Workload Identity
resource "google_service_account" "gke_sa" {
  account_id   = "megadoc-gke-sa"
  display_name = "GKE Service Account for MegaDoc"
  project      = var.project_id
}

# Grant GKE SA access to Storage
resource "google_storage_bucket_iam_member" "gke_storage_access" {
  bucket = google_storage_bucket.documents.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.gke_sa.email}"
}
