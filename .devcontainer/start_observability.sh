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
# In default Codespaces the `docker` CLI is INTENTIONALLY ABSENT. The
# `docker-in-docker` feature failed to build on `python:3.12-slim` +
# `network_mode: host` (Codespaces error 1302) and `docker-outside-of-docker`
# would build but the observability compose uses relative bind mounts that
# don't translate across the dev container ↔ VM filesystem boundary. Until
# we re-engineer the integration with workspace-path consistency, the
# observability STACK is DORMANT in default Codespaces — consistent with
# every other dormant capability per CLAUDE.md §6.6 / §6.16.
#
# The FastAPI app still exposes /api/v1/observability/prometheus on :8000
# so basic in-process telemetry is still scrapeable. Mission Control auto-
# start is parked until the integration is fixed.
loud_warn() {
    local msg="$1"
    echo "${msg}"
    echo "${msg}" >&2
    if [ -w "${REPO_ROOT}/.superhuman_bootstrap.log" ]; then
        printf "[start_observability.sh] %s\n" "${msg}" \
            >> "${REPO_ROOT}/.superhuman_bootstrap.log" 2>/dev/null || true
    fi
}

if ! command -v docker >/dev/null 2>&1; then
    echo "ℹ️  docker CLI is not available in this devcontainer."
    echo "   This is INTENTIONAL in the default Codespaces config (see CLAUDE.md §6.16)."
    echo "   The Grafana/Prometheus/Loki/Tempo stack is parked until Docker"
    echo "   integration is re-engineered with path-consistent compose mounts."
    echo ""
    echo "   In-process telemetry remains AVAILABLE at:"
    echo "     http://localhost:8000/api/v1/observability/prometheus  (Prometheus exposition)"
    echo "     http://localhost:8000/health                           (FastAPI health)"
    echo ""
    echo "   To wake the full observability stack manually (when running locally"
    echo "   with Docker installed): docker compose -f observability/docker-compose.observability.yml up -d"
    exit 0
fi

# ---- Wait for the Docker daemon to actually be ready ---------------------
# With docker-in-docker, the daemon takes 5–30s to come online after the
# container starts. We poll up to 60s. This is what makes the UX feel like
# 3000/8000 — by the time start_observability.sh proceeds, Docker IS ready.
wait_for_daemon() {
    local timeout=60
    local elapsed=0
    local interval=2
    while ! docker info >/dev/null 2>&1; do
        if [ "${elapsed}" -ge "${timeout}" ]; then
            loud_warn "❌ Docker daemon did not start within ${timeout}s."
            loud_warn "   Check: ps aux | grep dockerd  (the DinD feature should run it)"
            loud_warn "   Try : sudo service docker start"
            return 1
        fi
        sleep "${interval}"
        elapsed=$((elapsed + interval))
    done
    echo "✅ Docker daemon ready (waited ${elapsed}s)."
    return 0
}

if ! wait_for_daemon; then
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

# ---- CRITICAL: compute Grafana public URL for the active environment ------
# Without this, Grafana defaults to `domain=localhost` + `cookie_samesite=lax`
# from grafana.ini. In GitHub Codespaces the browser hits Grafana through the
# cross-origin preview proxy at https://<NAME>-3001.preview.app.github.dev/,
# and those defaults make the browser refuse the auth cookie → infinite
# redirect / blank panels / "you don't have access" loop.
#
# We export `GF_*` env vars here so the docker-compose service picks them up
# at container boot. These OVERRIDE the values in grafana.ini.
# -------------------------------------------------------------------------
detect_grafana_public_url() {
    # GitHub Codespaces injects CODESPACE_NAME and the preview domain.
    # Reference: https://docs.github.com/en/codespaces/developing-in-a-codespace/forwarding-ports-in-your-codespace
    if [ -n "${CODESPACE_NAME:-}" ] && [ -n "${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-}" ]; then
        echo "https://${CODESPACE_NAME}-3001.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}/"
        return 0
    fi
    if [ -n "${CODESPACE_NAME:-}" ]; then
        # Fallback if the port-forwarding domain env is missing (older images).
        echo "https://${CODESPACE_NAME}-3001.preview.app.github.dev/"
        return 0
    fi
    # Local / unknown environment — keep default.
    echo "http://localhost:3001/"
    return 0
}

GRAFANA_PUBLIC_URL="$(detect_grafana_public_url)"
export GRAFANA_PUBLIC_URL

if [[ "${GRAFANA_PUBLIC_URL}" == https://*.github.dev/* ]] || \
   [[ "${GRAFANA_PUBLIC_URL}" == https://*.preview.app.github.dev/* ]]; then
    # Codespaces: cross-origin proxy → SameSite=None + Secure are mandatory.
    export GF_SERVER_ROOT_URL="${GRAFANA_PUBLIC_URL}"
    export GF_SERVER_DOMAIN="$(echo "${GRAFANA_PUBLIC_URL}" | sed -E 's|^https?://([^/]+)/.*$|\1|')"
    export GF_SERVER_SERVE_FROM_SUB_PATH="false"
    export GF_SECURITY_COOKIE_SAMESITE="none"
    export GF_SECURITY_COOKIE_SECURE="true"
    export GF_SECURITY_CSRF_ALWAYS_CHECK="false"
    echo "🌐 Codespaces detected. Grafana wired to: ${GRAFANA_PUBLIC_URL}"
    echo "    GF_SERVER_DOMAIN          = ${GF_SERVER_DOMAIN}"
    echo "    GF_SECURITY_COOKIE_SAMESITE = none"
    echo "    GF_SECURITY_COOKIE_SECURE   = true"
    echo "    GF_SECURITY_CSRF_ALWAYS_CHECK = false"
else
    # Local / generic Linux. Default localhost wiring is correct; clear any
    # stale overrides so a previous Codespaces boot can't poison this run.
    unset GF_SERVER_ROOT_URL GF_SERVER_DOMAIN GF_SERVER_SERVE_FROM_SUB_PATH
    unset GF_SECURITY_COOKIE_SAMESITE GF_SECURITY_COOKIE_SECURE GF_SECURITY_CSRF_ALWAYS_CHECK
    echo "🏠 Local environment. Grafana on http://localhost:3001/."
fi

# Persist the resolved env so the next attach (without rebooting compose)
# can see what the active config is. Read-only debug aid.
{
    echo "# Generated by start_observability.sh @ $(date -u +%FT%TZ)"
    echo "GRAFANA_PUBLIC_URL=${GRAFANA_PUBLIC_URL}"
    [ -n "${GF_SERVER_ROOT_URL:-}" ]     && echo "GF_SERVER_ROOT_URL=${GF_SERVER_ROOT_URL}"
    [ -n "${GF_SERVER_DOMAIN:-}" ]       && echo "GF_SERVER_DOMAIN=${GF_SERVER_DOMAIN}"
    [ -n "${GF_SECURITY_COOKIE_SAMESITE:-}" ] && echo "GF_SECURITY_COOKIE_SAMESITE=${GF_SECURITY_COOKIE_SAMESITE}"
    [ -n "${GF_SECURITY_COOKIE_SECURE:-}" ]   && echo "GF_SECURITY_COOKIE_SECURE=${GF_SECURITY_COOKIE_SECURE}"
    [ -n "${GF_SECURITY_CSRF_ALWAYS_CHECK:-}" ] && echo "GF_SECURITY_CSRF_ALWAYS_CHECK=${GF_SECURITY_CSRF_ALWAYS_CHECK}"
} > "${STATE_DIR}/grafana.env" 2>/dev/null || true

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

# ---- Wait for Grafana to actually serve HTTP on :3001 --------------------
# VS Code's `onAutoForward: openBrowser` triggers when port 3001 transitions
# from not-listening to listening. We block here until Grafana's `/api/health`
# returns 200, so the moment this script exits, the browser auto-opens —
# exactly the same UX as port 3000 (Next.js) or 8000 (uvicorn).
wait_for_grafana() {
    local timeout=120
    local elapsed=0
    local interval=3
    echo "→ Waiting for Grafana on http://localhost:3001/api/health ..."
    while true; do
        if command -v curl >/dev/null 2>&1; then
            if curl -fsS -o /dev/null --max-time 2 "http://localhost:3001/api/health" 2>/dev/null; then
                echo "✅ Grafana healthy on :3001 (waited ${elapsed}s)."
                return 0
            fi
        elif command -v wget >/dev/null 2>&1; then
            if wget -q -O /dev/null --timeout=2 "http://localhost:3001/api/health" 2>/dev/null; then
                echo "✅ Grafana healthy on :3001 (waited ${elapsed}s)."
                return 0
            fi
        else
            # No HTTP client — fall back to TCP probe.
            if (echo > /dev/tcp/127.0.0.1/3001) >/dev/null 2>&1; then
                echo "✅ Grafana listening on :3001 (TCP probe, waited ${elapsed}s)."
                return 0
            fi
        fi
        if [ "${elapsed}" -ge "${timeout}" ]; then
            loud_warn "⚠️ Grafana did not become healthy within ${timeout}s."
            loud_warn "   Stack is still booting in background. Check:"
            loud_warn "     docker compose -f ${OBS_COMPOSE} --project-name cogniforge-obs ps"
            loud_warn "     docker logs cogniforge-grafana --tail=50"
            return 1
        fi
        sleep "${interval}"
        elapsed=$((elapsed + interval))
    done
}
wait_for_grafana || true

# ---- Friendly status snapshot --------------------------------------------
echo ""
echo "✅ Observability stack started."
echo ""
echo "   Mission Control (Grafana) : ${GRAFANA_PUBLIC_URL}"
echo "   Prometheus (host-local)   : http://localhost:9090/"
echo "   Tempo      (host-local)   : http://localhost:3200/"
echo "   Loki       (host-local)   : http://localhost:3100/"
echo "   OTel Collector (gRPC)     : localhost:4317"
echo "   OTel Collector (HTTP)     : http://localhost:4318/"
echo ""
echo "   Wire the FastAPI app  →  export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317"
echo ""

exit 0
