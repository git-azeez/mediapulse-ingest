# Cloud Firestore (native) projections + MediaCache index

resource "google_firestore_database" "main" {
  name        = "(default)"
  project     = local.project_id
  location_id = local.region
  type        = "FIRESTORE_NATIVE"
}

resource "google_firestore_index" "mediacache" {
  project    = local.project_id
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
}

resource "google_firestore_index" "media_projections" {
  project    = local.project_id
  database   = google_firestore_database.main.name
  collection = "media_projections"

  fields {
    field_path = "ownerId"
    order      = "ASCENDING"
  }

  fields {
    field_path = "aggregateVersion"
    order      = "DESCENDING"
  }
}
