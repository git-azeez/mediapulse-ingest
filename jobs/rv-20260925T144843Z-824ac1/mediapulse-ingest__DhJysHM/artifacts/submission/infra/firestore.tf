resource "google_firestore_database" "main" {
  name        = "(default)"
  project     = local.project
  location_id = local.region
  type        = "FIRESTORE_NATIVE"
}

# Cloud Datastore / Firestore index for the MediaCache kind
resource "google_firestore_index" "media_cache" {
  project    = local.project
  database   = google_firestore_database.main.name
  collection = "MediaCache"
  query_scope = "COLLECTION"

  fields {
    field_path = "namespace"
    order      = "ASCENDING"
  }

  fields {
    field_path = "updatedAt"
    order      = "DESCENDING"
  }
}
