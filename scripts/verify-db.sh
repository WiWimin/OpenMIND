#!/usr/bin/env bash
# Verify the OpenMIND development database stack.
#
# Checks, in order:
#   1. PostgreSQL readiness inside the `db` container
#   2. pgvector extension is installed (and its version)
#   3. the `vector` type is actually usable
#   4. Alembic schema is at head
#   5. backend health endpoint reports backend + database as up
#
# Exits non-zero on the first failure so it can be used in CI.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${ROOT_DIR}/docker/compose.dev.yml"
ENV_FILE="${ROOT_DIR}/docker/.env"
HEALTH_URL="${HEALTH_URL:-http://localhost:8000/api/v1/health/db}"

cd "${ROOT_DIR}"

if [ ! -f "${ENV_FILE}" ]; then
    echo "ERROR: ${ENV_FILE} not found. Copy docker/.env.example to docker/.env first." >&2
    exit 1
fi

# shellcheck disable=SC1090
set -a
. "${ENV_FILE}"
set +a

POSTGRES_USER="${POSTGRES_USER:-openmind}"
POSTGRES_DB="${POSTGRES_DB:-openmind}"

dc() {
    docker compose -f "${COMPOSE_FILE}" "$@"
}

fail() {
    echo "FAIL: $1" >&2
    exit 1
}

echo "== 1/5 PostgreSQL readiness =="
dc exec -T db pg_isready -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
    || fail "pg_isready returned non-zero"

echo "== 2/5 pgvector extension version =="
ext_version="$(dc exec -T db psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -tAc \
    "SELECT extversion FROM pg_extension WHERE extname = 'vector';" | tr -d '[:space:]')"
[ -n "${ext_version}" ] || fail "pgvector extension is not enabled in database '${POSTGRES_DB}'"
echo "pgvector version: ${ext_version}"

echo "== 3/5 vector type usability =="
vector_probe="$(dc exec -T db psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -tAc \
    "SELECT '[1,2,3]'::vector;" | tr -d '[:space:]')"
[ "${vector_probe}" = "[1,2,3]" ] \
    || fail "vector type probe returned unexpected output: '${vector_probe}'"
echo "vector probe: ${vector_probe}"

echo "== 4/5 Alembic migration state =="
# Alembic writes INFO log lines to stdout alongside the revision listing.
# A revision line looks like `0002_enable_pgvector (head)`.
extract_revision() {
    grep -E '^[0-9A-Za-z_]+( \(head\))?$' | tail -n 1 | tr -d '[:space:]'
}
head_revision="$(dc exec -T backend alembic heads 2>/dev/null | extract_revision || true)"
current_revision="$(dc exec -T backend alembic current 2>/dev/null | extract_revision || true)"
[ -n "${head_revision}" ] || fail "could not determine the Alembic head revision"
echo "head: ${head_revision}"
echo "current: ${current_revision:-<none>}"
[ "${current_revision}" = "${head_revision}" ] \
    || fail "database is not at Alembic head. Run: docker compose -f docker/compose.dev.yml exec backend alembic upgrade head"

echo "== 5/5 backend database health endpoint =="
health_body="$(curl -sS --max-time 10 -w '\n%{http_code}' "${HEALTH_URL}" || true)"
health_code="$(echo "${health_body}" | tail -n 1)"
health_json="$(echo "${health_body}" | sed '$d')"
echo "HTTP ${health_code} ${HEALTH_URL}"
echo "body: ${health_json}"
[ "${health_code}" = "200" ] || fail "health endpoint returned HTTP ${health_code}, expected 200"
echo "${health_json}" | grep -q '"database":"up"' \
    || fail 'health endpoint did not report "database":"up"'

echo ""
echo "OK: all database checks passed."
