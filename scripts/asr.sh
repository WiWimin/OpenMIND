#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/docker/compose.dev.yml"
ENV_FILE="$REPO_ROOT/docker/.env"
FIXTURE="$REPO_ROOT/frontend/e2e/fixtures/sample-audio-zh.wav"

dotenv_value() {
    local name="$1"
    local default="$2"
    local from_process="${!name:-}"
    if [[ -n "$from_process" ]]; then
        printf '%s' "$from_process"
        return
    fi
    if [[ ! -f "$ENV_FILE" ]]; then
        printf '%s' "$default"
        return
    fi
    local value
    value="$(grep -E "^${name}=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- | tr -d '\r')"
    printf '%s' "${value:-$default}"
}

ASR_HOST_PORT="$(dotenv_value ASR_HOST_PORT 10096)"
FUNASR_MODEL="$(dotenv_value FUNASR_MODEL sensevoice)"
BASE_URL="http://127.0.0.1:${ASR_HOST_PORT}"

compose() {
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" --profile asr "$@"
}

health() {
    curl -fsS "${BASE_URL}/health" 2>/dev/null || true
}

wait_healthy() {
    local timeout_seconds="${1:-1200}"
    local deadline=$((SECONDS + timeout_seconds))
    while (( SECONDS < deadline )); do
        local body
        body="$(health)"
        if [[ "$body" == *'"status":"ok"'* ]]; then
            echo "FunASR is healthy: ${BASE_URL}/health"
            return 0
        fi
        sleep 5
    done
    echo "FunASR did not become healthy within ${timeout_seconds}s. Check: scripts/asr.sh logs" >&2
    return 1
}

recreate_backend() {
    ASR_API_BASE="http://asr:8000/v1" \
    ASR_API_KEY="local-dev" \
    ASR_MODEL="$FUNASR_MODEL" \
        docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --force-recreate backend
}

case "${1:-status}" in
    up)
        if [[ ! -f "$ENV_FILE" ]]; then
            echo "Missing $ENV_FILE; copy docker/.env.example to docker/.env first." >&2
            exit 1
        fi
        compose up -d --build asr
        wait_healthy
        if [[ "${NO_BACKEND_RECREATE:-0}" != "1" ]]; then
            recreate_backend
        fi
        echo "Local FunASR is ready; model=${FUNASR_MODEL}, endpoint=${BASE_URL}/v1"
        echo "To persist across a plain 'docker compose up', add to docker/.env:"
        echo "  ASR_API_BASE=http://asr:8000/v1"
        echo "  ASR_API_KEY=local-dev"
        echo "  ASR_MODEL=${FUNASR_MODEL}"
        ;;
    down)
        compose stop asr
        echo "FunASR stopped. Audio uploads fail until it is started again."
        ;;
    restart)
        compose restart asr
        wait_healthy
        ;;
    logs)
        compose logs -f asr
        ;;
    status)
        compose ps asr
        body="$(health)"
        if [[ -n "$body" ]]; then
            printf '%s\n' "$body"
        else
            echo "FunASR is not reachable at ${BASE_URL}/health" >&2
        fi
        ;;
    smoke)
        if [[ ! -f "$FIXTURE" ]]; then
            echo "Missing fixture: $FIXTURE" >&2
            exit 1
        fi
        curl -fsS -X POST "${BASE_URL}/v1/audio/transcriptions" \
            -F "file=@${FIXTURE}" \
            -F "model=${FUNASR_MODEL}"
        ;;
    *)
        echo "Usage: $0 {up|down|restart|status|logs|smoke}" >&2
        exit 1
        ;;
esac
