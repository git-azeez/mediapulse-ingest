#!/bin/sh
set -eu

application_dir="$(cd "$(dirname "$0")" && pwd)"
cd "$application_dir"

for target in api projector relay archiver
do
  case "$target" in
    api) failure_code=21 ;;
    projector) failure_code=22 ;;
    relay) failure_code=23 ;;
    archiver) failure_code=24 ;;
  esac
  if ! docker buildx bake --load "$target"
  then
    echo "Failed to build the $target image." >&2
    exit "$failure_code"
  fi
done

for image in \
  cinderrouter/api:1.0.0 \
  cinderrouter/projector:1.0.0 \
  cinderrouter/relay:1.0.0 \
  cinderrouter/archiver:1.0.0
do
  if ! docker image inspect "$image" >/dev/null
  then
    echo "Docker did not load $image." >&2
    exit 31
  fi
done
