FROM mirror.gcr.io/library/rust:1.88.0-bookworm@sha256:af306cfa71d987911a781c37b59d7d67d934f49684058f96cf72079c3626bfe0 AS build

RUN apt-get update \
    && apt-get install --yes --no-install-recommends clang cmake make perl pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY Cargo.toml Cargo.lock ./
COPY library ./library
COPY api ./api
COPY projector ./projector
COPY outbox-relay ./outbox-relay
COPY audit-archiver ./audit-archiver

RUN --mount=type=cache,target=/usr/local/cargo/registry,sharing=locked \
    --mount=type=cache,target=/usr/local/cargo/git,sharing=locked \
    --mount=type=cache,target=/build/target,sharing=locked \
    cargo build --jobs 1 --locked --release --workspace --bins \
    && mkdir -p /out \
    && cp target/release/api /out/api \
    && cp target/release/projector /out/projector \
    && cp target/release/outbox-relay /out/outbox-relay \
    && cp target/release/audit-archiver /out/audit-archiver

FROM mirror.gcr.io/library/docker:27.5.1-cli@sha256:851f91d241214e7c6db86513b270d58776379aacc5eb9c4a87e5b47115e3065c AS runtime-setup
WORKDIR /application
COPY --from=build /out ./bin
COPY Dockerfile.runtime docker-bake.hcl build.sh ./
