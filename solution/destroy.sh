#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$SCRIPT_DIR/infra"
TFVARS_PATH="$INFRA_DIR/config.auto.tfvars.json"
STATE_PATH="$INFRA_DIR/terraform.tfstate"

if ! command -v terraform >/dev/null 2>&1; then
  echo "MediaPulse Ingest requires terraform on PATH" >&2
  exit 2
fi

if [[ ! -f "$STATE_PATH" ]]; then
  printf 'MediaPulse Ingest has no Terraform state; nothing to destroy.\n'
  exit 0
fi

if [[ ! -r "$TFVARS_PATH" ]]; then
  echo "Cannot destroy safely because deployment inputs are missing: $TFVARS_PATH" >&2
  exit 2
fi

export TF_IN_AUTOMATION=1
export TF_INPUT=0
unset TF_PLUGIN_CACHE_DIR
GCP_EP="$(jq -r '.gcp_endpoint_url // "http://gcp:4588"' "$TFVARS_PATH" 2>/dev/null || echo "http://gcp:4588")"
export GOOGLE_RESOURCE_MANAGER_CUSTOM_ENDPOINT="${GCP_EP%/}/v1/"
export GOOGLE_CLOUD_RESOURCE_MANAGER_CUSTOM_ENDPOINT="${GCP_EP%/}/v1/"
export GOOGLE_IAM_CUSTOM_ENDPOINT="${GCP_EP%/}/v1/"
export GOOGLE_LOGGING_CUSTOM_ENDPOINT="${GCP_EP%/}/v2/"
export GOOGLE_MONITORING_CUSTOM_ENDPOINT="${GCP_EP%/}/v3/"

rm -rf "$INFRA_DIR/.terraform" "$INFRA_DIR/.terraform.lock.hcl"
terraform -chdir="$INFRA_DIR" init -input=false -no-color

set +e
terraform -chdir="$INFRA_DIR" destroy -input=false -auto-approve -lock-timeout=60s -no-color
first_rc=$?
set -e

if (( first_rc != 0 )); then
  echo "First destroy returned $first_rc; refreshing and retrying once" >&2
  terraform -chdir="$INFRA_DIR" apply -refresh-only -input=false -auto-approve -lock-timeout=60s -no-color || true
  terraform -chdir="$INFRA_DIR" destroy -input=false -auto-approve -lock-timeout=60s -no-color
fi

remaining="$(terraform -chdir="$INFRA_DIR" state list 2>/dev/null | wc -l | tr -d ' ')"
rm -rf "$INFRA_DIR/.terraform" "$INFRA_DIR/.terraform.lock.hcl"
if [[ "$remaining" != "0" ]]; then
  echo "Destroy left $remaining Terraform resources in state" >&2
  exit 1
fi

printf 'MediaPulse Ingest resources destroyed.\n'
