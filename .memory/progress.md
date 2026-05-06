# Progress — What Has Been Done
> Last updated: 2026-05-05

## ✅ Session: 2026-05-05 — Persistence Consolidation + Terminal-Event Guarantee + Markdown Cleanup

**Branch**: `claude/fix-persistence-consolidate-8X8LT`

### What Was Fixed
1. **ISS-014/015 (Dual-write & save authority)** — D-006 implemented as a hard
   contract in CLAUDE.md §6.5 + architecture test
   `tests/architecture/test_persistence_authority.py`. Monolith is sole writer;
   Orchestrator only persists when delegated and signals back via `persisted: true`.
2. **ISS-016 (Silent fallback failures)** — New `_emit_terminal_frames()` helper in
   both `customer_chat.py` and `admin.py` finally blocks. Exactly one terminal
   frame (assistant_final/error) per turn. `[CRITICAL_DATA_LOSS]` logging surfaces
   when fail-safe writes fail.
3. **ISS-017 (Terminal-event corruption)** — `normalize_streaming_event` now passes
   `complete`, `persisted`, `conversation_init` through unchanged when the unified
   envelope flag is on. Previously they were coerced to `assistant_delta` and the
   router's terminal-event detection silently broke.

### Files Touched
- `shared/chat_protocol/event_protocol.py` — pass-through for control events.
- `app/api/routers/customer_chat.py` — `_emit_terminal_frames` helper + finally restructure.
- `app/api/routers/admin.py` — `_emit_terminal_frames` helper + WRITE_DECISION logs + retry parity.
- `tests/architecture/test_persistence_authority.py` — new regression guard.
- `CLAUDE.md` — added §6.5 "Architecture Truth and Persistence Rules".
- `.memory/decisions.md` — D-006 marked IMPLEMENTED, D-009 added.
- `.memory/issues.md` — ISS-014/015/016/017 marked RESOLVED.

### Markdown Consolidation
Deleted ~38 legacy diagnosis/forensic markdown files at repo root. Their conclusions
already lived in `.memory/issues.md` and CLAUDE.md; the standalone files were
point-in-time snapshots that drift from reality. Kept canonical operational docs
(README, CHANGELOG, LICENSE, SECURITY, governance, ARCHITECTURE, AGENTS, ROADMAP,
LangGraph blueprint, replit.md, README_MIGRATIONS, scientific applications).

---

## ✅ Session: 2026-05-05 — Environment Documentation Correction

**Branch**: `claude/fix-duplicate-messages-nTEBj`
**Goal**: Correct the recorded runtime environment from Replit to GitHub Codespaces

### What Was Verified
- User confirmed they run the project via **GitHub Codespaces**, not Replit
- Inspected `.devcontainer/devcontainer.json` and `.devcontainer/docker-compose.host.yml`
- Confirmed devcontainer launches a single `web` container running `uvicorn app.main:app` via `.devcontainer/supervisor.sh`
- Confirmed microservices stack (`docker-compose.yml`) is **not** started by the devcontainer → orchestrator-service:8006 + 7 other services remain DORMANT exactly as documented for Replit
- Net effect on dual-write analysis: **identical to Replit** (Monolith is the sole writer; no dual-write physically possible without manually running the full microservices stack)

### What Was Updated
1. `CLAUDE.md` — sections 1, 6, 10, 13, 14 — Replit references replaced with Codespaces; added devcontainer paths and the explicit `docker compose -f docker-compose.yml up -d` escape hatch to wake microservices
2. `.memory/context.md` — Identity block now lists Codespaces, devcontainer file, supervisor script; env var table updated to reference Codespaces secrets and `OPENROUTER_SITE_URL`
3. `.memory/architecture.md` — Fallback 3 annotation now explains *why* the microservice is dormant (devcontainer scope)
4. `.memory/decisions.md` — D-001, D-002 reworded to be environment-agnostic with Codespaces as the concrete case
5. `.memory/issues.md` — ISS-001 fix instructions updated for Codespaces secrets; ISS-013 historical-vs-current framing
6. `.memory/tasks.md` — task #2 (SECRET_KEY) and task #8 (microservice DNS) updated for Codespaces context
7. `.memory/progress.md` — this entry
8. `.memory/logs.md` — session log entry

---

## Completed
- Delivered a full architectural dissection summary in `CLAUDE.md`.
- Synchronized `.memory` architecture/context/decisions/issues to match the updated narrative.
- Preserved hybrid control-plane/execution-plane interpretation.
