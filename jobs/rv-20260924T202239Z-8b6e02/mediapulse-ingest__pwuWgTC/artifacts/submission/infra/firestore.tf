resource "google_firestore_database" "main" {
  name             = local.firestore_db_name
  type             = "FIRESTORE_NATIVE"
  location_id      = var.region

}

# Composite index for the MediaCache entity cache collection/kind
resource "google_firestore_index" "cache" {
  project    = var.project_id
  database   = google_firestore_database.main.name
  collection = "MediaCache"

  fields {
    field_path = "ownerId"
    order      = "ASCENDING"
  }

  fields {
    field_path = "updatedAt"
    order      = "DESCENDING"
  }

  query_scope = "COLLECTION"
}
