# D-238 — Live full-stack evidence (2026-08-11)

> **This file is the run, not a summary of the run.** Every block below is captured
> output. §6.6's rule applies to evidence too: a claim without `import + call chain +
> runtime evidence` is not a capability, and a fix without a live before/after is not a fix.

## 0. What the environment actually was

| | |
|---|---|
| Database | **real PostgreSQL 16.13**, local cluster `16/main` on `:5432`, db `cogniforge` |
| Driver | `postgresql+asyncpg://` (never bare `postgresql://` — CLAUDE.md pitfall) |
| LLM | **real OpenRouter**, live key, real rate limits |
| Services | 10 uvicorn microservices + monolith + Next.js frontend = **11 processes** |
| Not available | Supabase egress (blocked, CLAUDE.md:68) · Docker daemon → the 28-service compose stack could not run |

Supabase being unreachable is why a **local** Postgres was used. It is not SQLite: the
orchestrator reports `checkpointer_backend: postgres`, so the postgres checkpointer path
was genuinely exercised.

## 1. Health, verbatim

```
:8000  {"application":"ok","database":"ok","version":"v4.1-root"}
:8001  {"service":"user-service","status":"ok","environment":"development"}
:8002  {"service":"planning-agent","status":"ok","database":"sqlite+aiosqlite:///./planning_agent.db"}
:8003  {"status":"healthy","service":"conversation-service","version":"2.0.0","step":"12","graph_ready":true,"ws_enabled":true}
:8006  {"status":"ok","service":"orchestrator-service","graph_ready":true,"startup_state":"ready","checkpointer_backend":"postgres"}
:8007  {"status":"healthy","service":"research-agent","step":"7","tavily_available":"false"}
:8008  {"status":"healthy","service":"reasoning-agent","step":"8","llm_backend":"openrouter","mcts_enabled":"true"}
:8009  {"status":"healthy","service":"content-retrieval-skill","step":"11","kb_files":0,"version":"1.0.0"}
:8010  {"status":"healthy","service":"foundations-service","step":"13","domains":[…8 domains…],"llm_backend":"none"}
:8011  {"status":"healthy","service":"notation-service","step":"14","registry_version":"1.0.0","symbols_loaded":11,"startup_state":"ready"}
:5000  HTTP 200  (Next.js proxy — "[Server] Gateway: http://127.0.0.1:8000")
```

Two honest notes, because a health line that is read too generously is worse than none:

- `planning-agent` reports **sqlite**, not the shared Postgres. It boots and answers, but it
  is not on the same store as the rest. Recorded, not hidden.
- `research-agent` reports `tavily_available:false` — no Tavily key here, so web search
  degrades. Also: it fails to boot at all until `langchain-community` is installed, which
  lives only in that service's own `requirements.txt`. Same missing dependency makes
  `check_openapi_parity` unrunnable in a bare venv.

## 2. RED — the bug, on the wire, before any fix

Same question, real student (`user_id=2`, registered through
`POST /api/v1/auth/register` and logged in for a production-issued JWT):

```json
{"type":"assistant_delta","payload":{"content":"{\"type\": \"assistant_delta\", \"payload\": {\"content\": \"\\u0627\\u0644\"}}\n"}}
{"type":"assistant_delta","payload":{"content":"{\"type\": \"assistant_delta\", \"payload\": {\"content\": \"\\u0627\\u062d\"}}\n"}}
```

```
الإطارات: 34 · مُرمَّزة مرّتين: 32
```

**32 of 34 frames** carried a whole frame inside `payload.content`.

## 3. RED — the database, before any fix

The half no frame assertion covers:

```sql
SELECT role, left(content,200) FROM customer_messages ORDER BY id DESC LIMIT 2;
```
```
assistant|{"type": "assistant_delta", "payload": {"content": "ال"}}
         {"type": "assistant_delta", "payload": {"content": "اح"}}
user|ما هو تعريف الاحتمال؟ أجب بجملة واحدة.
```

The student's stored history is the envelope, permanently. This is what made ISS-156 a data
defect rather than a rendering nuisance.

**A third bug surfaced in the same run** — the first attempt failed on a foreign key
(`user_id=7` did not exist), and the raw exception went to the wire:

```
🚨 **SYSTEM DB ERROR:** … ForeignKeyViolationError … [SQL: INSERT INTO customer_conversations …]
[parameters: ('ما هو تعريف الاحتمال؟ …', 7)]
```

SQL text and bound parameters delivered to a student. That is **ISS-154**, previously
recorded from fixture analysis and now confirmed live.

## 4. A verification failure worth keeping

The first post-fix run **still showed double encoding**. The code was correct; the process
was not:

```
orchestrator process started: 14:12
orchestrator.py     mtime:    14:20
```

The launcher saw `:8006` healthy and skipped the relaunch, so the "green" run had tested
stale code. Comparing process age against file mtime is what caught it.

**Rule earned:** a live proof that does not verify *what it is running* proves nothing. Kill
by pattern, confirm the port is `000`, relaunch, confirm the new start time — then test.

## 5. GREEN — after the fix, same stack, same question

```json
{"type": "assistant_delta", "payload": {"content": "ال"}}
{"type": "assistant_delta", "payload": {"content": "اح"}}
{"type": "assistant_delta", "payload": {"content": "تمال"}}
```
```
الإطارات: 36 · مُرمَّزة مرّتين: 0
```

Database, after:

```
assistant | منظومة Overmind: الاحتمال هو مقياس لمدى احتمال وقوع حدث ما، يُعبر عنه بنسبة أو عدد بين 0 و1.
user      | عرّف الاحتمال بجملة واحدة.
```

Both states coexist in one table, which is the cleanest possible before/after:

```sql
SELECT count(*) FILTER (WHERE content LIKE '{"type"%') AS poisoned, count(*) AS total
  FROM customer_messages WHERE role='assistant';
```
```
 poisoned | total
        2 |     9
```

The 2 poisoned rows are exactly the two RED-proof runs. **Every row written after the fix is
clean.**

## 6. GREEN — all three layers (`scripts/e2e_orchestrator_live.py`)

```
[2] DIRECT orchestrator  POST /api/chat/messages
    ok=true deltas=45 chars=122 terminal=assistant_final ttft=31.56s
    answer: الاحتمال هو مقياس لمدى احتمال حدوث حدث ما، يُعطى عادةً قيمة بين 0 و 1، …

[3] MONOLITH WS  :8000/api/chat/ws
    ok=true terminal=assistant_final
    frames: session_ready, conversation_init, ui_component, assistant_delta, assistant_final

[4] FRONTEND WS (proxy)  :5000/api/chat/ws
    ok=true deltas=19 terminal=assistant_final
    answer: الاحتمال هو مقياس لمدى احتمال وقوع حدث ما في تجربة عشوائية، …

== RESULT: direct=True monolith=True frontend=True ==
```

Layer [3] answers with the deterministic generative-UI path (`ui_component`, D-116) rather
than prose — expected for this question class, not a failure.

## 7. ISS-157 — the banned model, measured

`services/llm/client.py` hardcoded `nvidia/nemotron-3-nano-30b-a3b:free`, which D-067 bans
as PRIMARY. Same question, same stack, only the model default changed:

| | answer |
|---|---|
| **before** (banned model) | `الاحتمال هو مقياس عددي يحددهنّierseny اللاحق … ويقُدرُ values بين 0 و1 inclusive.` |
| **after** (`ActiveModels.PRIMARY`) | `الاحتمال هو مقياس لمدى احتمال وقوع حدث ما ضمن مجموعة النتائج الممكنة، يُعبر عنه عادةً بنسبة أو عددًا بين 0 و1.` |

Latin fragments before: `يحددهنّierseny`, `values`, `inclusive`. After: only `Overmind`,
the product's own name. This is the garbage signature D-067 describes, reproduced and then
removed by measurement rather than by argument.

## 8. Reproducing this

```bash
pg_ctlcluster 16 main start
psql -c "CREATE ROLE cogni LOGIN PASSWORD 'cogni' SUPERUSER;" && createdb -O cogni cogniforge
export DATABASE_URL="postgresql+asyncpg://cogni:cogni@127.0.0.1:5432/cogniforge"
export APP_DATABASE_URL="$DATABASE_URL" SECRET_KEY=… OPENROUTER_API_KEY=…
# monolith + 10 microservices + frontend, then:
python scripts/e2e_orchestrator_live.py "ما هو تعريف الاحتمال؟"
psql -c "SELECT role, left(content,120) FROM customer_messages ORDER BY id DESC LIMIT 4;"
```

**Why this is not a CI job.** It needs a real OpenRouter key and outbound network. Forcing
it into CI imports exactly the rate-limit flakiness that fails `test_routing.py` locally, and
an amber pipeline gets ignored. The laws it proved are instead enforced by
`check_no_double_encoded_frames` and `check_model_chain_parity`, which need neither
credentials nor network. Same split as D-172/D-204.
