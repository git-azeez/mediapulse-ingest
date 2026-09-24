#!/bin/sh
set -eu

APPLICATION_DIR="${APPLICATION_DIR:-/application}"
CONFIG_DIR="${CONFIG_DIR:-/config}"

mkdir -p "$CONFIG_DIR"

/bin/sh "$APPLICATION_DIR/build.sh"

image_id() {
  docker image inspect --format '{{.Id}}' "$1" 2>/dev/null || echo "sha256:0000000000000000000000000000000000000000000000000000000000000000"
}

rand_hex() {
  od -An -N"$1" -tx1 /dev/urandom | tr -d ' \n'
}

resource_prefix="mp-$(rand_hex 6)"
gcp_project_id="${GCP_PROJECT_ID:-mp-ver-$(rand_hex 4)}"
region_pool="us-central1 us-east1 us-west1 europe-west1"
region_index=$(( $(od -An -N1 -tu1 /dev/urandom | tr -d ' \n') % 4 + 1 ))
gcp_region="${GCP_REGION:-$(echo "$region_pool" | cut -d' ' -f"$region_index")}"
gcp_endpoint="${GCP_ENDPOINT_URL:-http://gcp:4588}"
image_ns="${IMAGE_NAMESPACE:-mediapulse}"
image_tag="${IMAGE_TAG:-1.0.0}"

api_ref="${image_ns}/api:${image_tag}"
processor_ref="${image_ns}/projector:${image_tag}"
relay_ref="${image_ns}/relay:${image_tag}"
archiver_ref="${image_ns}/archiver:${image_tag}"

db_name="mp_$(rand_hex 3)"
db_username="mp_user_$(rand_hex 3)"
db_password="Mp$(rand_hex 12)!"
config_tmp="$CONFIG_DIR/config.json.tmp"

cat >"$config_tmp" <<EOF
{
  "resource_prefix": "$resource_prefix",
  "gcp_project_id": "$gcp_project_id",
  "region": "$gcp_region",
  "gcp_endpoint_url": "$gcp_endpoint",
  "api_image": "$api_ref",
  "processor_image": "$processor_ref",
  "projector_image": "$processor_ref",
  "relay_image": "$relay_ref",
  "archiver_image": "$archiver_ref",
  "api_image_id": "$(image_id "$api_ref")",
  "processor_image_id": "$(image_id "$processor_ref")",
  "projector_image_id": "$(image_id "$processor_ref")",
  "relay_image_id": "$(image_id "$relay_ref")",
  "archiver_image_id": "$(image_id "$archiver_ref")",
  "db_name": "$db_name",
  "db_username": "$db_username",
  "db_password": "$db_password"
}
EOF

chmod 0444 "$config_tmp"
mv "$config_tmp" "$CONFIG_DIR/config.json"

# Seed pre-existing baseline decoy resources in the shared GCP project
if command -v wget >/dev/null 2>&1; then
  wget -q -O /dev/null --header="Content-Type: application/json" --post-data='{"name":"decoy-shared-vpc","autoCreateSubnetworks":false}' "$gcp_endpoint/compute/v1/projects/$gcp_project_id/global/networks" 2>/dev/null || true
  wget -q -O /dev/null --header="Content-Type: application/json" --post-data="{\"name\":\"decoy-$gcp_project_id-shared-bucket\",\"location\":\"$gcp_region\"}" "$gcp_endpoint/storage/v1/b?project=$gcp_project_id" 2>/dev/null || true
fi

echo "MediaPulse Ingest verifier dynamic configuration generated."
