#!/bin/sh
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

docker run --rm --user root \
    -v "$repo_dir:/workspace:ro" \
    -w /workspace/services/notifications \
    -e PYTHONPATH=/workspace/services/notifications:/workspace \
    citizen-bridge-notifications:local sh -c \
    'pip install --no-cache-dir "ruff>=0.12,<1" >/tmp/pip.log && ruff check --no-cache /workspace/contracts/constants /workspace/contracts/lib /workspace/contracts/tests /workspace/services/auth/app /workspace/services/auth/tests /workspace/services/authority/app /workspace/services/authority/alembic/versions /workspace/services/authority/tests /workspace/services/case-engine/app /workspace/services/case-engine/alembic/versions /workspace/services/case-engine/tests /workspace/services/documents/app /workspace/services/documents/alembic/versions /workspace/services/documents/tests /workspace/services/notifications/app /workspace/services/notifications/alembic/versions /workspace/services/notifications/tests /workspace/services/ai/app /workspace/services/ai/alembic/versions /workspace/services/ai/tests /workspace/tests/integration'
