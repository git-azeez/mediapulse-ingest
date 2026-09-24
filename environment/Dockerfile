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
    PUBSUB_EMULATOR_HOST=gcp:4588 \
    FIRESTORE_EMULATOR_HOST=gcp:4588 \
    DATASTORE_EMULATOR_HOST=gcp:4588 \
    STORAGE_EMULATOR_HOST=http://gcp:4588 \
    SECRET_MANAGER_EMULATOR_HOST=gcp:4588 \
    FIREBASE_AUTH_EMULATOR_HOST=gcp:4588

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
      "psycopg[binary]" redis requests PyJWT cryptography jsonschema pyyaml pytest

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
      '  }' \
      '}' > /tmp/provider-seed/main.tf \
 && TF_PLUGIN_CACHE_DIR=/opt/terraform-plugin-cache terraform -chdir=/tmp/provider-seed init -backend=false -input=false \
 && rm -rf /tmp/provider-seed \
 && printf '%s\n' \
      'plugin_cache_dir = "/opt/terraform-plugin-cache"' \
      'disable_checkpoint = true' > /etc/terraformrc \
 && printf '%s\n' \
      'disable_checkpoint = true' \
      'provider_installation {' \
      '  filesystem_mirror {' \
      '    path    = "/opt/terraform-plugin-cache"' \
      '    include = ["registry.terraform.io/hashicorp/google", "registry.terraform.io/hashicorp/google-beta"]' \
      '  }' \
      '  direct {' \
      '    exclude = ["registry.terraform.io/hashicorp/google", "registry.terraform.io/hashicorp/google-beta"]' \
      '  }' \
      '}' > /etc/terraformrc.offline

FROM toolchain AS agent

COPY workspace/ /workspace/

RUN groupadd --gid 10001 agent \
 && useradd --uid 10001 --gid 10001 --create-home --shell /bin/bash agent \
 && mkdir -p /workspace/submission /workspace/evidence /workspace/config /artifacts \
 && chown -R agent:agent /workspace/submission /workspace/evidence /artifacts /home/agent \
 && chmod 0755 /workspace /workspace/config \
 && chmod -R a+rX /opt/terraform-plugin-cache

WORKDIR /workspace

USER agent
