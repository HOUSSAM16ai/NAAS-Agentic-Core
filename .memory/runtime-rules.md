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
