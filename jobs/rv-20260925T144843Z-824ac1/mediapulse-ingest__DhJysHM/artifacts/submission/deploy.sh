#!/usr/bin/env bash
# MediaPulse Ingest - GCP deployment via Terraform/OpenTofu
# Idempotent: safe to re-run; recreates missing managed resources.
set -euo pipefail

SUB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="${SUB_DIR}/infra"
MANIFEST="${SUB_DIR}/manifest.json"
CONFIG="/workspace/config/config.json"
TF_PLUGIN_CACHE_DIR="/opt/terraform-plugin-cache"
export TF_PLUGIN_CACHE_DIR
export TF_IN_AUTOMATION=1
export TF_INPUT=0
export TF_LOG=ERROR
# Keep provider custom endpoints from the environment (already set) and ensure
# the local Floci-GCP project/endpoint are used by the gcloud-free tooling.
export GOOGLE_OAUTH_ACCESS_TOKEN="${GOOGLE_OAUTH_ACCESS_TOKEN:-floci-gcp-local-token}"

# Pick the IaC engine (prefer tofu, fall back to terraform).
if command -v terraform >/dev/null 2>&1; then
  IAC="terraform"
elif command -v tofu >/dev/null 2>&1; then
  IAC="tofu"
else
  echo "ERROR: neither tofu nor terraform found" >&2
  exit 1
fi

cd "${INFRA_DIR}"

# Initialise providers (uses cached plugins; offline-friendly).
"${IAC}" init -input=false -no-color -upgrade=false 2>&1 | sed 's/^/[init] /' || \
  "${IAC}" init -input=false -no-color 2>&1 | sed 's/^/[init] /'

# Apply (creates + reconciles all managed resources). Re-running is a no-op for
# unchanged resources and recreates any that the verifier deleted.
"${IAC}" apply -input=false -no-color -auto-approve 2>&1 | sed 's/^/[apply] /'

# Render the manifest from state outputs.
"${IAC}" output -json -no-color > "${INFRA_DIR}/outputs.json" 2>/dev/null

python3 - "${INFRA_DIR}/outputs.json" "${CONFIG}" "${MANIFEST}" <<'PYEOF'
import json, sys, os

outs_raw = open(sys.argv[1]).read()
outs = json.loads(outs_raw) if outs_raw.strip() else {}
def ov(k):
    return outs.get(k, {}).get("value")

cfg = json.load(open(sys.argv[2]))

def img(role, ref_key, id_key):
    return {
        "reference": cfg[ref_key],
        "image_id": cfg.get(id_key, ""),
    }

lb_url = ov("lb_url") or ""
cloud_run_uri = ov("cloud_run_service_uri") or ""

manifest = {
    "schema_version": 1,
    "prefix": ov("prefix"),
    "project_id": ov("project_id"),
    "region": ov("region"),
    "gcp_endpoint_url": ov("gcp_endpoint_url"),
    "approved_images": {
        "api":       img("api",       "api_image",       "api_image_id"),
        "processor": img("processor", "processor_image", "processor_image_id"),
        "relay":     img("relay",     "relay_image",     "relay_image_id"),
        "archiver":  img("archiver",  "archiver_image",  "archiver_image_id"),
    },
    "load_balancer": {
        "ip_address": ov("lb_ip"),
        "url": lb_url,
        "connect_url": ov("gcp_endpoint_url"),
        "forwarding_rule_id": ov("forwarding_rule_id"),
        "backend_service_id": ov("backend_service_id"),
        "serverless_neg_id": ov("serverless_neg_id"),
    },
    "cloud_run": {
        "service_id": ov("cloud_run_service_id"),
        "service_name": ov("cloud_run_service_name"),
        "service_uri": cloud_run_uri,
        "min_instance_count": ov("cloud_run_min_instance_count"),
        "max_instance_count": ov("cloud_run_max_instance_count"),
    },
    "database": {
        "instance_name": ov("db_instance_name"),
        "private_ip": ov("db_private_ip"),
        "port": ov("db_port"),
        "name": ov("db_name"),
        "secret_id": ov("db_secret_id"),
    },
    "messaging": {
        "topic_id": ov("topic_id"),
        "topic_name": ov("topic_name"),
        "subscription_id": ov("subscription_id"),
        "dlq_topic_id": ov("dlq_topic_id"),
        "dlq_subscription_id": ov("dlq_subscription_id"),
        "max_delivery_attempts": ov("max_delivery_attempts"),
        "rebuild_tasks_queue": ov("rebuild_tasks_queue"),
    },
    "projections": {
        "firestore_database": ov("firestore_database"),
        "collection": ov("firestore_collection"),
        "bigquery_dataset": ov("bigquery_dataset"),
    },
    "cache": {
        "engine": ov("cache_engine"),
        "datastore_namespace": ov("cache_datastore_namespace"),
        "emulator_host": ov("cache_emulator_host"),
    },
    "auth": {
        "tenant_id": ov("auth_tenant_id"),
        "resource_server_identifier": ov("auth_resource_server_identifier"),
        "issuer": ov("auth_issuer"),
        "jwks_url": ov("auth_jwks_url"),
        "token_endpoint": ov("auth_token_endpoint"),
        "read_client_email": ov("read_client_email"),
        "write_client_email": ov("write_client_email"),
        "admin_client_email": ov("admin_client_email"),
        "read_client_id": ov("read_client_email"),
        "write_client_id": ov("write_client_email"),
        "admin_client_id": ov("admin_client_email"),
        "read_client_secret": ov("read_client_secret"),
        "write_client_secret": ov("write_client_secret"),
        "admin_client_secret": ov("admin_client_secret"),
    },
    "workers": {
        "processor_id": ov("processor_id"),
        "relay_id": ov("relay_id"),
        "archiver_id": ov("archiver_id"),
    },
    "schedules": {
        "relay_job_name": ov("relay_job_name"),
        "archiver_job_name": ov("archiver_job_name"),
    },
    "audit": {
        "bucket": ov("audit_bucket"),
        "prefix": ov("audit_prefix"),
    },
    "network": {
        "vpc_id": ov("vpc_id"),
        "ingress_subnet_id": ov("ingress_subnet_id"),
        "private_subnet_id": ov("private_subnet_id"),
    },
    "iam": {
        "api_service_account": ov("api_service_account"),
        "processor_service_account": ov("processor_service_account"),
        "relay_service_account": ov("relay_service_account"),
        "archiver_service_account": ov("archiver_service_account"),
        "scheduler_service_account": ov("scheduler_service_account"),
    },
    "kms": {
        "keyring_id": ov("kms_keyring_id"),
        "database_key_id": ov("kms_database_key_id"),
        "messaging_key_id": ov("kms_messaging_key_id"),
        "projection_key_id": ov("kms_projection_key_id"),
        "audit_key_id": ov("kms_audit_key_id"),
    },
    "logs": {
        "api": ov("logs_api"),
        "processor": ov("logs_processor"),
        "relay": ov("logs_relay"),
        "archiver": ov("logs_archiver"),
    },
}

with open(sys.argv[3], "w") as f:
    json.dump(manifest, f, indent=2)
# Guard the 1 MiB manifest size limit.
sz = os.path.getsize(sys.argv[3])
if sz > 1024 * 1024:
    print(f"WARNING: manifest is {sz} bytes (>1MiB)", file=sys.stderr)
print(f"[manifest] written {sys.argv[3]} ({sz} bytes)")
PYEOF

# Wait until the API is ready through the Load Balancer / Cloud Run endpoint.
python3 - "${MANIFEST}" <<'PYEOF'
import json, sys, time, urllib.request, urllib.error
m = json.load(open(sys.argv[1]))
candidates = []
lb = m.get("load_balancer", {})
cr = m.get("cloud_run", {})
if lb.get("connect_url"): candidates.append(lb["connect_url"])
if lb.get("url"): candidates.append(lb["url"])
if cr.get("service_uri"): candidates.append(cr["service_uri"])
candidates = [c for c in candidates if c]
deadline = time.time() + 300
last = None
while time.time() < deadline:
    for base in candidates:
        url = base.rstrip("/") + "/health/ready"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "mediapulse-deploy"})
            with urllib.request.urlopen(req, timeout=10) as r:
                code = r.getcode()
                body = r.read(200)
            if code == 200:
                print(f"[ready] {url} -> 200 OK")
                sys.exit(0)
            last = f"{url} -> {code}"
        except urllib.error.HTTPError as e:
            last = f"{url} -> HTTP {e.code}"
        except Exception as e:
            last = f"{url} -> {type(e).__name__}: {e}"
    time.sleep(5)
print(f"[ready] NOT healthy within timeout. last={last}", file=sys.stderr)
sys.exit(1)
PYEOF
