#!/bin/sh
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_dir/frontend"

npm run lint
npm run typecheck
npm test
npm run build
