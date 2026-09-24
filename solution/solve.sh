#!/usr/bin/env bash
set -Eeuo pipefail
unset TF_PLUGIN_CACHE_DIR

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="/workspace/submission"

mkdir -p "$TARGET_DIR/infra"
cp "$SOURCE_DIR/deploy.sh" "$TARGET_DIR/deploy.sh"
cp "$SOURCE_DIR/destroy.sh" "$TARGET_DIR/destroy.sh"
cp "$SOURCE_DIR/infra/"*.tf "$TARGET_DIR/infra/"
chmod +x "$TARGET_DIR/deploy.sh" "$TARGET_DIR/destroy.sh"

printf 'MediaPulse Ingest deployment copied to %s; starting deployment...\n' "$TARGET_DIR"
exec "$TARGET_DIR/deploy.sh"
