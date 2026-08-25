#!/bin/sh
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

docker run --rm \
    -v "$repo_dir:/workspace:ro" \
    -w /workspace \
    -e PYTHONPATH=/workspace \
    citizen-bridge-auth:local python -m unittest discover -s contracts/tests -q
