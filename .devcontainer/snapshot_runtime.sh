#!/usr/bin/env bash
###############################################################################
# snapshot_runtime.sh - Runtime Truth Snapshot Hook
#
# Runs at every Codespace attach (and on-demand). Produces:
#   .runtime/truth_table.json   — current static truth state
#   .runtime/path_map.json      — live WS / HTTP route map
#   .runtime/snapshot.txt       — human-readable summary
#
# Compares against `.runtime/truth_table.lock.json` and prints a friendly
# warning on drift, but never fails — this hook is INFORMATIONAL only.
# CI is the enforcement layer (`.github/workflows/runtime_truth.yml`).
#
# Principles:
#   - Non-blocking: must not slow down attach by more than a few seconds
#   - Read-only: no DB or network calls; pure static analysis
#   - Idempotent: safe to run repeatedly
###############################################################################

set -Eeuo pipefail

APP_ROOT="${APP_ROOT:-/app}"

if [ ! -d "$APP_ROOT" ]; then
    # Fall back to repo root when not in the devcontainer image (e.g. local
    # macOS shell doing `bash .devcontainer/snapshot_runtime.sh`).
    APP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

cd "$APP_ROOT"

if [ ! -f "scripts/runtime_truth.py" ]; then
    echo "⚠️  snapshot_runtime: scripts/runtime_truth.py not found, skipping."
    exit 0
fi

# Generate fresh artifacts.
if ! python scripts/runtime_truth.py >/dev/null 2>&1; then
    echo "⚠️  snapshot_runtime: generator failed (non-blocking)."
    exit 0
fi

# Compare against lock — informational only at attach time.
if python scripts/runtime_truth.py --check >/dev/null 2>&1; then
    echo "✅ Runtime truth: matches lock file"
else
    echo "⚠️  Runtime truth: drift detected vs .runtime/truth_table.lock.json"
    echo "   Run:  python scripts/runtime_truth.py --check"
    echo "   Or update the baseline (intentional change):"
    echo "         python scripts/runtime_truth.py --update"
fi

# Cheap one-line counts so the developer sees real numbers at attach time.
if [ -f .runtime/snapshot.txt ]; then
    components=$(grep -c "^\s*\[" .runtime/snapshot.txt || true)
    active=$(grep -c "derived=ACTIVE" .runtime/snapshot.txt || true)
    zombie=$(grep -c "derived=ZOMBIE" .runtime/snapshot.txt || true)
    dormant=$(grep -c "derived=DORMANT" .runtime/snapshot.txt || true)
    echo "   tracked=$components  active=$active  dormant=$dormant  zombie=$zombie"
fi

exit 0
