FROM --platform=linux/amd64 mirror.gcr.io/library/node:24-bookworm-slim@sha256:6f7b03f7c2c8e2e784dcf9295400527b9b1270fd37b7e9a7285cf83b6951452d AS verifier-base

ARG JSONSCHEMA_VERSION=4.25.1
ARG PYTEST_VERSION=8.4.1

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/tests \
    PATH=/opt/venv/bin:/usr/local/bin:${PATH} \
    GCP_ENDPOINT_URL=http://gcp:4588 \
    PUBSUB_EMULATOR_HOST=gcp:4588 \
    FIRESTORE_EMULATOR_HOST=gcp:4588 \
    DATASTORE_EMULATOR_HOST=gcp:4588 \
    STORAGE_EMULATOR_HOST=http://gcp:4588 \
    SECRET_MANAGER_EMULATOR_HOST=gcp:4588 \
    FIREBASE_AUTH_EMULATOR_HOST=gcp:4588

RUN apt-get update \
 && apt-get install -y --no-install-recommends bash ca-certificates curl jq python3 python3-venv python3-pip \
 && rm -rf /var/lib/apt/lists/* \
 && python3 -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir \
      google-cloud-storage google-cloud-pubsub google-cloud-firestore google-cloud-datastore google-cloud-secret-manager \
      boto3 botocore "psycopg[binary]" redis requests PyJWT cryptography pyyaml \
      "jsonschema[format-nongpl]==${JSONSCHEMA_VERSION}" \
      "pytest==${PYTEST_VERSION}"

FROM verifier-base AS verifier

COPY . /tests/
COPY runtime/manifest.schema.json /opt/cinderroute-verifier/contracts/manifest.schema.json

RUN groupadd --gid 10002 verifier \
 && useradd --uid 10002 --gid 10002 --create-home --shell /bin/bash verifier \
 && mkdir -p /logs/verifier /workspace/config /workspace/submission /workspace/evidence \
 && chown -R verifier:verifier /logs/verifier /workspace \
 && chmod +x /tests/test.sh

WORKDIR /tests

USER verifier

CMD ["sleep", "infinity"]

FROM --platform=linux/amd64 mirror.gcr.io/library/node:24-bookworm-slim@sha256:6f7b03f7c2c8e2e784dcf9295400527b9b1270fd37b7e9a7285cf83b6951452d AS runner-toolchain

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
    GCP_ENDPOINT_URL=http://gcp:4588

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      bash ca-certificates curl wget unzip xz-utils \
      git patch jq ripgrep fd-find less file vim procps psmisc util-linux \
      python3 python3-venv python3-pip \
      postgresql-client redis-tools netcat-openbsd dnsutils \
 && rm -rf /var/lib/apt/lists/* \
 && ln -sf /usr/bin/fdfind /usr/local/bin/fd

RUN python3 -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir \
      google-cloud-storage google-cloud-pubsub google-cloud-firestore google-cloud-datastore google-cloud-secret-manager \
      boto3 botocore "psycopg[binary]" redis requests \
      PyJWT cryptography jsonschema pyyaml pytest

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

FROM runner-toolchain AS runner

COPY runtime/runner.py /runner.py

RUN chmod 0555 /runner.py \
 && chmod -R a+rX /opt/terraform-plugin-cache

WORKDIR /

USER root

CMD ["python3", "/runner.py"]

FROM mirror.gcr.io/library/rust:1.88.0-bookworm@sha256:af306cfa71d987911a781c37b59d7d67d934f49684058f96cf72079c3626bfe0 AS application-build

RUN apt-get update \
 && apt-get install --yes --no-install-recommends clang cmake make perl pkg-config \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY application/Cargo.toml application/Cargo.lock ./
COPY application/library ./library
COPY application/api ./api
COPY application/projector ./projector
COPY application/outbox-relay ./outbox-relay
COPY application/audit-archiver ./audit-archiver

RUN --mount=type=cache,target=/usr/local/cargo/registry,sharing=locked \
    --mount=type=cache,target=/usr/local/cargo/git,sharing=locked \
    --mount=type=cache,target=/build/target,sharing=locked \
    cargo build --jobs 1 --release --workspace --bins \
 && mkdir -p /out \
 && cp target/release/api /out/api \
 && cp target/release/projector /out/projector \
 && cp target/release/outbox-relay /out/outbox-relay \
 && cp target/release/audit-archiver /out/audit-archiver

FROM mirror.gcr.io/library/docker:27.5.1-cli@sha256:851f91d241214e7c6db86513b270d58776379aacc5eb9c4a87e5b47115e3065c AS runtime-setup

WORKDIR /application
COPY --from=application-build /out ./bin
COPY application/Dockerfile.runtime application/docker-bake.hcl application/build.sh ./
COPY runtime/runtime.sh /runtime.sh
