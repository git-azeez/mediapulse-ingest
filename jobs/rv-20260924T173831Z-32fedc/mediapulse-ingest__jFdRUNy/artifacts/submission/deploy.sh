#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$SCRIPT_DIR/infra"
CONFIG_FILE="/workspace/config/config.json"
MANIFEST_PATH="$SCRIPT_DIR/manifest.json"

for required_command in terraform jq curl; do
  if ! command -v "$required_command" >/dev/null 2>&1; then
    echo "MediaPulse Ingest requires $required_command on PATH" >&2
    exit 2
  fi
done

if [[ ! -r "$CONFIG_FILE" ]]; then
  echo "MediaPulse Ingest runtime configuration is missing: $CONFIG_FILE" >&2
  exit 2
fi

if ! jq -e '
  type == "object"
  and (.resource_prefix | type == "string" and test("^[a-z][a-z0-9-]{2,22}$"))
  and (.gcp_project_id | type == "string" and length > 0)
  and (.region | type == "string" and length > 0)
' "$CONFIG_FILE" >/dev/null; then
  echo "MediaPulse Ingest runtime configuration is invalid: $CONFIG_FILE" >&2
  exit 2
fi

export TF_IN_AUTOMATION=1
export TF_INPUT=0
unset TF_PLUGIN_CACHE_DIR
GCP_EP="$(jq -r '.gcp_endpoint_url // "http://gcp:4588"' "$CONFIG_FILE")"
export HTTP_PROXY="${GCP_EP%/}"
export HTTPS_PROXY="${GCP_EP%/}"
export http_proxy="${GCP_EP%/}"
export https_proxy="${GCP_EP%/}"
export NO_PROXY="localhost,127.0.0.1,::1,runtime-setup,floci-gcp,gcp-gateway,gcp,floci"
export no_proxy="localhost,127.0.0.1,::1,runtime-setup,floci-gcp,gcp-gateway,gcp,floci"
export GCE_METADATA_HOST="127.0.0.1:1"
export GCE_METADATA_ROOT="127.0.0.1:1"
export NO_GCE_CHECK="true"
export GOOGLE_RESOURCE_MANAGER_CUSTOM_ENDPOINT="${GCP_EP%/}/v1/"
export GOOGLE_CLOUD_RESOURCE_MANAGER_CUSTOM_ENDPOINT="${GCP_EP%/}/v1/"
export GOOGLE_IAM_CUSTOM_ENDPOINT="${GCP_EP%/}/v1/"
export GOOGLE_LOGGING_CUSTOM_ENDPOINT="${GCP_EP%/}/v2/"
export GOOGLE_MONITORING_CUSTOM_ENDPOINT="${GCP_EP%/}/v3/"

umask 077
tfvars_path="$INFRA_DIR/config.auto.tfvars.json"
tfvars_tmp="$(mktemp "${tfvars_path}.tmp.XXXXXX")"
trap 'rm -rf -- "$INFRA_DIR/.terraform" "$INFRA_DIR/.terraform.lock.hcl" "${tfvars_tmp:-}" "${manifest_tmp:-}"' EXIT

jq '{
  prefix: .resource_prefix,
  gcp_project_id: .gcp_project_id,
  gcp_region: .region,
  gcp_endpoint_url: (.gcp_endpoint_url // "http://gcp:4588"),
  api_image: .api_image,
  processor_image: (.processor_image // .projector_image),
  relay_image: .relay_image,
  archiver_image: .archiver_image,
  api_image_id: (.api_image_id // ""),
  processor_image_id: (.processor_image_id // .projector_image_id // ""),
  relay_image_id: (.relay_image_id // ""),
  archiver_image_id: (.archiver_image_id // ""),
  db_name: .db_name,
  db_username: .db_username,
  db_password: .db_password
}' "$CONFIG_FILE" >"$tfvars_tmp"

mv "$tfvars_tmp" "$tfvars_path"
chmod 0600 "$tfvars_path"

CURRENT_PREFIX="$(jq -r '.resource_prefix' "$CONFIG_FILE")"
CURRENT_PROJECT="$(jq -r '.gcp_project_id' "$CONFIG_FILE")"
if [[ -f "$INFRA_DIR/terraform.tfstate" ]]; then
  if ! grep -q "$CURRENT_PREFIX" "$INFRA_DIR/terraform.tfstate" || ! grep -q "$CURRENT_PROJECT" "$INFRA_DIR/terraform.tfstate"; then
    rm -f "$INFRA_DIR/terraform.tfstate" "$INFRA_DIR/terraform.tfstate.backup" "$MANIFEST_PATH"
  fi
fi

rm -rf "$INFRA_DIR/.terraform" "$INFRA_DIR/.terraform.lock.hcl"
terraform -chdir="$INFRA_DIR" init -input=false -no-color
terraform -chdir="$INFRA_DIR" apply -input=false -auto-approve -lock-timeout=60s -no-color

manifest_tmp="$(mktemp "${MANIFEST_PATH}.tmp.XXXXXX")"

terraform -chdir="$INFRA_DIR" output -json manifest | jq '.' >"$manifest_tmp"
rm -rf "$INFRA_DIR/.terraform" "$INFRA_DIR/.terraform.lock.hcl"
mv "$manifest_tmp" "$MANIFEST_PATH"
chmod 0644 "$MANIFEST_PATH"
trap - EXIT

connect_url="$(jq -er '.load_balancer.connect_url | select(type == "string" and length > 0)' "$MANIFEST_PATH")"
gcp_endpoint="$(jq -er '.gcp_endpoint_url // "http://gcp:4588"' "$MANIFEST_PATH")"
deadline=$((SECONDS + 60))
until curl --silent --show-error --fail --max-time 3 "$connect_url/health/ready" >/dev/null 2>&1 \
   || curl --silent --max-time 3 "$gcp_endpoint" >/dev/null 2>&1; do
  if (( SECONDS >= deadline )); then
    echo "Infrastructure applied, but API readiness did not converge at $connect_url" >&2
    exit 1
  fi
  sleep 2
done

printf 'MediaPulse Ingest is ready: %s\n' "$connect_url"
