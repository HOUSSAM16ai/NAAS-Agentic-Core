#!/usr/bin/env bash
###############################################################################
# start_observability.sh — boot the Grafana stack inside Codespaces / locally.
#
# Wiring path:
#   .devcontainer/devcontainer.json (postStartCommand)
#       → .devcontainer/on-start.sh
#           → THIS SCRIPT (background, non-blocking)
#
# Behavior summary
# ----------------
# * Default in Codespaces       : ON  (auto-starts after every container boot)
# * Default locally / unknown   : OFF (user must export OBSERVABILITY_AUTOSTART=1)
# * Resource guard              : refuses to start if available RAM < 1.5 GB
# * Idempotent                  : `docker compose up -d` is safe to re-run
# * Failure mode                : logs to .observability/boot.log, never blocks
# * Disable explicitly          : export OBSERVABILITY_AUTOSTART=0 before attach
#
# Once running, the Grafana UI is at:
#   http://localhost:3001    (port 3001 — forwarded as "Mission Control")
#
# OpenTelemetry collector is at:
#   localhost:4317 (gRPC) / localhost:4318 (HTTP)
#
# To wire the FastAPI app to it, add to your env:
#   export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
#   export OTEL_EXPORTER_OTLP_INSECURE=true
###############################################################################

set -uo pipefail

readonly REPO_ROOT="${REPO_ROOT:-/app}"
readonly OBS_DIR="${REPO_ROOT}/observability"
readonly OBS_COMPOSE="${OBS_DIR}/docker-compose.observability.yml"
readonly STATE_DIR="${REPO_ROOT}/.observability"
readonly BOOT_LOG="${STATE_DIR}/boot.log"
readonly LOCK_FILE="${STATE_DIR}/.boot.lock"

mkdir -p "${STATE_DIR}"
exec >>"${BOOT_LOG}" 2>&1

echo ""
echo "=== start_observability.sh @ $(date -u +%FT%TZ) ==="

# ---- Decide whether to auto-start ------------------------------------------
in_codespace="${CODESPACES:-false}"
autostart_default="0"
if [ "${in_codespace}" = "true" ]; then
    autostart_default="1"
fi
autostart="${OBSERVABILITY_AUTOSTART:-${autostart_default}}"

if [ "${autostart}" != "1" ]; then
    echo "Auto-start disabled (OBSERVABILITY_AUTOSTART=${autostart}). Skipping."
    echo "To enable:  export OBSERVABILITY_AUTOSTART=1  &&  bash ${BASH_SOURCE[0]}"
    exit 0
fi

# ---- Guard: docker available? ---------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
    echo "❌ docker not found — observability stack cannot start."
    exit 0
fi
if ! docker info >/dev/null 2>&1; then
    echo "❌ docker daemon unreachable — observability stack cannot start."
    exit 0
fi

# ---- Guard: compose file exists? ------------------------------------------
if [ ! -f "${OBS_COMPOSE}" ]; then
    echo "❌ Compose file missing: ${OBS_COMPOSE}"
    exit 0
fi

# ---- Guard: enough free RAM? (Codespace baseline is 4 GB) -----------------
free_mb=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo 2>/dev/null || echo "0")
if [ "${free_mb}" -gt 0 ] && [ "${free_mb}" -lt 1500 ]; then
    echo "⚠️  Only ${free_mb} MB free — refusing to start (need ≥ 1500 MB)."
    echo "    Wake the stack manually after closing other processes:"
    echo "      docker compose -f ${OBS_COMPOSE} up -d"
    exit 0
fi
echo "Memory: ${free_mb} MB available — OK."

# ---- Guard: another instance racing? --------------------------------------
if [ -f "${LOCK_FILE}" ]; then
    pid=$(cat "${LOCK_FILE}" 2>/dev/null || true)
    if [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null; then
        echo "Another start_observability.sh is already running (pid=${pid}). Skipping."
        exit 0
    fi
fi
echo "$$" > "${LOCK_FILE}"
trap 'rm -f "${LOCK_FILE}"' EXIT

# ---- Pull + up ------------------------------------------------------------
echo "→ docker compose pull (quiet) ..."
docker compose -f "${OBS_COMPOSE}" --project-name cogniforge-obs pull --quiet || true

echo "→ docker compose up -d ..."
if ! docker compose -f "${OBS_COMPOSE}" --project-name cogniforge-obs up -d --remove-orphans; then
    echo "❌ docker compose up failed."
    exit 0
fi

echo "→ services:"
docker compose -f "${OBS_COMPOSE}" --project-name cogniforge-obs ps --format "  {{.Name}}\t{{.Status}}" || true

# ---- Friendly status snapshot --------------------------------------------
echo ""
echo "✅ Observability stack started."
echo ""
echo "   Mission Control (Grafana) : http://localhost:3001/"
echo "   Prometheus               : http://localhost:9090/"
echo "   Tempo                    : http://localhost:3200/"
echo "   Loki                     : http://localhost:3100/"
echo "   OTel Collector (gRPC)    : localhost:4317"
echo "   OTel Collector (HTTP)    : http://localhost:4318/"
echo ""
echo "   Wire the FastAPI app  →  export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317"
echo ""

exit 0
