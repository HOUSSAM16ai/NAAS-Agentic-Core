# Anti-Patterns Catalogue — CogniForge Math Pipeline

> كتالوج كامل للـ anti-patterns المُكتشَفة بالتجريب الحي.
> كل anti-pattern مُوثَّق بأدلة حية وتاريخ الاكتشاف.

---

## Table of Contents
1. [نماذج ميتة في fallback chain](#dead-models)
2. [نماذج reasoning-only كـ PRIMARY](#reasoning-only-primary)
3. [خلط اللغات في الإجابات](#language-mixing)
4. [meta-text بدلاً من إجابة](#meta-text)
5. [MCTS depth > 1 مع نماذج مجانية](#mcts-depth)
6. [content=None صامت](#content-none)
7. [تعارض patterns في تصنيف المسائل](#pattern-conflict)
8. [verification_node يستدعي LLM بـ prompt معقد](#verification-llm)

---

## 1. نماذج ميتة في fallback chain {#dead-models}

**المشكلة:** نماذج تظهر في قائمة OpenRouter لكنها ترجع `No endpoints found`.

**الأدلة الحية (2026-05-15):**
```
❌ google/gemini-2.0-flash-exp:free: No endpoints found
❌ meta-llama/llama-3.2-11b-vision-instruct:free: No endpoints found
❌ qwen/qwen3-next-80b-a3b-instruct:free: Provider returned error
❌ meta-llama/llama-3.3-70b-instruct:free: Provider returned error
```

**القاعدة:** لا تضع نموذجاً في fallback chain بدون اختباره حياً أولاً.

**الفحص:**
```bash
python3 -c "
import asyncio, httpx, os
async def check(model):
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post('https://openrouter.ai/api/v1/chat/completions',
            headers={'Authorization': f'Bearer {os.environ[\"OPENROUTER_API_KEY\"]}'},
            json={'model': model, 'messages': [{'role': 'user', 'content': 'test'}], 'max_tokens': 5})
        d = r.json()
        err = d.get('error', {}).get('message', '')
        print(f'{'✅' if d.get('choices') else '❌'} {model}: {err[:50]}')
asyncio.run(check('google/gemini-2.0-flash-exp:free'))
"
```

**النماذج الميتة المؤكدة (2026-05-15):**
- `google/gemini-2.0-flash-exp:free` → `google/gemma-4-26b-a4b-it:free`
- `meta-llama/llama-3.2-11b-vision-instruct:free` → `openai/gpt-oss-20b:free`
- `inclusionai/ring-2.6-1t:free` → rate-limited دائماً على Novita (ISS-068)

---

## 2. نماذج reasoning-only كـ PRIMARY {#reasoning-only-primary}

**المشكلة:** نماذج تنتهي بـ `:reasoning:free` تضع الإجابة في `message.reasoning` لا `message.content` عند وجود system prompt → `content=None` → إجابات فارغة.

**الأدلة الحية (ISS-069, 2026-05-15):**
```python
# nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free مع system prompt:
msg = {"content": None, "reasoning": "Okay, let's see..."}
# content=None → إجابة فارغة للطالب
```

**القاعدة:** أي نموذج ينتهي بـ `:reasoning:free` → اختبره قبل تعيينه PRIMARY:
```python
content = msg.get("content") or msg.get("reasoning") or ""
assert content and len(content) > 0, "BROKEN: content=None"
```

**النماذج المحظورة:**
- `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` — content=None مع system prompt
- أي نموذج ينتهي بـ `:reasoning:free` — اختبره أولاً

---

## 3. خلط اللغات في الإجابات {#language-mixing}

**المشكلة:** النموذج يخلط العربية بالروسية والإنجليزية مع context كبير أو system prompt ضعيف.

**الأدلة الحية (ISS-070, 2026-05-15):**
```
# nvidia/nemotron-3-nano-30b-a3b:free مع system prompt ضعيف:
"...поэтому нам нужно إيجاد related интеграл, чтобы получить面积..."
"...That's why we need to compute ∫sin²(x)dx before we can plug it..."
```

**السبب:** system prompt لا يُطبِّق قاعدة اللغة بشكل صريح وصارم.

**الإصلاح:** أضف في بداية كل system prompt:
```python
"## قواعد اللغة — صارمة لا تُخرق\n"
"- اكتب بالعربية الفصحى الواضحة فقط\n"
"- لا تخلط مع الروسية أو الإنجليزية أو الفرنسية إلا للمصطلحات التقنية\n"
```

**الفحص:**
```python
bad = any(w in response for w in ['это', 'что', 'для', ' the ', ' is ', ' are '])
assert not bad, "خلط لغات مكتشف"
```

---

## 4. meta-text بدلاً من إجابة {#meta-text}

**المشكلة:** النموذج يُعيد وصفاً لما سيفعله بدلاً من الفعل مباشرة.

**الأدلة الحية (ISS-070, 2026-05-15):**
```
# verification_node مع prompt معقد:
"We need to output exactly the sections in order, in Arabic, with LaTeX formatting..."
"Must follow format exactly. Provide verification maybe by differentiating..."
"So produce: ✅ التحقق من النتيجة: [...], with verification using..."
```

**السبب:** الـ prompt يستخدم كلمات تعليمية (`Must`, `Should`, `Provide`, `output exactly`) تُحفِّز النموذج على وصف المهمة بدلاً من تنفيذها.

**الإصلاح:**
```python
# ❌ خاطئ
"Must follow format exactly. Provide verification. Output sections in order."

# ✅ صحيح — اطلب مباشرة
"اكتب الأقسام التالية بالعربية:\n**التحقق:**\n**التفسير:**"
```

**القاعدة:** إذا كان الـ node يُعيد meta-text باستمرار → اجعله deterministic (لا LLM).

---

## 5. MCTS depth > 1 مع نماذج مجانية {#mcts-depth}

**المشكلة:** `depth=2` يستدعي LLM 6+ مرات → rate limiting → timeout → إجابات فارغة.

**الحساب:**
```
depth=1: 1 expand (3 nodes) + 3 evaluate = 4 calls
depth=2: 3 expand (9 nodes) + 9 evaluate = 12 calls → rate limit
```

**القاعدة:** `depth=1` دائماً مع النماذج المجانية.

```python
# reasoning_service.py
best_node = await self.strategy.execute(
    root_content=f"Analyze: {query}",
    context=context,
    depth=1  # NOT 2 — causes rate limiting with free models
)
```

---

## 6. content=None صامت {#content-none}

**المشكلة:** `message.content` يُعيد `None` بدون exception → إجابة فارغة للطالب.

**الأسباب:**
1. نموذج reasoning-only مع system prompt
2. النموذج rate-limited ويُعيد response فارغ
3. خطأ في الـ API يُعيد `choices=[]`

**الإصلاح الإلزامي في كل مكان يستدعي LLM:**
```python
choices = data.get("choices", [])
if not choices:
    logger.warning("LLM returned no choices: %s", data.get("error", {}))
    return fallback_response

msg = choices[0].get("message", {})
# ISS-069: reasoning models put answer in "reasoning" not "content"
content = msg.get("content") or msg.get("reasoning") or ""
if not content or not content.strip():
    logger.warning("LLM returned empty content for model=%s", model)
    return fallback_response
```

---

## 7. تعارض patterns في تصنيف المسائل {#pattern-conflict}

**المشكلة:** pattern قصير يُطابق مسائل من نوع آخر.

**الأمثلة الحية:**
- `"حد"` في `limit` يُطابق `"محدد المصفوفة"` → يُصنَّف كـ `limit` بدلاً من `matrix`
- `"ادرس"` في `function_study` يُطابق `"ادرس تقاربية المتتالية"` → يُصنَّف كـ `function_study` بدلاً من `sequence`

**الإصلاح:**
1. الترتيب مهم — الأكثر تحديداً أولاً في `_MATH_TYPES`
2. استخدم patterns أطول وأكثر تحديداً:
```python
# ❌ خاطئ
"limit": ["حد", ...],
"matrix": ["محدد", ...],

# ✅ صحيح
"matrix": ["مصفوفة", "محدد المصفوفة", ...],  # أولاً
"limit": ["نهاية الدالة", "نهاية عند", "lim(", ...],  # بعده
```

**الفحص:**
```bash
PYTHONPATH=. python -m pytest tests/microservices/conversation_service/test_math_pipeline.py::TestMathTypeClassification -v
```

---

## 8. verification_node يستدعي LLM بـ prompt معقد {#verification-llm}

**المشكلة:** `verification_node` يستدعي LLM لإضافة تحقق وتفسير → النموذج يُعيد meta-text (anti-pattern #4).

**الحل المُطبَّق (ISS-070):** جعل `verification_node` deterministic — يُجمِّع الإجابة فقط بدون LLM:
```python
async def verification_node(state: MathPipelineState) -> MathPipelineState:
    solution = state.get("solution", "")
    label = type_labels.get(state["math_type"], "📚 رياضيات")
    final = f"## {label}\n\n{solution}"
    return {**state, "final_response": final}
```

**التحقق والتفسير** مُدمَجان في `step_by_step_node` (القسم 5 و6 من الـ 6 أقسام الإلزامية).

**متى تُعيد LLM لـ verification_node؟**
فقط إذا كان النموذج يُعيد إجابات نقية بدون meta-text — اختبر أولاً بـ 5 أسئلة متنوعة.
