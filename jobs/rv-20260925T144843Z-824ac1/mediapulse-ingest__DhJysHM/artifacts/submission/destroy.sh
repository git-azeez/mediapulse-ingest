#!/usr/bin/env bash
# MediaPulse Ingest - clean teardown of all GCP resources for this deployment.
# Uses Terraform/OpenTofu state so only managed resources are removed; any
# pre-existing baseline resources (decoy VPC/bucket, etc.) are untouched.
set -euo pipefail

SUB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="${SUB_DIR}/infra"
TF_PLUGIN_CACHE_DIR="/opt/terraform-plugin-cache"
export TF_PLUGIN_CACHE_DIR
export TF_IN_AUTOMATION=1
export TF_INPUT=0
export TF_LOG=ERROR
export GOOGLE_OAUTH_ACCESS_TOKEN="${GOOGLE_OAUTH_ACCESS_TOKEN:-floci-gcp-local-token}"

if command -v terraform >/dev/null 2>&1; then
  IAC="terraform"
elif command -v tofu >/dev/null 2>&1; then
  IAC="tofu"
else
  echo "ERROR: neither tofu nor terraform found" >&2
  exit 1
fi

cd "${INFRA_DIR}"

if [ -f "${INFRA_DIR}/terraform.tfstate" ]; then
  "${IAC}" init -input=false -no-color -upgrade=false 2>&1 | sed 's/^/[init] /' || \
    "${IAC}" init -input=false -no-color 2>&1 | sed 's/^/[init] /'
  "${IAC}" destroy -input=false -no-color -auto-approve 2>&1 | sed 's/^/[destroy] /'
else
  echo "[destroy] no terraform.tfstate found; nothing to tear down"
fi

echo "[destroy] complete"
