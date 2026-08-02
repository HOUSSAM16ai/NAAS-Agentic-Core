# Runtime Rules (Observability Truth + Skills Philosophy)
> Last updated: 2026-05-11

---

## القواعد الأساسية (Observability Truth)

- Required proof triplet for any observability claim:
  1) Import anchor.
  2) Live call chain from kernel/router.
  3) Runtime evidence (metric/log/trace/CI artifact).
- Missing any leg => UNKNOWN.
- Classify each component: ACTIVE / PARTIAL / DORMANT / ZOMBIE / UNKNOWN.
- Treat OTel stack as PARTIAL by default unless OTLP endpoint + collector + backend signals are observed.
- Before merge: verify workflows `ci.yml`, `observability_validation.yml`, `runtime_truth.yml` are green and relevant telemetry fields still emitted.
- **Reasoning about Truth:** Future agents must inherit the discipline of verifying capabilities via the truth table (`.runtime/truth_table.lock.json`) rather than assuming aspirational architecture docs are real.
- **Uncertainty vs Evidence:** When there is uncertainty, do not synthesize or assume positive state. Default to UNKNOWN or DORMANT until explicit runtime evidence (logs, DB writes, metrics) proves otherwise. Always favor runtime evidence over documented claims.

---

## قواعد Skills Architecture (D-038 — إلزامية من 2026-05-11)

### تعريف Skill حقيقي
Skill حقيقي = **import + call chain + runtime evidence + metrics + tests**
أي Skill يفتقد واحداً من هذه الخمسة → DORMANT حتى يُثبت العكس.

### قواعد بناء Skill جديد (checklist إلزامي)
- [ ] `/health` يُعيد `{"status":"healthy","service":"...","step":"N"}`
- [ ] `/metrics` يُصدِّر `cogniforge_{skill}_startup_info{step="N"} 1.0`
- [ ] `prom_metrics.py` بـ `CollectorRegistry` مستقل — minimum 11 مقياساً
- [ ] `supervisor.sh:launch_{skill}()` — STEP 4X — idempotent
- [ ] `.ona/automations.yaml` — service + verify + restart + test tasks
- [ ] `observability/native/prometheus.yml` — scrape target + step label
- [ ] Grafana dashboard — minimum 15 panels + UID `cogniforge-ms-stepN-{skill}`
- [ ] CI gate — minimum 7 jobs + 79 اختباراً
- [ ] Fallback mode — يعمل بدون API key (mock responses, لا crash)
- [ ] Live verification قبل الـ commit — `/health` + `/metrics` حياً

### قوانين WebSocket Flapping — D-WS-FLAP-001 (2026-05-25)

**السبب الجذري للـ flapping:** `_emit_terminal_frames` تُستدعى في `finally` بدون `try/except` — إذا قطع العميل الاتصال أثناء البث، `send_json` يرمي `RuntimeError` يُسقط من `finally` ويُخرب الـ loop.

**القوانين الإلزامية:**
1. **كل `send_json` في `finally` يجب أن يكون داخل `try/except (WebSocketDisconnect, RuntimeError)`**
2. **كل `stream_and_forward` يجب أن تتحقق من `_ws_is_connected()` في بداية كل iteration**
3. **لا `await` ثقيل (DB/LLM) قبل بدء البث — استخدم `asyncio.create_task()`**
4. **Supabase + asyncpg = `pool_size=5, max_overflow=5` لا `NullPool`** — NullPool يُسبب connection exhaustion تراكمي

**التحقق الحي (2026-05-25):**
- 6 سيناريوهات: Customer 3 turns + mid-stream disc + Admin turn + Admin disc → **6/6 PASS**
- LLM يرد بالعربية، `persisted` يصل، reconnect فوري بدون flapping

---

### قواعد D-094 (2026-05-28 — لا تُكسر بدون ADR)

**D-094-BOOT — Bash nested function scope**:
```bash
# ❌ محظور: استدعاء دالة nested خارج نطاق الدالة الأم
_outer() { local env_file=".env"; _inner() { echo "$env_file"; } }
_outer
_inner  # ❌ env_file: unbound variable

# ✅ صحيح: sed مباشر أو دالة في النطاق العام
_tmp_f=".env"; sed -i "s|^KEY=.*|KEY=val|" "$_tmp_f"; unset _tmp_f
```

**D-094-DELTA — JavaScript array splice**:
```js
// ❌ محظور: قراءة عنصر بعد splice
const merged = arr.splice(0).reduce(...);
const base = arr[0] || {};  // دائماً undefined!

// ✅ صحيح: احفظ قبل splice
const base = arr[arr.length - 1] || {};
const merged = arr.splice(0).reduce(...);
```

**D-094-REQID — Terminal events يجب أن تُصفِّر activeRequestIdRef**:
```js
// كل terminal event في useAgentSocket.js يجب أن يبدأ بـ:
activeRequestIdRef.current = null;
// ينطبق على: assistant_final, complete, error, stream_end
```

### Anti-patterns محظورة (يُرفض الـ PR الذي يحتويها)
- **Prompt Spaghetti**: prompt واحد يحاول أكثر من مسؤولية واحدة
- **Direct Skill-to-Skill import**: `from microservices.planning_agent import ...` داخل `research_agent`
- **Skill بدون metrics**: `/metrics` endpoint غير موجود أو يُعيد `b""`
- **Skill بدون fallback**: يرفع exception عند غياب API key بدلاً من mock response
- **Import-time side effects**: إنشاء AI client عند import (ISS-039-B pattern)
- **Zombie metrics**: مقياس مُعرَّف في dashboard لكن لا emitter له في الكود

### قانون التركيب (Composition Law)
```
Skill A → orchestrator → Skill B   ✅ صحيح
Skill A → Skill B مباشرة           ❌ محظور (Constitution §5)
```

### قانون القياس (Measurement Law)
كل Skill يجب أن يُصدِّر على الأقل:
- `cogniforge_{skill}_requests_total{method,endpoint,status_code}`
- `cogniforge_{skill}_request_duration_seconds{method,endpoint}`
- `cogniforge_{skill}_invocations_total{action,status}`
- `cogniforge_{skill}_startup_info{step,version,environment,...}`

---

## قواعد بيئية مُرحَّلة من الدستور (D-188 · ISS-148 — 2026-08-02)

الأقسام الثلاثة أدناه كانت في `CLAUDE.md` §6، وهي **قواعد بيئية/مرحلية** لا قوانين
دائمة: واحدة تخصّ مُخطَّط أتمتة Ona، وواحدة تصف غياب Docker في devcontainer بعينه،
وثالثة تبدأ حرفياً بـ«after Step 4» — وهو الشكل الذي تمنعه قاعدة D-188 من العيش في
عقدٍ دائم، لأنه يتقادم ثمّ يكذب. نُقلت **حرفياً** بلا تعديل، ويشير إليها الدستور.

### NEVER add `dependsOn` to Ona automation services

```yaml
# ❌ Wrong — schema rejects it: additionalProperties: false
services:
  orchestrator-stack:
    dependsOn:
      - some-other-service  # FORBIDDEN in services

# ✅ Correct — use `ready` command to gate startup
services:
  orchestrator-stack:
    commands:
      ready: curl -sf http://localhost:8006/health
```

**Rule**: Only `tasks` support `dependsOn`. Services use the `ready` command as a readiness gate. A service stays in "Starting" phase until `ready` passes — this naturally gates any dependent workflow.

### NEVER try to use Docker in the default Codespaces devcontainer

```bash
# ❌ Wrong — Docker CLI not available in this devcontainer
docker compose -f docker-compose.step3.yml up -d
# Error: docker: not found

# ✅ Correct — orchestrator-service runs as a uvicorn process (Step 3)
# supervisor.sh starts it automatically at boot when OPENROUTER_API_KEY is set
# Manual restart:
gitpod automations service start orchestrator-service
# Or:
gitpod automations task start restart-orchestrator
```

**Why no Docker**: `devcontainer.json` intentionally omits `docker-in-docker` — it fails on `python:3.12-slim` + `network_mode: host` (Codespaces error 1302). The `docker-compose.step3.yml` file exists for future environments that support Docker (local dev, CI with DinD). In Codespaces, `supervisor.sh:launch_orchestrator_service()` is the canonical activation path.

### NEVER use a shared prometheus_client REGISTRY across monolith and orchestrator

```python
# ❌ Wrong — Step 4 lesson: using the default REGISTRY causes metric name collisions
# when both monolith and orchestrator run in the same process (tests, CI).
from prometheus_client import Counter
REQUESTS = Counter("cogniforge_requests_total", "...")  # registers in default REGISTRY

# ✅ Correct — use an independent CollectorRegistry per service
from prometheus_client import Counter, CollectorRegistry
_REGISTRY = CollectorRegistry()
REQUESTS = Counter("cogniforge_orchestrator_requests_total", "...", registry=_REGISTRY)
```

**Rule**: Every microservice that exposes `/metrics` must use its own `CollectorRegistry()`. Never import from `prometheus_client` without passing `registry=`. The monolith uses its own registry in `app/telemetry/`. The orchestrator uses `prom_metrics._REGISTRY`. They must never share.

### NEVER set OUTBOX_RELAY_ENABLED=false in production supervisor.sh after Step 4

```bash
# ❌ Wrong — Step 3 default, now obsolete after D-031 fulfilled in Step 4
OUTBOX_RELAY_ENABLED="false" \
nohup python -m uvicorn microservices.orchestrator_service.main:app ...

# ✅ Correct — Step 4 default (supervisor.sh and .ona/automations.yaml)
OUTBOX_RELAY_ENABLED="true" \
OUTBOX_RELAY_INTERVAL_SECONDS="15" \
OUTBOX_RELAY_BATCH_SIZE="50" \
nohup python -m uvicorn microservices.orchestrator_service.main:app ...
```

**Rule**: `OUTBOX_RELAY_ENABLED=false` was a Step 3 safety guard (D-031). Step 4 verified the persistence path — relay is now the default. Reverting to `false` silently disables event propagation without any error.
