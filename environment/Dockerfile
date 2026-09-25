FROM --platform=linux/amd64 mirror.gcr.io/library/node:24-bookworm-slim@sha256:6f7b03f7c2c8e2e784dcf9295400527b9b1270fd37b7e9a7285cf83b6951452d AS toolchain

ARG TERRAFORM_VERSION=1.15.8
ARG OPENTOFU_VERSION=1.12.4
ARG GOOGLE_PROVIDER_VERSION=5.0.0

ENV DEBIAN_FRONTEND=noninteractive \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:/usr/local/bin:${PATH} \
    TF_CLI_CONFIG_FILE=/etc/terraformrc.offline \
    GOOGLE_CLOUD_PROJECT=mediapulse-dev \
    GCP_PROJECT_ID=mediapulse-dev \
    GCP_REGION=us-central1 \
    GCP_ENDPOINT_URL=http://gcp:4588 \
    GOOGLE_OAUTH_ACCESS_TOKEN=floci-gcp-local-token \
    PUBSUB_EMULATOR_HOST=gcp:4588 \
    FIRESTORE_EMULATOR_HOST=gcp:4588 \
    DATASTORE_EMULATOR_HOST=gcp:4588 \
    STORAGE_EMULATOR_HOST=http://gcp:4588 \
    SECRET_MANAGER_EMULATOR_HOST=gcp:4588 \
    FIREBASE_AUTH_EMULATOR_HOST=gcp:4588 \
    GOOGLE_COMPUTE_CUSTOM_ENDPOINT=http://gcp:4588/compute/v1/ \
    GOOGLE_STORAGE_CUSTOM_ENDPOINT=http://gcp:4588/storage/v1/ \
    GOOGLE_IAM_CUSTOM_ENDPOINT=http://gcp:4588/v1/ \
    GOOGLE_IAM_BETA_CUSTOM_ENDPOINT=http://gcp:4588/v1/ \
    GOOGLE_IAM_CREDENTIALS_CUSTOM_ENDPOINT=http://gcp:4588/v1/ \
    GOOGLE_PUBSUB_CUSTOM_ENDPOINT=http://gcp:4588/v1/ \
    GOOGLE_FIRESTORE_CUSTOM_ENDPOINT=http://gcp:4588/v1/ \
    GOOGLE_DATASTORE_CUSTOM_ENDPOINT=http://gcp:4588/v1/ \
    GOOGLE_SQL_CUSTOM_ENDPOINT=http://gcp:4588/sql/v1beta4/ \
    GOOGLE_CLOUD_RUN_CUSTOM_ENDPOINT=http://gcp:4588/run/v1/ \
    GOOGLE_CLOUD_RUN_V2_CUSTOM_ENDPOINT=http://gcp:4588/v2/ \
    GOOGLE_CLOUDFUNCTIONS2_CUSTOM_ENDPOINT=http://gcp:4588/v2/ \
    GOOGLE_CLOUD_SCHEDULER_CUSTOM_ENDPOINT=http://gcp:4588/v1/ \
    GOOGLE_CLOUD_TASKS_CUSTOM_ENDPOINT=http://gcp:4588/v2/ \
    GOOGLE_SECRET_MANAGER_CUSTOM_ENDPOINT=http://gcp:4588/v1/ \
    GOOGLE_KMS_CUSTOM_ENDPOINT=http://gcp:4588/v1/ \
    GOOGLE_LOGGING_CUSTOM_ENDPOINT=http://gcp:4588/v2/ \
    GOOGLE_MONITORING_CUSTOM_ENDPOINT=http://gcp:4588/v3/ \
    GOOGLE_BIG_QUERY_CUSTOM_ENDPOINT=http://gcp:4588/bigquery/v2/ \
    GOOGLE_BIGQUERY_CUSTOM_ENDPOINT=http://gcp:4588/bigquery/v2/ \
    GOOGLE_IDENTITY_PLATFORM_CUSTOM_ENDPOINT=http://gcp:4588/v2/ \
    GOOGLE_ARTIFACT_REGISTRY_CUSTOM_ENDPOINT=http://gcp:4588/v1/ \
    GOOGLE_RESOURCE_MANAGER_CUSTOM_ENDPOINT=http://gcp:4588/v1/ \
    GOOGLE_RESOURCE_MANAGER_V3_CUSTOM_ENDPOINT=http://gcp:4588/v3/ \
    GOOGLE_CLOUD_RESOURCE_MANAGER_CUSTOM_ENDPOINT=http://gcp:4588/v1/ \
    GOOGLE_SERVICE_USAGE_CUSTOM_ENDPOINT=http://gcp:4588/v1/ \
    GOOGLE_EVENTARC_CUSTOM_ENDPOINT=http://gcp:4588/v1/

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      bash ca-certificates curl wget unzip xz-utils \
      git patch jq ripgrep fd-find less file vim procps psmisc util-linux \
      python3 python3-venv python3-pip \
      postgresql-client redis-tools netcat-openbsd dnsutils \
 && rm -rf /var/lib/apt/lists/* \
 && ln -sf /usr/bin/fdfind /usr/local/bin/fd

RUN npm install -g opencode-ai@1.17.8

RUN python3 -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir \
      google-cloud-storage google-cloud-pubsub google-cloud-firestore google-cloud-datastore google-cloud-secret-manager \
      "psycopg[binary]" redis requests PyJWT cryptography jsonschema pyyaml pytest \
 && printf '%s\n' \
      '#!/usr/bin/env bash' \
      'if ! nc -z -w 1 172.20.0.1 18080 >/dev/null 2>&1; then' \
      '  unset HTTP_PROXY http_proxy HTTPS_PROXY https_proxy' \
      'fi' \
      'if [[ ! -f "${SSL_CERT_FILE:-/etc/daytona-netleash-ca.crt}" ]] || [[ ! -s "${SSL_CERT_FILE:-/etc/daytona-netleash-ca.crt}" ]]; then' \
      '  export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt' \
      '  export CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt' \
      '  export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt' \
      '  unset NODE_EXTRA_CA_CERTS' \
      'fi' \
      'exec /usr/local/bin/opencode "$@"' > /opt/venv/bin/opencode \
 && printf '%s\n' \
      '#!/usr/bin/env bash' \
      'if [[ "$*" == *"nvm-sh/nvm"* ]]; then' \
      '  echo "true"' \
      '  exit 0' \
      'fi' \
      'if ! nc -z -w 1 172.20.0.1 18080 >/dev/null 2>&1; then' \
      '  unset HTTP_PROXY http_proxy HTTPS_PROXY https_proxy' \
      'fi' \
      'if [[ ! -f "${CURL_CA_BUNDLE:-/etc/daytona-netleash-ca.crt}" ]] || [[ ! -s "${CURL_CA_BUNDLE:-/etc/daytona-netleash-ca.crt}" ]]; then' \
      '  export CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt' \
      '  export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt' \
      'fi' \
      'exec /usr/bin/curl "$@"' > /opt/venv/bin/curl \
 && printf '%s\n' \
      '#!/usr/bin/env bash' \
      'if [[ "$*" == *" -g "* ]] && [[ -x /usr/local/bin/opencode ]]; then' \
      '  exit 0' \
      'fi' \
      'if ! nc -z -w 1 172.20.0.1 18080 >/dev/null 2>&1; then' \
      '  unset HTTP_PROXY http_proxy HTTPS_PROXY https_proxy' \
      'fi' \
      'exec /usr/local/bin/npm "$@"' > /opt/venv/bin/npm \
 && printf '%s\n' \
      '#!/usr/bin/env bash' \
      'if [[ "$(id -u)" != "0" ]] || [[ "$*" == *"curl"* ]]; then' \
      '  exit 0' \
      'fi' \
      'exec /usr/bin/apt-get "$@"' > /opt/venv/bin/apt-get \
 && printf '%s\n' \
      '#!/usr/bin/env bash' \
      'unset TF_PLUGIN_CACHE_DIR' \
      'export GCE_METADATA_HOST="127.0.0.1:1"' \
      'export GCE_METADATA_ROOT="127.0.0.1:1"' \
      'export NO_GCE_CHECK="true"' \
      'if [[ "$*" != *"init"* ]]; then' \
      '  export HTTP_PROXY="${GCP_ENDPOINT_URL:-http://gcp:4588}"' \
      '  export HTTPS_PROXY="${GCP_ENDPOINT_URL:-http://gcp:4588}"' \
      '  export http_proxy="${GCP_ENDPOINT_URL:-http://gcp:4588}"' \
      '  export https_proxy="${GCP_ENDPOINT_URL:-http://gcp:4588}"' \
      '  export NO_PROXY="localhost,127.0.0.1,::1,runtime-setup,floci-gcp,gcp-gateway,gcp,floci"' \
      '  export no_proxy="localhost,127.0.0.1,::1,runtime-setup,floci-gcp,gcp-gateway,gcp,floci"' \
      'elif ! nc -z -w 1 172.20.0.1 18080 >/dev/null 2>&1; then' \
      '  unset HTTP_PROXY http_proxy HTTPS_PROXY https_proxy' \
      'fi' \
      'exec /usr/local/bin/terraform "$@"' > /opt/venv/bin/terraform \
 && printf '%s\n' \
      '#!/usr/bin/env bash' \
      'unset TF_PLUGIN_CACHE_DIR' \
      'export GCE_METADATA_HOST="127.0.0.1:1"' \
      'export GCE_METADATA_ROOT="127.0.0.1:1"' \
      'export NO_GCE_CHECK="true"' \
      'if [[ "$*" != *"init"* ]]; then' \
      '  export HTTP_PROXY="${GCP_ENDPOINT_URL:-http://gcp:4588}"' \
      '  export HTTPS_PROXY="${GCP_ENDPOINT_URL:-http://gcp:4588}"' \
      '  export http_proxy="${GCP_ENDPOINT_URL:-http://gcp:4588}"' \
      '  export https_proxy="${GCP_ENDPOINT_URL:-http://gcp:4588}"' \
      '  export NO_PROXY="localhost,127.0.0.1,::1,runtime-setup,floci-gcp,gcp-gateway,gcp,floci"' \
      '  export no_proxy="localhost,127.0.0.1,::1,runtime-setup,floci-gcp,gcp-gateway,gcp,floci"' \
      'elif ! nc -z -w 1 172.20.0.1 18080 >/dev/null 2>&1; then' \
      '  unset HTTP_PROXY http_proxy HTTPS_PROXY https_proxy' \
      'fi' \
      'exec /usr/local/bin/tofu "$@"' > /opt/venv/bin/tofu \
 && chmod +x /opt/venv/bin/opencode /opt/venv/bin/curl /opt/venv/bin/npm /opt/venv/bin/apt-get /opt/venv/bin/terraform /opt/venv/bin/tofu

RUN curl -fsSLo "/tmp/terraform_${TERRAFORM_VERSION}_linux_amd64.zip" \
      "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip" \
 && curl -fsSLo /tmp/terraform_SHA256SUMS \
      "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_SHA256SUMS" \
 && cd /tmp \
 && grep "terraform_${TERRAFORM_VERSION}_linux_amd64.zip" terraform_SHA256SUMS | sha256sum -c - \
 && unzip -q "terraform_${TERRAFORM_VERSION}_linux_amd64.zip" -d /usr/local/bin \
 && rm -f "/tmp/terraform_${TERRAFORM_VERSION}_linux_amd64.zip" /tmp/terraform_SHA256SUMS

RUN curl -fsSLo "/tmp/tofu_${OPENTOFU_VERSION}_linux_amd64.zip" \
      "https://github.com/opentofu/opentofu/releases/download/v${OPENTOFU_VERSION}/tofu_${OPENTOFU_VERSION}_linux_amd64.zip" \
 && curl -fsSLo /tmp/tofu_SHA256SUMS \
      "https://github.com/opentofu/opentofu/releases/download/v${OPENTOFU_VERSION}/tofu_${OPENTOFU_VERSION}_SHA256SUMS" \
 && cd /tmp \
 && grep "tofu_${OPENTOFU_VERSION}_linux_amd64.zip" tofu_SHA256SUMS | sha256sum -c - \
 && unzip -q "tofu_${OPENTOFU_VERSION}_linux_amd64.zip" -d /usr/local/bin \
 && rm -f "/tmp/tofu_${OPENTOFU_VERSION}_linux_amd64.zip" /tmp/tofu_SHA256SUMS

RUN mkdir -p /opt/terraform-plugin-cache /tmp/provider-seed \
 && printf '%s\n' \
      'terraform {' \
      '  required_providers {' \
      '    google = {' \
      '      source = "hashicorp/google"' \
      "      version = \">=${GOOGLE_PROVIDER_VERSION}\"" \
      '    }' \
      '    google-beta = {' \
      '      source = "hashicorp/google-beta"' \
      "      version = \">=${GOOGLE_PROVIDER_VERSION}\"" \
      '    }' \
      '    archive = { source = "hashicorp/archive" }' \
      '    null    = { source = "hashicorp/null" }' \
      '    random  = { source = "hashicorp/random" }' \
      '    local   = { source = "hashicorp/local" }' \
      '    time    = { source = "hashicorp/time" }' \
      '  }' \
      '}' > /tmp/provider-seed/main.tf \
 && TF_PLUGIN_CACHE_DIR=/opt/terraform-plugin-cache /usr/local/bin/terraform -chdir=/tmp/provider-seed init -backend=false -input=false \
 && rm -rf /tmp/provider-seed \
 && printf '%s\n' \
      'plugin_cache_dir = "/opt/terraform-plugin-cache"' \
      'disable_checkpoint = true' > /etc/terraformrc \
 && printf '%s\n' \
      'disable_checkpoint = true' \
      'provider_installation {' \
      '  filesystem_mirror {' \
      '    path    = "/opt/terraform-plugin-cache"' \
      '    include = ["registry.terraform.io/hashicorp/*"]' \
      '  }' \
      '  direct {' \
      '    exclude = ["registry.terraform.io/hashicorp/*"]' \
      '  }' \
      '}' > /etc/terraformrc.offline

FROM toolchain AS agent

COPY workspace/ /workspace/

RUN groupadd --gid 10001 agent \
 && useradd --uid 10001 --gid 10001 --create-home --shell /bin/bash agent \
 && mkdir -p /workspace/submission /workspace/evidence /workspace/config /artifacts /home/agent/.nvm /root/.nvm \
 && printf '%s\n' 'nvm() { return 0; }' 'export -f nvm' > /home/agent/.nvm/nvm.sh \
 && printf '%s\n' 'nvm() { return 0; }' 'export -f nvm' > /root/.nvm/nvm.sh \
 && chmod +x /home/agent/.nvm/nvm.sh /root/.nvm/nvm.sh \
 && chown -R agent:agent /workspace/submission /workspace/evidence /artifacts /home/agent \
 && chmod 0755 /workspace /workspace/config \
 && chmod -R a+rX /opt/terraform-plugin-cache

WORKDIR /workspace

USER agent
