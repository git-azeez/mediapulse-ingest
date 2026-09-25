#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$SCRIPT_DIR/infra"
CONFIG_FILE="/workspace/config/config.json"
TFVARS_PATH="$INFRA_DIR/config.auto.tfvars.json"
STATE_PATH="$INFRA_DIR/terraform.tfstate"

if ! command -v terraform >/dev/null 2>&1; then
  echo "MediaPulse Ingest requires terraform on PATH" >&2
  exit 2
fi

GCP_EP="http://gcp:4588"
if [[ -r "$CONFIG_FILE" ]]; then
  GCP_EP="$(jq -r '.gcp_endpoint_url // "http://gcp:4588"' "$CONFIG_FILE")"
elif [[ -r "$TFVARS_PATH" ]]; then
  GCP_EP="$(jq -r '.gcp_endpoint_url // "http://gcp:4588"' "$TFVARS_PATH")"
fi
GCP_EP="${GCP_EP%/}"

if [[ -f "$STATE_PATH" ]]; then
  export TF_IN_AUTOMATION=1
  export TF_INPUT=0
  unset TF_PLUGIN_CACHE_DIR
  export HTTP_PROXY="${GCP_EP}"
  export HTTPS_PROXY="${GCP_EP}"
  export http_proxy="${GCP_EP}"
  export https_proxy="${GCP_EP}"
  export NO_PROXY="localhost,127.0.0.1,::1,runtime-setup,floci-gcp,gcp-gateway,gcp,floci"
  export no_proxy="localhost,127.0.0.1,::1,runtime-setup,floci-gcp,gcp-gateway,gcp,floci"
  export GCE_METADATA_HOST="127.0.0.1:1"
  export GCE_METADATA_ROOT="127.0.0.1:1"
  export NO_GCE_CHECK="true"
  export GOOGLE_RESOURCE_MANAGER_CUSTOM_ENDPOINT="${GCP_EP}/v1/"
  export GOOGLE_CLOUD_RESOURCE_MANAGER_CUSTOM_ENDPOINT="${GCP_EP}/v1/"
  export GOOGLE_IAM_CUSTOM_ENDPOINT="${GCP_EP}/v1/"
  export GOOGLE_LOGGING_CUSTOM_ENDPOINT="${GCP_EP}/v2/"
  export GOOGLE_MONITORING_CUSTOM_ENDPOINT="${GCP_EP}/v3/"

  if [[ ! -d "$INFRA_DIR/.terraform" ]]; then
    terraform -chdir="$INFRA_DIR" init -input=false -no-color >/dev/null
  fi
  terraform -chdir="$INFRA_DIR" destroy -input=false -auto-approve -lock-timeout=60s -no-color
fi

rm -rf "$INFRA_DIR/.terraform" "$INFRA_DIR/.terraform.lock.hcl" "$STATE_PATH" "${STATE_PATH}.backup"
printf 'MediaPulse Ingest resources destroyed.\n'
