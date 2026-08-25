#!/bin/sh
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_dir"

cleanup() {
    docker compose -f docker-compose.test.yml down -v
}
trap cleanup EXIT INT TERM

if [ "${SKIP_BUILD:-false}" != "true" ]; then
    docker compose -f docker-compose.test.yml build --quiet
fi
if ! docker compose -f docker-compose.test.yml up -d --no-build; then
    docker compose -f docker-compose.test.yml ps -a
    docker compose -f docker-compose.test.yml logs --no-color --tail=100
    exit 1
fi
if ! pytest -q -p no:cacheprovider tests/integration; then
    docker compose -f docker-compose.test.yml logs --no-color --tail=100
    exit 1
fi
