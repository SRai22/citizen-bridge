#!/bin/sh
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
services=${*:-"auth authority case-engine catalog documents notifications"}

for service in $services; do
    image="citizen-bridge-$service:local"
    echo "==> Testing $service"
    docker run --rm --user root \
        -v "$repo_dir:/workspace:ro" \
        -w "/workspace/services/$service" \
        -e "PYTHONPATH=/workspace/services/$service:/workspace" \
        "$image" sh -c \
        'pip install --no-cache-dir "pytest>=8,<9" "pytest-asyncio>=0.24,<2" "httpx>=0.28,<1" "aiosqlite>=0.20,<1" >/tmp/pip.log && pytest -q -p no:cacheprovider'
done
