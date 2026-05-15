---
name: cogniforge-math-pipeline
description: >
  Diagnose, build, and repair the CogniForge Math Pipeline — the LangGraph 4-node
  StateGraph that handles BAC math questions. Use when: math responses are in wrong
  language (Russian/English mixed with Arabic), missing LaTeX or $$\boxed{}$$,
  no step-by-step structure, a new math question type needs adding, system prompts
  need updating, or the pipeline fails silently. Triggers on: "إجابات رياضيات كارثية",
  "خلط لغات", "بدون LaTeX", "بدون boxed", "نوع مسألة جديد", "math pipeline",
  "conversation_graph", "math_pipeline.py", "subject detection", "system prompt رياضيات",
  "pipeline لا يعمل", "تصنيف المسائل", "BAC math", "شرح رياضيات".
---

# CogniForge Math Pipeline

> **Law:** A math response is correct only when it contains Arabic text + LaTeX `$$...$$`
> + `$$\boxed{...}$$` + numbered steps. Anything less is a broken response.

---

## 1. Quick Diagnosis (30 seconds)

```bash
cd /workspaces/NAAS-Agentic-Core
export OPENROUTER_API_KEY="..."
export PYTHONPATH="/workspaces/NAAS-Agentic-Core"

# Test Math Pipeline directly
python3 -c "
import asyncio, sys
sys.path.insert(0, '.')
from microservices.conversation_service.src.math_pipeline import invoke_math_pipeline

async def test():
    r = await invoke_math_pipeline('احسب مشتق f(x) = x²·e^(3x)', 'diag-001')
    resp = r['final_response']
    print(f'type={r[\"math_type\"]} | chars={len(resp)} | boxed={\"boxed\" in resp}')
    ar = sum(1 for c in resp if \"\\u0600\" <= c <= \"\\u06ff\")
    bad = any(w in resp for w in ['We need', 'Must', 'это', 'что'])
    print(f'AR_chars={ar} | foreign_meta={bad}')
    print(resp[:400])

asyncio.run(test())
"
```

**Expected healthy output:**
- `type=derivative | chars>500 | boxed=True`
- `AR_chars > 200` (عربية كافية)
- `foreign_meta=False` (لا خلط لغات)
- يحتوي على `$$\boxed{...}$$`

---

## 2. Pipeline Architecture

```
ConversationGraph (3 nodes):
  intent_node → context_node → response_node
                     ↓
              subject detection
              (math/physics/chemistry/general)
                     ↓
         subject=="math" AND intent=="educational"?
                  YES ↓              NO ↓
           Math Pipeline        Direct LLM
           (4 nodes)         (system prompt)

Math Pipeline (4 nodes):
  problem_analysis_node   → تصنيف 11 نوع + أخطاء شائعة
  solution_strategy_node  → اختيار الاستراتيجية + تبرير
  step_by_step_node       → الحل الكامل 6 أقسام + LaTeX + $$\boxed{}$$
  verification_node       → تجميع + header مناسب
```

**Files:**
- `microservices/conversation_service/src/math_pipeline.py` — Math Pipeline
- `microservices/conversation_service/src/conversation_graph.py` — ConversationGraph + routing
- `microservices/conversation_service/main.py` — ChatResponse includes `subject`

---

## 3. Symptom → Root Cause → Fix

### إجابات بالروسية أو الإنجليزية

**Root cause:** system prompt لا يُطبِّق قاعدة اللغة بشكل صريح.

**Fix:** تحقق من `_BASE_RULES` في `math_pipeline.py`:
```python
_BASE_RULES = (
    "## قواعد اللغة — صارمة لا تُخرق\n"
    "- اكتب بالعربية الفصحى الواضحة فقط\n"
    "- لا تخلط مع الروسية أو الإنجليزية أو الفرنسية إلا للمصطلحات التقنية\n"
    ...
)
```
يجب أن يكون `_BASE_RULES` مُضمَّناً في **كل** system prompt.

---

### لا `$$\boxed{}$$` في الإجابة

**Root cause:** `step_by_step_node` لا يطلب `\boxed` صراحةً في الـ prompt.

**Fix:** تحقق من نهاية user_prompt في `step_by_step_node`:
```python
"يجب أن تنتهي بـ: $$\\boxed{النتيجة النهائية}$$"
```

---

### `foreign_meta=True` — النموذج يُعيد meta-text

**Root cause:** النموذج يُعيد وصفاً لما سيفعله بدلاً من الفعل. يحدث مع `verification_node` عند استخدام prompts معقدة.

**Fix:** بسِّط user_prompt — اطلب الأقسام مباشرة بدون شرح:
```python
user_prompt=(
    "اكتب الأقسام التالية بالعربية مباشرة:\n"
    "**✅ التحقق:**\n"
    "**🔭 التفسير:**\n"
    # لا تضف: "Must", "Should", "Provide", "output exactly"
)
```

---

### `math_type=general_math` لمسألة واضحة

**Root cause:** الـ pattern لا يُطابق — تعارض بين أنواع (مثلاً `محدد` يُطابق `حد`).

**Fix:** راجع ترتيب `_MATH_TYPES` — الأكثر تحديداً أولاً:
```python
_MATH_TYPES = {
    "differential_eq": [...],  # أولاً — الأطول
    "derivative": [...],
    "matrix": ["مصفوفة", "محدد المصفوفة"],  # "محدد المصفوفة" لا "محدد" وحده
    "limit": ["نهاية الدالة", "lim("],       # لا "حد" وحده
    ...
}
```

---

### Pipeline لا يُوجَّه إليه (يذهب للـ LLM المباشر)

**Root cause:** `subject` لا يُكتشف كـ `"math"` أو `intent` ليس `"educational"`.

**Debug:**
```python
from microservices.conversation_service.src.conversation_graph import (
    _detect_subject, _classify_intent
)
print(_detect_subject("احسب مشتق الدالة"))  # يجب: "math"
print(_classify_intent("احسب مشتق الدالة"))  # يجب: "educational"
```

**Fix:** أضف الـ pattern المفقود في `_SUBJECT_PATTERNS["math"]` أو `_INTENT_PATTERNS["educational"]`.

---

### `content=None` من النموذج (ISS-069)

**Root cause:** نموذج reasoning-only يضع الإجابة في `message.reasoning` لا `message.content`.

**Fix:** تحقق من `_call_openrouter` في `math_pipeline.py`:
```python
content = msg.get("content") or msg.get("reasoning") or ""
```
يجب أن يكون هذا الـ guard موجوداً. إذا لم يكن — أضفه.

---

## 4. Adding a New Math Type

لإضافة نوع مسألة جديد (مثلاً `trigonometry`):

**Step 1:** أضف في `_MATH_TYPES` (بترتيب صحيح — الأكثر تحديداً أولاً):
```python
"trigonometry": [
    "مثلثات", "جيب", "جتا", "ظل", "sin", "cos", "tan",
    "trigonométrie", "sinusoïde",
],
```

**Step 2:** أضف سياقاً تعليمياً في `_get_math_context`:
```python
"trigonometry": (
    "مسألة مثلثات — قوانين: sin²x + cos²x = 1، "
    "صيغ التحويل، المعادلات المثلثية، الدوائر المثلثية"
),
```

**Step 3:** أضف header في `verification_node`:
```python
"trigonometry": "📐 مسألة مثلثات",
```

**Step 4:** أضف اختباراً في `test_math_pipeline.py`:
```python
def test_trigonometry(self):
    assert _classify_math_type("احسب sin(30°)") == "trigonometry"
```

**Step 5:** شغِّل الاختبارات:
```bash
cd /workspaces/NAAS-Agentic-Core
PYTHONPATH=. python -m pytest tests/microservices/conversation_service/test_math_pipeline.py -v
```

---

## 5. Live Model Benchmark

قبل تغيير النموذج الافتراضي، شغِّل البنشمارك الحي:

```bash
cd /workspaces/NAAS-Agentic-Core
export OPENROUTER_API_KEY="..."
python3 -c "
import asyncio, httpx, time, os

SYSTEM = '''أنت أستاذ رياضيات. اكتب بالعربية فقط. LaTeX: \$\$...\$\$. النتيجة: \$\$\\\\boxed{...}\$\$'''
Q = 'اشرح مشتق f(x) = x²·e^(3x) خطوة بخطوة'

async def test(model):
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=25) as c:
            r = await c.post('https://openrouter.ai/api/v1/chat/completions',
                headers={'Authorization': f'Bearer {os.environ[\"OPENROUTER_API_KEY\"]}'},
                json={'model': model, 'messages': [
                    {'role': 'system', 'content': SYSTEM},
                    {'role': 'user', 'content': Q}
                ], 'max_tokens': 400})
            d = r.json()
            elapsed = time.time() - t0
            choices = d.get('choices', [])
            if choices:
                content = choices[0].get('message', {}).get('content', '') or ''
                ar = sum(1 for c in content if '\u0600' <= c <= '\u06ff')
                latex = '\$\$' in content or '\\\\[' in content
                bad = any(w in content for w in ['это', 'что', ' the ', ' is '])
                q = '✅' if ar > 50 and not bad else '⚠️'
                print(f'{q} {elapsed:.1f}s AR:{ar} LaTeX:{latex} | {model[:50]}')
            else:
                print(f'❌ {model[:50]}: {d.get(\"error\",{}).get(\"message\",\"?\")[:50]}')
    except Exception as e:
        print(f'💥 {model[:50]}: {e}')

async def main():
    models = [
        'nvidia/nemotron-3-nano-30b-a3b:free',
        'openai/gpt-oss-20b:free',
        'google/gemma-4-26b-a4b-it:free',
        'nvidia/nemotron-3-super-120b-a12b:free',
    ]
    await asyncio.gather(*[test(m) for m in models])

asyncio.run(main())
"
```

**Verified live (2026-05-15):**

| Model | TTFT | Arabic | LaTeX | Status |
|-------|------|--------|-------|--------|
| `nvidia/nemotron-3-nano-30b-a3b:free` | 2.4s | ✅ | ✅ | **PRIMARY** |
| `nvidia/nemotron-3-super-120b-a12b:free` | 10.3s | ✅ | ✅ | FALLBACK-1 |
| `openai/gpt-oss-120b:free` | 41.8s | ✅ | ✅ | FALLBACK-2 |
| `openai/gpt-oss-20b:free` | 10.4s | ✅ | ✅ | FALLBACK-3 |
| `google/gemma-4-26b-a4b-it:free` | 15.5s | ✅ | ✅ | FALLBACK-4 |

---

## 6. System Prompt Rules

Load `references/system-prompt-templates.md` for canonical templates.

**Mandatory elements in every math system prompt:**
1. قاعدة اللغة الصارمة: "اكتب بالعربية الفصحى فقط — لا تخلط مع الروسية أو الإنجليزية"
2. LaTeX rules: `$$...$$` للمعادلات، `\(...\)` للرموز المضمّنة
3. `$$\boxed{...}$$` للنتيجة النهائية
4. "ابدأ بـ لماذا قبل الحساب"
5. "لا تختصر — الطالب يحتاج كل التفاصيل"

**Anti-pattern — prompt يُسبب meta-text:**
```python
# ❌ خاطئ — يُسبب "We need to output..."
"Must follow format exactly. Provide verification. Output sections in order."

# ✅ صحيح — اطلب مباشرة
"اكتب الأقسام التالية بالعربية:\n**التحقق:**\n**التفسير:**"
```

---

## 7. Anti-Patterns (مُكتشَفة حياً)

Load `references/anti-patterns.md` for the full catalogue.

**Critical — never do these:**

| Anti-pattern | السبب | البديل |
|---|---|---|
| `google/gemini-2.0-flash-exp:free` في fallback | DEAD — No endpoints | `google/gemma-4-26b-a4b-it:free` |
| `meta-llama/llama-3.2-11b-vision-instruct:free` | DEAD — No endpoints | `openai/gpt-oss-20b:free` |
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` كـ PRIMARY | content=None مع system prompt | `nvidia/nemotron-3-nano-30b-a3b:free` |
| `inclusionai/ring-2.6-1t:free` | rate-limited دائماً على Novita | أي نموذج آخر |
| MCTS depth > 1 مع نماذج مجانية | 6+ LLM calls → rate limiting | `depth=1` دائماً |
| verification_node يستدعي LLM بـ prompt معقد | meta-text بدلاً من إجابة | بسِّط الـ prompt أو اجعله deterministic |
| `content=None` صامت | إجابات فارغة للطالب | `msg.get("content") or msg.get("reasoning") or ""` |

---

## 8. Run Tests

```bash
cd /workspaces/NAAS-Agentic-Core
PYTHONPATH=. python -m pytest \
  tests/microservices/conversation_service/test_math_pipeline.py \
  -v --tb=short
# Expected: 36 passed
```

---

## 9. Reference Files

- `references/system-prompt-templates.md` — قوالب system prompts الكاملة لكل نوع مسألة
- `references/anti-patterns.md` — كتالوج كامل للـ anti-patterns مع الأدلة الحية
- `references/math-types-registry.md` — سجل 11 نوع مسألة مع patterns + سياق تعليمي
