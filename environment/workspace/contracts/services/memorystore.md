# Cloud Datastore Cache Contract

- Engine (`cache.engine`): `"cloud-datastore"`.
- Namespace (`cache.datastore_namespace`): `<resource_prefix>-cache`.
- Emulator/Endpoint Host (`cache.emulator_host`): Host/port of the Floci-GCP Datastore endpoint (`gcp:4588`).
- Purpose: Low-latency read-through cache in front of Cloud Firestore projections (`X-Projection-Cache: HIT` / `MISS`).
