#!/usr/bin/env bash
set -euo pipefail

echo "== backend =="
(cd backend && ruff check . && pytest)

echo "== frontend =="
(cd frontend && npm run typecheck && npm run lint && npm run test)
