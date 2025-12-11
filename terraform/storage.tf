# Cloud Storage for Document Storage
resource "google_storage_bucket" "documents" {
  name          = "megadoc-documents-${var.project_id}"
  location      = var.region
  project       = var.project_id
  force_destroy = false

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }
}

# Cloud SQL for Metadata (PostgreSQL)
resource "google_sql_database_instance" "metadata" {
  name             = "megadoc-metadata-db"
  database_version = "POSTGRES_15"
  region           = var.region
  project          = var.project_id

  settings {
    tier = "db-f1-micro" # Use larger tier for production
    
    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.vpc.id
    }

    backup_configuration {
      enabled = true
    }
  }

  deletion_protection = true
}

resource "google_sql_database" "database" {
  name     = "megadoc_db"
  instance = google_sql_database_instance.metadata.name
  project  = var.project_id
}
