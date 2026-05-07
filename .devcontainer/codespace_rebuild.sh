#!/usr/bin/env bash
###############################################################################
# codespace_rebuild.sh — one-command Codespace rebuild
#
# Why this exists
# ---------------
# After pulling a branch that changes `.devcontainer/devcontainer.json` (e.g.
# adding the `docker-in-docker` feature), the Codespace must be REBUILT for
# the change to take effect. Three ways to trigger a rebuild:
#
#   1. VS Code shows an automatic notification when it detects the change
#      (sometimes only after a window reload). Click "Rebuild Container".
#   2. VS Code Command Palette (Ctrl+Shift+P) → "Codespaces: Rebuild Container".
#   3. THIS SCRIPT — runs `gh codespace rebuild` from the terminal.
#
# Use this script when (1) and (2) didn't surface the prompt, or you simply
# prefer one terminal command. It is interactive: confirms before rebuilding.
#
# After rebuild
# -------------
# * `docker-in-docker` feature is installed → `docker` CLI works inside the
#   devcontainer.
# * `setup.sh` re-runs (postCreateCommand), pre-pulls the observability images.
# * `on-start.sh` re-runs, launching the supervisor + the obs stack.
# * Mission Control (port 3001) opens automatically — same UX as 3000/8000.
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
if ! command -v docker >/dev/null 2>&1; then
    needs_rebuild_reasons+=("Docker CLI is missing — devcontainer was built without 'docker-in-docker' feature.")
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
echo -e "  ${GREEN}✓${NC} Reinstalls all devcontainer features (docker-in-docker, node, github-cli, ...)"
echo -e "  ${GREEN}✓${NC} Re-runs setup.sh (postCreateCommand) — pre-pulls observability images"
echo -e "  ${GREEN}✓${NC} Re-runs on-start.sh — launches supervisor + observability stack"
echo -e "  ${GREEN}✓${NC} Mission Control (port 3001) opens automatically — same UX as 3000/8000"
echo ""

# ---- Cost reminder --------------------------------------------------------
echo -e "${YELLOW}${BOLD}This will:${NC}"
echo -e "  ${YELLOW}•${NC} Disconnect your current VS Code session for ~5–8 minutes"
echo -e "  ${YELLOW}•${NC} ${BOLD}PRESERVE${NC} all files in /workspaces/ (your code is safe)"
echo -e "  ${YELLOW}•${NC} ${BOLD}WIPE${NC} Docker volumes inside the devcontainer (none today, since Docker is missing)"
echo -e "  ${YELLOW}•${NC} Use ~50–100 MB of bandwidth for the new feature install"
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
