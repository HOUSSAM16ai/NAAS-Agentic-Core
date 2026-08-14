#!/usr/bin/env python3
"""Runtime Truth Generator — CogniForge / NAAS-Agentic-Core.

Re-derives the project's "runtime truth" by static analysis ONLY (no app
import, no network), then writes machine-readable artifacts under
`.runtime/` and compares against a committed lock file.

What it produces
----------------
* `.runtime/truth_table.json`   — current snapshot of every tracked component
* `.runtime/path_map.json`      — live WS / HTTP routes + their downstream chain
* `.runtime/snapshot.txt`       — human-readable summary (gitignored)
* `.runtime/truth_table.lock.json` — committed baseline; this script
                                     compares against it.

Why static-only
---------------
The project's strict rule (CLAUDE.md §6.6 closing rule):
> A capability counts as real ONLY when proven by import + call chain +
> runtime evidence.

We do NOT claim runtime evidence in CI — we measure the *static* slice
(import + call chain), and surface drift between the lock file (the
intentional snapshot) and the current tree.

Usage
-----
    python scripts/runtime_truth.py            # generate snapshot artifacts
    python scripts/runtime_truth.py --check    # CI mode: exit 1 on drift
    python scripts/runtime_truth.py --update   # rewrite the lock file

Exit codes
----------
    0 — no drift (or in non-check mode, artifacts written successfully)
    1 — drift detected vs lock file (only in --check mode)
    2 — internal error
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_DIR = REPO_ROOT / ".runtime"
LOCK_FILE = RUNTIME_DIR / "truth_table.lock.json"
TRUTH_FILE = RUNTIME_DIR / "truth_table.json"
PATH_MAP_FILE = RUNTIME_DIR / "path_map.json"
SNAPSHOT_FILE = RUNTIME_DIR / "snapshot.txt"

# Live entrypoints — the ONLY anchors a component can be reachable from.
LIVE_ANCHORS = (
    "app/main.py",
    "app/kernel.py",
    "app/api/routers/",
    "app/middleware/",
    "app/core/app_blueprint.py",
)


# ─── Component catalog ──────────────────────────────────────────────────────
# Mirrors `.memory/runtime_truth.md`. Adding/removing entries here is the
# explicit way to evolve the truth table. Drift between this list and the
# lock file is what the doc-integrity CI step will block.


@dataclass
class TrackedComponent:
    """One row of the runtime truth table."""

    id: str
    name: str
    files: list[str]
    expected_status: str  # ACTIVE | PARTIAL | DORMANT | ZOMBIE
    notes: str = ""
    importer_count: int = 0
    importers: list[str] = field(default_factory=list)
    on_live_chain: bool = False


CATALOG: list[TrackedComponent] = [
    TrackedComponent(
        id="local_graph",
        name="LangGraph local engine",
        files=["app/services/chat/local_graph.py"],
        expected_status="PARTIAL",
        notes=(
            "Pre-warmed at app/kernel.py; invoked by orchestrator_client fallback "
            "tier 3. Runs every turn in default Codespaces."
        ),
    ),
    TrackedComponent(
        id="path_observer",
        name="WS chat path observer",
        files=["app/telemetry/path_observer.py"],
        expected_status="ACTIVE",
        notes="Imported by customer_chat.py + admin.py at WS turn entry.",
    ),
    TrackedComponent(
        id="unified_observability",
        name="Unified Observability service",
        files=["app/telemetry/unified_observability.py"],
        expected_status="ACTIVE",
        notes="Wired into kernel startup; consumed by every HTTP request.",
    ),
    TrackedComponent(
        id="orchestrator_client",
        name="Orchestrator HTTP client + fallback chain",
        files=["app/infrastructure/clients/orchestrator_client.py"],
        expected_status="ACTIVE",
        notes="Sole entrypoint to chat from customer_chat.py and admin.py.",
    ),
    # D-173 (Stage 5): multi_agent_workflow + kagent_mesh removed — the ZOMBIE
    # cluster (KAgent mesh + multi-agent workflow + graph/nodes) was deleted.
    TrackedComponent(
        id="mcp_integrations",
        name="MCP integrations",
        files=["app/services/mcp/integrations.py"],
        expected_status="DORMANT",
        notes="Lazy-imported only by side-path agents not on the live chat router.",
    ),
    TrackedComponent(
        id="llamaindex_driver",
        name="LlamaIndex driver",
        files=["app/drivers/llamaindex_driver.py"],
        expected_status="ZOMBIE",
        notes="No live importer.",
    ),
    TrackedComponent(
        id="reranker_driver",
        name="Reranker driver (monolith)",
        files=["app/drivers/reranker_driver.py"],
        expected_status="ZOMBIE",
        notes="Driver registered only via dormant MCPIntegrations.",
    ),
    TrackedComponent(
        id="education_council",
        name="EducationCouncil",
        files=["app/services/chat/agents/education_council.py"],
        expected_status="ZOMBIE",
        notes="Only consumer is agents/orchestrator.py (also ZOMBIE).",
    ),
    TrackedComponent(
        id="orchestrator_support",
        name="OrchestratorSupport shards (D-253)",
        files=[
            "app/services/chat/agents/orchestrator_support/__init__.py",
            "app/services/chat/agents/orchestrator_support/_sources.py",
            "app/services/chat/agents/orchestrator_support/explanation.py",
            "app/services/chat/agents/orchestrator_support/search_params.py",
            "app/services/chat/agents/orchestrator_support/chat_fallback.py",
            "app/services/chat/agents/orchestrator_support/content_retrieval.py",
            "app/services/chat/agents/orchestrator_support/history_context.py",
        ],
        expected_status="ACTIVE",
        notes=(
            "D-253: turn-lifecycle shards extracted from agents/orchestrator.py; "
            "consumed by the orchestrator shell itself and its own test suite."
        ),
    ),
    TrackedComponent(
        id="boundary_customer",
        name="CustomerChatBoundaryService",
        files=["app/services/boundaries/customer_chat_boundary_service.py"],
        expected_status="PARTIAL",
        notes=(
            "Persistence methods ACTIVE; orchestrate_chat_stream/stream_chat "
            "never invoked from live router (loaded-not-invoked tier)."
        ),
    ),
    TrackedComponent(
        id="boundary_admin",
        name="AdminChatBoundaryService",
        files=["app/services/boundaries/admin_chat_boundary_service.py"],
        expected_status="PARTIAL",
        notes="Same shape as customer boundary.",
    ),
    TrackedComponent(
        id="customer_chat_router",
        name="Customer chat WS router",
        files=["app/api/routers/customer_chat.py"],
        expected_status="ACTIVE",
        notes="Live WS endpoint /api/chat/ws.",
    ),
    TrackedComponent(
        id="admin_chat_router",
        name="Admin chat WS router",
        files=["app/api/routers/admin.py"],
        expected_status="ACTIVE",
        notes="Live WS endpoint /admin/api/chat/ws.",
    ),
    TrackedComponent(
        id="otel_setup",
        name="OpenTelemetry SDK bootstrap",
        files=["app/telemetry/otel_setup.py"],
        expected_status="ACTIVE",
        notes=(
            "Imported by app/kernel.py at boot (setup_otel + instrument_fastapi_app). "
            "Hard no-op when OTEL_EXPORTER_OTLP_ENDPOINT is unset, so default Codespaces "
            "without the stack still boot. ACTIVE under §6.6 because the import + call "
            "chain are present at kernel startup; runtime evidence depends on the stack "
            "being up (validated separately by observability_validation CI)."
        ),
    ),
    TrackedComponent(
        id="grafana_stack_compose",
        name="Grafana observability stack (Docker compose)",
        files=["observability/docker-compose.observability.yml"],
        expected_status="DORMANT",
        notes=(
            "5-container stack (Grafana + Prometheus + Loki + Tempo + OTel collector). "
            "Auto-starts in Codespaces via .devcontainer/start_observability.sh (background, "
            "resource-guarded). DORMANT classification reflects the §6.6 rule: the stack "
            "is real code but lives outside the FastAPI process — runtime evidence requires "
            "the containers to be UP."
        ),
    ),
    TrackedComponent(
        id="observability_router_prometheus",
        name="Prometheus scrape endpoint on observability router",
        files=["app/api/routers/observability.py"],
        expected_status="ACTIVE",
        notes=(
            "GET /api/v1/observability/prometheus returns text/plain Prometheus exposition. "
            "Mounted via app/api/routers/registry.py; scraped by Prometheus job "
            "cogniforge-fastapi-direct every 15s when the stack is up."
        ),
    ),
]


def _grep_count(token: str, *, paths: list[str]) -> tuple[int, list[str]]:
    """Count importers of `token` under `paths`. Returns (count, sample-files).

    Uses ripgrep when available (Codespaces image ships it), falls back to
    grep -r. Output is bounded to keep the artifact small.
    """
    base_cmd = ["rg", "--files-with-matches", "--no-messages", token, *paths]
    try:
        proc = subprocess.run(
            base_cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False, timeout=30
        )
        if proc.returncode in (0, 1):
            files = sorted({line.strip() for line in proc.stdout.splitlines() if line.strip()})
            return len(files), files[:8]
    except FileNotFoundError:
        pass
    # grep fallback
    try:
        proc = subprocess.run(
            [
                "grep",
                "-rIl",
                "--include=*.py",
                token,
                *paths,
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        files = sorted({line.strip() for line in proc.stdout.splitlines() if line.strip()})
        return len(files), files[:8]
    except Exception:
        return 0, []


def _module_path(file_path: str) -> str:
    """`app/services/chat/local_graph.py` → `app.services.chat.local_graph`."""
    p = file_path
    if p.endswith(".py"):
        p = p[:-3]
    return p.replace("/", ".")


def measure_component(c: TrackedComponent) -> TrackedComponent:
    """Populate `importers`, `importer_count`, `on_live_chain`."""
    seen: set[str] = set()
    for fp in c.files:
        module = _module_path(fp)
        # importers under app/, microservices/, scripts/, tests/, frontend/ — but exclude self
        token = f"from {module}"
        _, files = _grep_count(
            token,
            paths=["app", "microservices", "scripts", "tests"],
        )
        for f in files:
            if f != fp:
                seen.add(f)
        # Also catch `import <module>` style
        _, files2 = _grep_count(
            f"import {module}",
            paths=["app", "microservices", "scripts", "tests"],
        )
        for f in files2:
            if f != fp:
                seen.add(f)

    importers = sorted(seen)
    c.importers = importers[:8]
    c.importer_count = len(importers)

    def _under_live_anchor(file_path: str) -> bool:
        return any(
            file_path.startswith(anchor) or file_path == anchor.rstrip("/")
            for anchor in LIVE_ANCHORS
        )

    # On live chain if (a) the component itself lives under a LIVE_ANCHOR (it
    # IS the entrypoint, e.g. routers / kernel / middleware), OR (b) at least
    # one importer file falls under a LIVE_ANCHOR.
    self_anchored = any(_under_live_anchor(fp) for fp in c.files)
    importer_anchored = any(_under_live_anchor(imp) for imp in importers)
    c.on_live_chain = self_anchored or importer_anchored
    return c


def derive_status(c: TrackedComponent) -> str:
    """Static-derived status. ACTIVE/PARTIAL is hand-asserted via expected_status
    because the live runtime path of a multi-step chain is not derivable from
    grep alone. We DO derive ZOMBIE objectively (importer_count == 0), EXCEPT
    when the component is intentionally DORMANT and lives outside Python
    (e.g. a docker-compose stack file has no Python importers but is still
    a real, intentional artifact)."""
    if c.importer_count == 0:
        # Trust the curator: a ZOMBIE/DORMANT label on a 0-importer component
        # is intentional (e.g. a YAML / config artifact). Otherwise default
        # to ZOMBIE.
        if c.expected_status in {"ZOMBIE", "DORMANT"}:
            return c.expected_status
        return "ZOMBIE"
    if not c.on_live_chain:
        # Has importers but none from a live anchor → DORMANT or ZOMBIE.
        # Keep the expected status if it acknowledges this.
        if c.expected_status in {"ZOMBIE", "DORMANT"}:
            return c.expected_status
        return "ZOMBIE"
    # On live chain — trust the curated expected_status.
    return c.expected_status


def collect_truth() -> dict:
    """Build the truth artifact dict."""
    rows: list[dict] = []
    for c in CATALOG:
        measured = measure_component(c)
        derived = derive_status(measured)
        rows.append(
            {
                "id": measured.id,
                "name": measured.name,
                "files": measured.files,
                "expected_status": measured.expected_status,
                "derived_status": derived,
                "agreed": derived == measured.expected_status,
                "importer_count": measured.importer_count,
                "importers_sample": measured.importers,
                "on_live_chain": measured.on_live_chain,
                "notes": measured.notes,
            }
        )
    return {
        "schema_version": 1,
        "generated_at_utc": dt.datetime.now(dt.UTC).isoformat(),
        "branch": _git_branch(),
        "components": rows,
    }


def collect_path_map() -> dict:
    """Build the live path map artifact."""
    routers_dir = REPO_ROOT / "app" / "api" / "routers"
    routes: list[dict] = []
    for py in sorted(routers_dir.rglob("*.py")):
        rel = py.relative_to(REPO_ROOT).as_posix()
        try:
            text = py.read_text(encoding="utf-8")
        except Exception:
            continue
        for m in re.finditer(
            r'@router\.(websocket|get|post|put|delete|patch)\("([^"]+)"',
            text,
        ):
            kind, path = m.group(1), m.group(2)
            routes.append(
                {
                    "method": kind.upper(),
                    "path": path,
                    "file": rel,
                }
            )
    # WS chat fallback chain (manually curated — single source of truth).
    ws_paths = [
        {
            "name": "customer_chat_ws",
            "endpoint": "/api/chat/ws",
            "file": "app/api/routers/customer_chat.py",
            "downstream_chain": [
                "app/telemetry/path_observer.py:open_ws_turn",
                "app/services/boundaries/customer_chat_boundary_service.py:save_message",
                "app/infrastructure/clients/orchestrator_client.py:chat_with_agent",
                "  → http(orchestrator-service)  [DORMANT in default Codespaces]",
                "  → fallback: file_intelligence",
                "  → fallback: exercise_retrieval",
                "  → fallback: local_graph (run_local_graph)",
                "  → fallback: local_general_chat",
                "app/api/routers/customer_chat.py:_emit_terminal_frames",
                "app/telemetry/path_observer.py:close_ws_turn",
            ],
            "path_types": ["educational", "general_chat", "fallback"],
        },
        {
            "name": "admin_chat_ws",
            "endpoint": "/admin/api/chat/ws",
            "file": "app/api/routers/admin.py",
            "downstream_chain": [
                "app/telemetry/path_observer.py:open_ws_turn",
                "app/services/boundaries/admin_chat_boundary_service.py:save_message",
                "app/infrastructure/clients/orchestrator_client.py:chat_with_agent",
                "app/api/routers/admin.py:_emit_terminal_frames",
                "app/telemetry/path_observer.py:close_ws_turn",
            ],
            "path_types": ["admin"],
        },
    ]
    return {
        "schema_version": 1,
        "generated_at_utc": dt.datetime.now(dt.UTC).isoformat(),
        "branch": _git_branch(),
        "http_routes_total": len(routes),
        "ws_chat_paths": ws_paths,
    }


def _git_branch() -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        return proc.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _stable_dump(obj: dict) -> str:
    """JSON dump with stable key ordering for diff-friendly artifacts."""
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _strip_volatile(snapshot: dict) -> dict:
    """Remove fields that change on every run before comparing to the lock."""
    clone = json.loads(json.dumps(snapshot))  # cheap deep-copy
    clone.pop("generated_at_utc", None)
    clone.pop("branch", None)
    return clone


def write_artifacts(truth: dict, path_map: dict) -> None:
    RUNTIME_DIR.mkdir(exist_ok=True)
    TRUTH_FILE.write_text(_stable_dump(truth), encoding="utf-8")
    PATH_MAP_FILE.write_text(_stable_dump(path_map), encoding="utf-8")

    lines: list[str] = []
    lines.append("# CogniForge — Runtime Snapshot")
    lines.append(f"Generated: {truth['generated_at_utc']}")
    lines.append(f"Branch: {truth['branch']}")
    lines.append("")
    lines.append("## Components")
    for row in truth["components"]:
        agreed = "✓" if row["agreed"] else "✗"
        lines.append(
            f"  [{agreed}] {row['id']:<26} expected={row['expected_status']:<7} "
            f"derived={row['derived_status']:<7} importers={row['importer_count']:>3} "
            f"live={'yes' if row['on_live_chain'] else 'no '}"
        )
    lines.append("")
    lines.append("## WS chat paths")
    for p in path_map["ws_chat_paths"]:
        lines.append(f"  {p['endpoint']}  ({p['name']})")
        for step in p["downstream_chain"]:
            lines.append(f"    → {step}")
        lines.append("")
    SNAPSHOT_FILE.write_text("\n".join(lines), encoding="utf-8")


def diff_against_lock(truth: dict) -> tuple[bool, list[str]]:
    """Return (drift_detected, diff_messages)."""
    if not LOCK_FILE.exists():
        return True, [
            f"No lock file at {LOCK_FILE.relative_to(REPO_ROOT)}.",
            "Run `python scripts/runtime_truth.py --update` to create the baseline.",
        ]
    try:
        locked = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        return True, [f"Failed to read lock file: {e}"]

    current = _strip_volatile(truth)
    baseline = _strip_volatile(locked)

    if current == baseline:
        return False, []

    msgs: list[str] = []
    locked_by_id = {row["id"]: row for row in baseline.get("components", [])}
    for row in current.get("components", []):
        rid = row["id"]
        if rid not in locked_by_id:
            msgs.append(f"NEW component (not in lock): {rid}")
            continue
        old = locked_by_id[rid]
        for k in ("expected_status", "derived_status", "on_live_chain"):
            if row.get(k) != old.get(k):
                msgs.append(f"{rid}: {k} {old.get(k)!r} → {row.get(k)!r}")
        if row.get("importer_count", 0) != old.get("importer_count", 0):
            msgs.append(
                f"{rid}: importer_count {old.get('importer_count')} → {row.get('importer_count')}"
            )
    locked_ids = set(locked_by_id.keys())
    current_ids = {row["id"] for row in current.get("components", [])}
    for missing in locked_ids - current_ids:
        msgs.append(f"REMOVED component (was in lock): {missing}")
    if not msgs:
        msgs.append("Lock-file structure differs but per-component diff is empty.")
    return True, msgs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="Fail on drift vs lock file (CI mode).")
    group.add_argument(
        "--update", action="store_true", help="Rewrite the lock file to match the current tree."
    )
    args = parser.parse_args(argv)

    try:
        truth = collect_truth()
        path_map = collect_path_map()
        write_artifacts(truth, path_map)
    except Exception as e:  # pragma: no cover
        print(f"runtime_truth: internal error: {e}", file=sys.stderr)
        return 2

    if args.update:
        LOCK_FILE.write_text(_stable_dump(truth), encoding="utf-8")
        print(f"✅ Lock file rewritten: {LOCK_FILE.relative_to(REPO_ROOT)}")
        return 0

    if args.check:
        drifted, msgs = diff_against_lock(truth)
        if drifted:
            print("❌ Runtime truth drift detected:")
            for m in msgs:
                print(f"   • {m}")
            print()
            print("If the change is intentional, regenerate the baseline with:")
            print("   python scripts/runtime_truth.py --update")
            return 1
        print("✅ Runtime truth matches lock file.")
        return 0

    print(f"✅ Wrote {TRUTH_FILE.relative_to(REPO_ROOT)}")
    print(f"✅ Wrote {PATH_MAP_FILE.relative_to(REPO_ROOT)}")
    print(f"✅ Wrote {SNAPSHOT_FILE.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


# Suppress ruff F401: importer of asdict (kept for future serialization use).
_ = asdict
