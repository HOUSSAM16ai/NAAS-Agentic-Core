# `chat_with_agent_endpoint` — Behavioral Archaeology (Phase 0)

> **Target:** `microservices/orchestrator_service/src/api/routes.py:903-1239` (`/agent/chat`)
> **Purpose:** know what the code *actually does* before touching a line. Every one of the
> 336 lines is assigned to a responsibility and a layer below — no orphan line.
> **Rule this document serves:** §6.6 — code presence ≠ runtime usage. A capability is real
> only with import + call chain + runtime evidence.
>
> **Status: this is the pre-surgery snapshot, kept as the record of what was measured.**
> All line numbers below refer to the code *before* D-237. The outcome:

| | before | after | budget |
|---|---|---|---|
| endpoint LOC | 336 | **39** | ≤ 40 |
| endpoint CC | 51 | **2** | ≤ 6 |
| endpoint nesting | 13 | **1** | ≤ 2 |
| `routes.py` LOC | 1,566 | **1,272** | — |

> Decision: `.memory/decisions.md` D-237 · ADR: `docs/adr/ADR-009-agent-chat-endpoint-decomposition.md`
> Enforced by: `scripts/fitness/check_endpoint_complexity.py` (guardrails job).
> Of the defects in §4: **4.1 fixed** (dead probes removed) · **4.3 fixed** (admin `query`)
> · **4.2 → ISS-153** · the empty-turn and raw-exception leaks → **ISS-154** · the WS twins
> → **ISS-155**. None were silently dropped.

---

## 1. Measured baseline

Measured with stdlib AST under `python3.12` (cyclomatic count over decision nodes:
`If/For/While/ExceptHandler/With/Assert/IfExp/comprehension`, plus `BoolOp` operands − 1).
The repo's own `type` statements do not parse under the container default 3.11, so 3.12 is
mandatory for any AST tooling here.

| Function | CC | LOC | Max nesting |
|---|---|---|---|
| **`chat_with_agent_endpoint` (L904)** | **51** | **336** | **13** |
| `admin_chat_ws_stategraph` (L728) | 23 | 153 | 5 |
| `chat_messages_endpoint` (L471) | 22 | 103 | 7 |
| `chat_ws_stategraph` (L577) | 20 | 148 | 5 |
| `stream_mission_ws` (L1318) | 20 | 88 | 5 |

`routes.py` total: **1,566 lines**. The endpoint alone is **21%** of the file.

CodeScene reports 336 LOC / complexity 48 / change frequency 43 for the same function. The
LOC agrees exactly; the complexity differs by 3 because CodeScene's metric is not identical
to ours. **We gate on our own number**, so the gate can never disagree with itself.

---

## 2. Runtime status — PARTIAL, not ACTIVE

| Leg of the proof | Evidence |
|---|---|
| import | ✅ route registered, `routes.py:903` |
| call chain | ⚠️ **conditional only** — `app/infrastructure/clients/routing_policy.py:21-26` maps `"agent" → /agent/chat`, and `_DEFAULT_ENDPOINT_MODE = "state_graph"` |
| runtime evidence | ❌ no deployment sets `ORCHESTRATOR_CHAT_ENDPOINT=agent`: `.devcontainer/supervisor.sh:551` and `:1450` and `scripts/e2e_up.sh:17` all pin `state_graph` |

Corroborated by `.memory/runtime_truth.md:694`. By the §6.6 legend this is **PARTIAL** —
"on a live chain but only via fallback, conditional, or non-default branch."

**Consequence for this work:** decomposing this endpoint buys code health and a safe,
cheap-to-change rollback lever. It does **not** change what a student receives by default,
because the default traverses `/api/chat/messages`. Stating otherwise would be the kind of
unfalsifiable claim D-227 forbids.

---

## 3. Responsibility map — 100% line coverage

Layer key: **API** = HTTP boundary · **APP** = application/workflow · **DOM** = domain policy ·
**INF** = infrastructure adapter · **PRE** = presentation/streaming · **ERR** = error translation ·
**X** = cross-cutting (logging/tracing).

### 3.1 Handler prologue — `L903-938` (36 lines)

| Lines | Responsibility | Layer |
|---|---|---|
| 903 | Route declaration `@router.post("/agent/chat")` | API |
| 904-908 | HTTP binding: body model, `Request`, `Authorization` header | API |
| 909-912 | Docstring | — |
| 914-915 | `extract_trace_context(fastapi_req)` | X |
| 917 | `_decode_auth_payload_or_401(authorization)` — authN, raises 401 | API + DOM |
| 918 | `request.user_id = user_id` — JWT identity overrides body (**security-critical**) | APP |
| 920 | Request log line (truncates question to 50 chars) | X |
| 923 | `context = request.context.copy()` | APP |
| 924-926 | Trace context injected into **both** `context` and `request.context` (aliasing) | X + APP |
| 927-933 | `context.update({user_id, conversation_id, history_messages})` | APP |
| 936 | `is_admin = _is_admin_payload(auth_payload)` — authZ from JWT, fail-closed | DOM |
| 938 | `is_compatibility_facade` — the §6.5 persistence-delegation handshake | DOM |
| 940 | `if is_admin:` — branch / agent selection | APP |

### 3.2 Admin generator `_admin_stream` — `L942-1130` (189 lines)

| Lines | Responsibility | Layer |
|---|---|---|
| 942 | Async generator declaration (nested closure — the nesting-13 root) | PRE |
| 943 | Outer `try` | ERR |
| 944-948 | Resolve `admin_app` from `app.state`; raise if absent | INF |
| 950-955 | Build admin payload; mutates `request.context` in place | DOM |
| 957-960 | `_augment_ambiguous_objective(question, history)` | APP |
| **963-974** | **DEAD SLICE** — see §4.1 | — |
| 975-978 | `_merge_admin_inputs` — admin state into graph inputs (D-171) | DOM |
| 980-984 | `conversation_id` (uuid4 fallback) — live | APP |
| 986-989 | `thread_id` — live, consumed at 993 | APP |
| 991-992 | `final_resp`, `admin_streamed_chars` accumulators (D-047) | APP |
| 993 | LangGraph `config` with `thread_id` | INF |
| 994-997 | LangSmith trace id into `config["metadata"]` | X |
| 999-1001 | `admin_app.astream_events(..., version="v2")` — execution | INF |
| 1002-1015 | `on_chain_start` → `phase_start` frame | PRE |
| 1016-1028 | `on_chat_model_stream` → `assistant_delta` (D-047) | PRE |
| 1029-1041 | `on_custom_event` → `assistant_delta` (D-048) | PRE |
| 1042-1054 | `on_chain_end` → `phase_completed` frame | PRE |
| 1055-1063 | Extract `final_response` / last message content | APP |
| 1065-1066 | `_extract_human_readable_response` — ISS-056 JSON-envelope anti-leak | APP |
| 1068-1069 | Bind user message / AI response for persistence | APP |
| 1070-1085 | `_ensure_conversation` + `_persist_assistant_message` (own session) | INF |
| 1086-1088 | `[DB SAVED]` marker frame | PRE |
| 1089-1091 | `_final_payload_content` — suppress duplicate when tokens streamed (D-047) | PRE |
| 1092-1099 | **`assistant_final` + `persisted: True`** — §6.5 contract | PRE + DOM |
| 1100-1107 | DB failure → `assistant_error` frame | ERR |
| 1108-1115 | **`assistant_final` + `persisted: False`** — Monolith must persist (§6.5) | PRE + DOM |
| 1116-1128 | Outer `except` → `request_id`, `logger.error`, `_safe_assistant_error` | ERR + X |
| 1130 | `return StreamingResponse(_admin_stream(), media_type="text/plain")` | API |

### 3.3 Customer path — `L1132-1239` (108 lines)

| Lines | Responsibility | Layer |
|---|---|---|
| 1132 | `get_ai_client()` | INF |
| 1133 | `OrchestratorAgent(ai_client, tool_registry)` — **not** LangGraph, by design (D-021) | INF + DOM |
| 1135 | Async generator declaration | PRE |
| 1136 | Outer `try` | ERR |
| 1137-1139 | `_augment_ambiguous_objective` | APP |
| **1142-1153** | **DEAD SLICE** — see §4.1 | — |
| 1154-1157 | `_build_graph_messages_manual` — history seeding | APP |
| 1159-1161 | `agent.run(...)` — execution | INF |
| 1162-1163 | `ai_chunks`, `final_chunk` accumulators | APP |
| 1164-1179 | Chunk loop, 4 shapes: `str` / `assistant_delta` / `assistant_final` / passthrough | PRE + APP |
| 1181-1183 | Join accumulated chunks | APP |
| 1184-1185 | `if full_ai_response:` + `orchestrator_persisted = False` | APP |
| 1186-1202 | `_ensure_conversation` + `_persist_assistant_message` (own session) | INF |
| 1203-1205 | `[DB SAVED]` marker frame | PRE |
| 1206-1213 | DB failure → `assistant_error` frame | ERR |
| 1214-1220 | **`assistant_final` + `persisted` flag** — §6.5 contract | PRE + DOM |
| 1221-1223 | `elif final_chunk:` → forward original, **no** persistence flag | PRE |
| 1225-1237 | Outer `except` → `request_id`, `logger.error`, `_safe_assistant_error` | ERR + X |
| 1239 | `return StreamingResponse(_stream_generator(), media_type="text/plain")` | API |

**Coverage check:** 903-938 (36) + 942-1130 (189) + 1132-1239 (108) + blank separators
= the full 903-1239 span. No orphan line.

---

## 4. Defects found (evidence, not opinion)

### 4.1 Two fully dead slices, each costing a live DB round-trip

Verified by AST, not by eye — reader/writer sets computed per generator:

```
_stream_generator:  conversation_id_fallback  written [1142]  read [1149]
                    thread_id                 written [1147]  read [1152]
                    _checkpointer_available   written [1151]  read []      ← never
                    _checkpoint_has_state     written [1151]  read []      ← never

_admin_stream:      conversation_id_fallback  written [963]   read [970]
                    thread_id                 written [968, 986]  read [973, 993]
                    _checkpointer_available   written [972]   read []      ← never
                    _checkpoint_has_state     written [972]   read []      ← never
```

The chain is single-use in both cases, so deadness is transitive:

- **Customer, `L1142-1153` (12 lines):** `conversation_id_fallback` → `thread_id` →
  `_detect_checkpoint_state(...)` → **result discarded**. Nothing else reads any of them.
- **Admin, `L963-974` (12 lines):** same chain. `thread_id`'s live value is the *second*
  write at `L986`, which is what `L993` consumes; the `L968` write feeds only the dead probe.

`_detect_checkpoint_state` (`chat_context.py:358-375`) is not free — it calls
`get_checkpointer()` and awaits `checkpointer.aget_tuple(...)` under `asyncio.timeout(1.5)`.
So every `/agent/chat` request pays a real checkpointer round-trip whose answer is thrown
away, and on failure emits a `[CHECKPOINTER] state probe failed` warning about a decision
that is never made.

**Why this is dead here but correct elsewhere:** the identical call at
`chat_stream_engine.py:484` *is* consumed — fed to `_build_graph_messages_graph(...,
checkpointer_available=..., checkpoint_has_state=...)`. That contrast is what proves the
`routes.py` copies vestigial rather than merely redundant.

Independently corroborated by `tests/unit/test_context_fragmentation.py:433`, which already
documents: "PROOF: مسار /agent/chat يستدعي agent.run() مباشرة بدون checkpointer" — the
endpoint has no checkpointer wiring at all, so the probe could never have influenced it.

**Disposition:** preserved verbatim through extraction, removed afterwards in its own
proven, revertible commit (Phase 3).

### 4.2 The `persisted` flag never reaches the wire — forbidden dual-write

**Severity: constitutional.** §6.5 makes `persisted` "the single source of truth for write
coordination" and §0 forbids dual writes outright. On this endpoint the flag is silently
discarded before it leaves the process.

Every frame is serialized by `_serialize_stream_frame_sync`
(`stream_serialization.py:104-110`), which does
`StreamFrame.model_validate(payload).model_dump()`. `StreamFrame` (`chat_types.py:68-72`)
declares **only** `type` and `payload` — so a top-level `persisted` key is dropped by
pydantic on validate and absent from the dump.

Verified live, not inferred:

```
in  -> {'type': 'assistant_final', 'payload': {'content': 'x'}, 'persisted': True}
out -> {"type": "assistant_final", "payload": {"content": "x"}}
persisted survives? False          # identical result for persisted=False
```

Consequence, following the monolith's own code:

1. `/agent/chat` **does** persist the assistant message (`L1080` admin, `L1196` customer).
2. It sets `persisted: True` (`L1097`, `L1218`) — stripped here.
3. `app/api/routers/customer_chat.py:525` — `if normalized_event.get("persisted") is True`
   never fires, so `orchestrator_persisted` stays `False`.
4. `customer_chat.py:643` — the monolith takes the `WRITE (Fail-Safe)` arm.

Result: **two assistant rows for one turn**, exactly the dual-write §6.5 exists to prevent.
§6.5 states the rule that makes it inevitable: "Absence of signal = failure."

Why the default path is unaffected: `_run_chat_langgraph` puts its extras *inside* `payload`
(`chat_stream_engine.py:579-601`) where `dict[str, object]` preserves them, and it never
persists — so the monolith's fail-safe write is the one and only write. The bug is specific
to the one path that both persists **and** signals at the top level.

⚠️ It therefore fires **only when the rollback lever is pulled** — i.e. during an incident,
which is the worst moment to start silently double-writing every student message.

**Note:** §6.5 cites `orchestrator_client.py:_normalize_stream_event` as the flag's
custodian. That symbol does not exist in that file (it lives in
`app/infrastructure/clients/orchestrator/turn_fallback.py`) — stale doc reference, D-188 class.

### 4.3 Admin graph receives no `query` — tool resolution on an empty string

`routes.py:975-978` builds admin inputs as `_merge_admin_inputs({"messages": [...]},
admin_payload)`. `_merge_admin_inputs` (`identity_access.py:86-93`) merges only
`_coerce_admin_state` → `{is_admin, user_role, scope}`. **No `query` key is ever set.**

But `microservices/orchestrator_service/src/services/overmind/graph/admin.py:128` decides
which tool to run with `resolve_tool_deterministic(state.get("query", ""))` — so on this
path it always resolves against `""`.

The contrast proves it is an omission, not a design: the StateGraph path sets it explicitly
— `chat_stream_engine.py:491`, `inputs = {"messages": graph_messages, "query": prepared_objective}`.

**This already has a failing test.** `test_agent_chat_admin_path_forwards_aligned_admin_state`
(`test_agent_chat_contract.py:119`) asserts `last_inputs["query"] == "count python files"`
and fails with `KeyError: 'query'`.

Red on main, proven structurally rather than assumed: `git diff origin/main..HEAD` over
`microservices/orchestrator_service/src/api/` **and** that test file is empty — byte-identical
code and byte-identical test. The branch's diff is entirely frontend + auth/error-contract
work (D-236/ISS-152). So this is a correct test failing against broken code, and it has been
failing unattended.

### 4.4 Duplicated persistence + terminal-frame block

`L1070-1115` (admin) and `L1186-1223` (customer) implement the same §6.5 contract —
ensure conversation → persist → `[DB SAVED]` → terminal frame carrying `persisted` — with
**deliberately different** failure behaviour: admin emits `assistant_final` in *both* the
success and failure arms; customer emits `[DB SAVED]` only on success and emits its terminal
frame after the try/except. Unifying them is a behaviour change, not a refactor.

**Disposition:** extracted as two distinct functions, **not** unified. Recorded as follow-up.

### 4.5 The trap that would silently gut the safety net

`tests/microservices/test_agent_chat_contract.py:29-31,77-79,136-138` patches
`routes._persist_assistant_message`, `routes._ensure_conversation`,
`routes._decode_auth_payload_or_401`. After extraction those names resolve against the new
module's globals, so the patches become **silent no-ops** and the tests would hit a real
database instead of failing loudly — D-168 permanent rule #1 (late binding: patch the module
where the *caller* lives).

Precedent for the fix is already in-tree:
`tests/microservices/test_orchestrator_chat_stategraph.py:145` patches
`chat_stream_engine._persist_assistant_message` while `:139` still patches
`routes._ensure_conversation`.

### 4.6 Source-inspection tests: checked, and they survive

`tests/infrastructure/test_d045_user_routing.py:194-231` reads `routes.py` **directly**
(not through `read_api_source()`) and asserts on literal strings. Occurrence counts in
`routes.py` today:

| String | Count | Also outside the target? |
|---|---|---|
| `assistant_final` | 7 | ✅ `L532,545,557` in `chat_messages_endpoint` |
| `conversation_init` | 2 | ✅ both in the WS handlers |
| `StreamingResponse` | 6 | ✅ |
| `_decode_auth_payload_or_401` | 7 | ✅ |

All four survive extraction. `test_d171_admin_state_via_graph.py:19,37` already reads through
`read_api_source()` and is immune by construction.

---

## 5. Dependency map

```
chat_with_agent_endpoint
├── extract_trace_context ................ core/tracing            [X]
├── _decode_auth_payload_or_401 .......... identity_access.py:217  [API+DOM]
├── _is_admin_payload .................... identity_access.py:62   [DOM]
├── admin branch
│   ├── fastapi_req.app.state.admin_app .. INF (shared mutable app state)
│   ├── _augment_ambiguous_objective ..... chat_context.py:308     [APP]
│   ├── _resolve_thread_id ............... identity_access.py:185  [APP]
│   ├── _detect_checkpoint_state ......... chat_context.py:358     [DEAD]
│   ├── _merge_admin_inputs .............. identity_access.py:86   [DOM]
│   ├── _serialize_stream_frame .......... stream_serialization.py:99  [PRE]
│   ├── _extract_human_readable_response . stream_serialization.py:59  [APP]
│   ├── _ensure_conversation ............. conversation_store.py:123   [INF]
│   ├── _persist_assistant_message ....... conversation_store.py:336   [INF]
│   ├── async_session_factory ............ INF (own session per call)
│   └── _safe_assistant_error ............ identity_access.py:125  [ERR]
└── customer branch
    ├── get_ai_client / OrchestratorAgent  INF
    ├── _build_graph_messages_manual ..... chat_context.py:147     [APP]
    └── (same persistence + serialization helpers as above)
```

**Shared mutable state:** `fastapi_req.app.state.admin_app` (read), `request.context`
(mutated in place at `L926` and `L951-952` — the `context` local is a *copy*, so these two
objects diverge after `L923`).

**No globals or singletons** are mutated by the endpoint. `get_ai_client()` returns the
shared gateway client; `tool_registry` is module-level and read-only here.

---

## 6. Fixture matrix for Phase 1

Every path the map above proves reachable:

| # | Case | Expected terminal contract |
|---|---|---|
| 1 | customer, tokens streamed | `assistant_final` + `persisted: true` |
| 2 | customer, no tokens, `final_chunk` present | forwarded chunk, **no** `persisted` key |
| 3 | customer, empty response, no `final_chunk` | no terminal frame from this arm |
| 4 | customer, persistence raises | `assistant_error` then `assistant_final` + `persisted: false` |
| 5 | customer, `agent.run` raises | single `assistant_error` with `request_id` |
| 6 | admin, tokens streamed | `assistant_final` content `""` + `persisted: true` (D-047) |
| 7 | admin, no tokens | `assistant_final` carrying full text + `persisted: true` |
| 8 | admin, `admin_app` missing | single `assistant_error` |
| 9 | admin, persistence raises | `assistant_error` then `assistant_final` + `persisted: false` |
| 10 | non-admin JWT + `chat_scope: admin` | customer path only — fail-closed |
| 11 | `compatibility_facade: true` | `skip_user_message=True` reaches `_ensure_conversation` |
| 12 | missing / invalid `Authorization` | 401 before any streaming begins |
| 13 | disconnect mid-stream | generator closed, no leaked tasks |

Cases 1, 6 and 10 are the only ones the existing 3 tests touch.
