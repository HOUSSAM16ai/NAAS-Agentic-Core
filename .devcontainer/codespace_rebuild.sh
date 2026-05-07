#!/usr/bin/env bash
###############################################################################
# codespace_rebuild.sh — one-command Codespace rebuild
#
# Why this exists
# ---------------
# After pulling a branch that changes the Dockerfile or .devcontainer/, the
# Codespace must be REBUILT for the change to take effect. Three ways to
# trigger a rebuild:
#
#   1. VS Code shows an automatic notification when it detects the change
#      (sometimes only after a window reload). Click "Rebuild Container".
#   2. VS Code Command Palette (Ctrl+Shift+P) → "Codespaces: Rebuild Container".
#   3. THIS SCRIPT — runs `gh codespace rebuild` from the terminal.
#
# Use this script when (1) and (2) didn't surface the prompt, or you simply
# prefer one terminal command. It is interactive: confirms before rebuilding.
#
# After rebuild (post-§6.17)
# --------------------------
# * Dockerfile bakes Grafana + Prometheus binaries into /opt/grafana and
#   /opt/prometheus. ~5-8 min for the first build, mostly image download.
# * supervisor.sh starts uvicorn + Next.js + Prometheus + Grafana as
#   background processes. Mission Control listens on port 3001.
# * Port 3001 auto-opens in the browser as soon as Grafana's /api/health
#   returns 200 — same UX as 3000/8000.
###############################################################################

set -uo pipefail

readonly CYAN='\033[0;36m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly RED='\033[0;31m'
readonly BOLD='\033[1m'
readonly NC='\033[0m'

echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║              CODESPACE REBUILD — One Command Wrapper             ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ---- Detect environment ---------------------------------------------------
if [ -z "${CODESPACE_NAME:-}" ]; then
    echo -e "${RED}❌ Not running inside a GitHub Codespace${NC}"
    echo "   This script only works inside a Codespace (CODESPACE_NAME env var unset)."
    echo "   For local dev containers: use VS Code Command Palette →"
    echo "   'Dev Containers: Rebuild Container'."
    exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
    echo -e "${RED}❌ gh CLI not found${NC}"
    echo "   Cannot rebuild from terminal without 'gh'. Use the VS Code"
    echo "   Command Palette instead: Ctrl+Shift+P → 'Codespaces: Rebuild Container'."
    exit 1
fi

# ---- Status report --------------------------------------------------------
echo -e "${BOLD}Codespace:${NC} ${CODESPACE_NAME}"
echo -e "${BOLD}Branch   :${NC} $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')"
echo -e "${BOLD}Commit   :${NC} $(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
echo ""

# ---- Detect why rebuild is needed -----------------------------------------
needs_rebuild_reasons=()
if [ ! -x /opt/grafana/bin/grafana-server ] || [ ! -x /opt/prometheus/prometheus ]; then
    needs_rebuild_reasons+=("Grafana / Prometheus native binaries missing — image was built before §6.17.")
fi

if [ ${#needs_rebuild_reasons[@]} -gt 0 ]; then
    echo -e "${YELLOW}${BOLD}Why rebuild is needed:${NC}"
    for reason in "${needs_rebuild_reasons[@]}"; do
        echo -e "  ${YELLOW}•${NC} ${reason}"
    done
    echo ""
fi

# ---- What rebuild does ----------------------------------------------------
echo -e "${BOLD}What rebuild does:${NC}"
echo -e "  ${GREEN}✓${NC} Bakes Grafana OSS + Prometheus binaries into /opt/grafana and /opt/prometheus"
echo -e "  ${GREEN}✓${NC} Re-runs setup.sh (postCreateCommand)"
echo -e "  ${GREEN}✓${NC} Re-runs on-start.sh → supervisor.sh launches uvicorn + Next.js + Mission Control"
echo -e "  ${GREEN}✓${NC} Mission Control (port 3001) opens automatically — same UX as 3000/8000"
echo ""

# ---- Cost reminder --------------------------------------------------------
echo -e "${YELLOW}${BOLD}This will:${NC}"
echo -e "  ${YELLOW}•${NC} Disconnect your current VS Code session for ~5–8 minutes"
echo -e "  ${YELLOW}•${NC} ${BOLD}PRESERVE${NC} all files in /workspaces/ (your code is safe)"
echo -e "  ${YELLOW}•${NC} Add ~350 MB to the image (Grafana ~270 MB + Prometheus ~80 MB)"
echo ""

# ---- Confirmation ---------------------------------------------------------
read -r -p "$(echo -e "${BOLD}Proceed with rebuild? [y/N] ${NC}")" answer
case "${answer,,}" in
    y|yes)
        echo ""
        echo -e "${CYAN}→ Triggering rebuild via gh CLI…${NC}"
        echo ""
        # gh codespace rebuild is the official command. It waits for the
        # rebuild to be queued, then exits. The actual rebuild happens
        # asynchronously; VS Code will reconnect automatically.
        if gh codespace rebuild --codespace "${CODESPACE_NAME}"; then
            echo ""
            echo -e "${GREEN}${BOLD}✅ Rebuild queued.${NC}"
            echo -e "${CYAN}   Your VS Code session will reconnect in ~5–8 minutes.${NC}"
            echo -e "${CYAN}   When it does, port 3001 will auto-open Mission Control.${NC}"
        else
            echo ""
            echo -e "${RED}${BOLD}❌ gh codespace rebuild failed.${NC}"
            echo -e "   Falling back: open VS Code Command Palette →"
            echo -e "   ${BOLD}'Codespaces: Rebuild Container'${NC}"
            exit 1
        fi
        ;;
    *)
        echo ""
        echo -e "${YELLOW}Cancelled.${NC} Run again when ready, or use the Command Palette."
        exit 0
        ;;
esac
