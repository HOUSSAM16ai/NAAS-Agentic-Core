# Runtime Rules — Operational Invariants
> Last updated: 2026-05-06 | Branch: `claude/autonomous-runtime-observability-pjzY9` | Authority: this file overrides any conflicting aspirational doc.

## Closing rule (load-bearing)
A capability is real ONLY when proven by all three of:
1. **import** — reachable from `app/main.py`, `app/kernel.py`, `app/api/routers/*`, or `app/middleware/*`.
2. **call chain** — a live entrypoint actually invokes its public surface.
3. **runtime evidence** — logs, spans, metrics, or DB writes attributable to a real request.

Missing any one → `PARTIAL` / `DORMANT` / `ZOMBIE` / `UNKNOWN`. Never `ACTIVE`.

## Live WS chat invariants
- Exactly one `WsTurnSpan` per turn (`open_ws_turn` → `close_ws_turn`). Close lives next to `_emit_terminal_frames` in the per-turn `finally:`.
- Exactly one terminal frame per turn (`assistant_final` OR `error`). One `persisted` event after a real save.
- `path_observer` NEVER raises out of the live path. All tracing calls are wrapped.

## Path taxonomy (closed set)
`educational | general_chat | fallback | admin | unknown` — defined in `app/telemetry/path_observer.py:_VALID_PATHS`. New values require code change AND dashboard update.

## Persistence authority (D-006 — unchanged)
- Monolith owns `customer_messages` + `admin_messages`.
- Orchestrator microservice writes ONLY when `compatibility_facade=True` AND echoes `persisted: true`.
- Absence of signal = failure → fail-safe write with 2 retries → `[CRITICAL_DATA_LOSS]` log + terminal `error` if all retries fail.

## Observability authority
- `app/telemetry/unified_observability.py:UnifiedObservabilityService` is the single facade for tracing / metrics / logs.
- `ObservabilityMiddleware` is the only WS-aware tracer in the middleware stack today (still does NOT trace WS frames — ISS-005).
- New observability layers MUST be wired through `UnifiedObservabilityService`, not built in parallel.

## CI gates (mandatory pre-merge)
- `lint` → ruff
- `contracts` → gateway/provider parity
- `guardrails` → `ci_guardrails.py` + fitness checks
- `test` → pytest
- `doc-integrity` → `CLAUDE.md` + `.memory/*` integrity
- `runtime-truth-drift-check` → `scripts/runtime_truth.py --check` matches `.runtime/truth_table.lock.json`

## Things that MUST NOT change without an ADR
1. The user-message write at the WS entrypoint. Single writer.
2. `_emit_terminal_frames()` as the single terminal-frame emitter.
3. The `persisted` flag — never rename, type-cast, or normalize away.
4. The `path_observer.open_ws_turn / close_ws_turn` boundary. One open, one close, in the per-turn `finally:`.
5. The `.runtime/truth_table.lock.json` schema. Updates require running `--update` in the same PR.
6. Promoting any `ZOMBIE` / `DORMANT` to `ACTIVE` without the three-part proof.

## Adding a new tracked capability
1. Add a `TrackedComponent(...)` row to `CATALOG` in `scripts/runtime_truth.py`.
2. Run `python scripts/runtime_truth.py --update`.
3. Commit BOTH the script change and the regenerated `.runtime/truth_table.lock.json`.
4. Update `.memory/runtime_truth.md` (the canonical narrative table).
