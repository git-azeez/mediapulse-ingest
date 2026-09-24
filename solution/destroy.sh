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

PREFIX=""
PROJECT_ID=""
REGION=""
GCP_EP="http://gcp:4588"

if [[ -r "$CONFIG_FILE" ]]; then
  PREFIX="$(jq -r '.resource_prefix // ""' "$CONFIG_FILE")"
  PROJECT_ID="$(jq -r '.gcp_project_id // ""' "$CONFIG_FILE")"
  REGION="$(jq -r '.region // "us-central1"' "$CONFIG_FILE")"
  GCP_EP="$(jq -r '.gcp_endpoint_url // "http://gcp:4588"' "$CONFIG_FILE")"
elif [[ -r "$TFVARS_PATH" ]]; then
  PREFIX="$(jq -r '.prefix // ""' "$TFVARS_PATH")"
  PROJECT_ID="$(jq -r '.gcp_project_id // ""' "$TFVARS_PATH")"
  REGION="$(jq -r '.gcp_region // "us-central1"' "$TFVARS_PATH")"
  GCP_EP="$(jq -r '.gcp_endpoint_url // "http://gcp:4588"' "$TFVARS_PATH")"
fi
GCP_EP="${GCP_EP%/}"

if [[ -f "$STATE_PATH" ]] && [[ -r "$TFVARS_PATH" ]]; then
  if [[ -n "$PREFIX" ]] && grep -q "$PREFIX" "$STATE_PATH" 2>/dev/null; then
    export TF_IN_AUTOMATION=1
    export TF_INPUT=0
    unset TF_PLUGIN_CACHE_DIR
    export GOOGLE_RESOURCE_MANAGER_CUSTOM_ENDPOINT="${GCP_EP}/v1/"
    export GOOGLE_CLOUD_RESOURCE_MANAGER_CUSTOM_ENDPOINT="${GCP_EP}/v1/"
    export GOOGLE_IAM_CUSTOM_ENDPOINT="${GCP_EP}/v1/"
    export GOOGLE_LOGGING_CUSTOM_ENDPOINT="${GCP_EP}/v2/"
    export GOOGLE_MONITORING_CUSTOM_ENDPOINT="${GCP_EP}/v3/"

    rm -rf "$INFRA_DIR/.terraform" "$INFRA_DIR/.terraform.lock.hcl"
    terraform -chdir="$INFRA_DIR" init -input=false -no-color >/dev/null 2>&1 || true
    timeout 90 terraform -chdir="$INFRA_DIR" destroy -input=false -auto-approve -lock-timeout=30s -no-color || true
  fi
fi

# Ensure all trial-prefixed resources in the live control plane are cleanly deleted
if [[ -n "$PREFIX" && -n "$PROJECT_ID" ]]; then
  for sub in $(curl -s "${GCP_EP}/v1/projects/${PROJECT_ID}/subscriptions" | jq -r --arg p "$PREFIX" '.subscriptions[]?.name // empty | select(contains($p))'); do
    curl -s -X DELETE "${GCP_EP}/v1/${sub}" >/dev/null 2>&1 || true
  done
  for topic in $(curl -s "${GCP_EP}/v1/projects/${PROJECT_ID}/topics" | jq -r --arg p "$PREFIX" '.topics[]?.name // empty | select(contains($p))'); do
    curl -s -X DELETE "${GCP_EP}/v1/${topic}" >/dev/null 2>&1 || true
  done
  for bucket in $(curl -s "${GCP_EP}/storage/v1/b?project=${PROJECT_ID}" | jq -r --arg p "$PREFIX" '.items[]?.name // empty | select(contains($p))'); do
    curl -s -X DELETE "${GCP_EP}/storage/v1/b/${bucket}" >/dev/null 2>&1 || true
  done
  for net in $(curl -s "${GCP_EP}/compute/v1/projects/${PROJECT_ID}/global/networks" | jq -r --arg p "$PREFIX" '.items[]?.name // empty | select(contains($p))'); do
    curl -s -X DELETE "${GCP_EP}/compute/v1/projects/${PROJECT_ID}/global/networks/${net}" >/dev/null 2>&1 || true
  done
  for svc in $(curl -s "${GCP_EP}/v2/projects/${PROJECT_ID}/locations/${REGION}/services" | jq -r --arg p "$PREFIX" '.services[]?.name // empty | select(contains($p))'); do
    svc_short="${svc##*/}"
    curl -s -X DELETE "${GCP_EP}/v2/projects/${PROJECT_ID}/locations/${REGION}/services/${svc_short}" >/dev/null 2>&1 || true
  done
  for fn in $(curl -s "${GCP_EP}/v2/projects/${PROJECT_ID}/locations/${REGION}/functions" | jq -r --arg p "$PREFIX" '.functions[]?.name // empty | select(contains($p))'); do
    fn_short="${fn##*/}"
    curl -s -X DELETE "${GCP_EP}/v2/projects/${PROJECT_ID}/locations/${REGION}/functions/${fn_short}" >/dev/null 2>&1 || true
  done
  for sql_inst in $(curl -s "${GCP_EP}/sql/v1beta4/projects/${PROJECT_ID}/instances" | jq -r --arg p "$PREFIX" '.items[]?.name // empty | select(contains($p))'); do
    sql_short="${sql_inst##*/}"
    curl -s -X DELETE "${GCP_EP}/sql/v1beta4/projects/${PROJECT_ID}/instances/${sql_short}" >/dev/null 2>&1 || true
  done
fi

rm -rf "$INFRA_DIR/.terraform" "$INFRA_DIR/.terraform.lock.hcl" "$STATE_PATH" "${STATE_PATH}.backup"
printf 'MediaPulse Ingest resources destroyed.\n'
