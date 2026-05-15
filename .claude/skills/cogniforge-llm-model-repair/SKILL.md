---
name: cogniforge-llm-model-repair
description: >
  Diagnose and fix broken LLM model configurations in CogniForge microservices.
  Use when: AI responses are empty, garbage, or missing LaTeX; reasoning-agent
  returns empty answers or times out; research-agent returns empty results;
  any service logs "rate-limited", "429", or "Provider returned error";
  a model default needs updating after OpenRouter deprecates a free model;
  content=None from any model; reasoning-only model used as PRIMARY.
  Triggers on: "إجابات فارغة", "إجابات كارثية", "rate-limited", "429",
  "Provider returned error", "No endpoints found", "empty answer", "model broken",
  "reasoning timeout", "inclusionai", "ring-2.6", "model not working",
  "LLM not responding", "بدون LaTeX", "إجابات غبية", "نموذج معطّل",
  "content=None", "reasoning model", "omni-reasoning", "إجابات غير منظمة",
  "حروف متداخلة", "فقدان سياق", "نصوص غير منظمة".
---

# CogniForge LLM Model Repair

> **Law:** A model is ACTIVE only when it returns Arabic text + LaTeX in < 30s
> AND `message.content` is non-None and non-empty with a system prompt.
> A running service ≠ a working LLM. Always verify with a live math question.

---

## 1. Rapid Diagnosis (60 seconds)

```bash
# Step 1: Check what model each service is using
grep -rn "OPENROUTER_MODEL\|DEFAULT_MODEL\|AI_MODEL\|primary_model\|self.model" \
  app/core/ai_config.py \
  microservices/reasoning_agent/src/ai_client.py \
  microservices/reasoning_agent/src/core/config.py \
  microservices/planning_agent/settings.py \
  | grep -v __pycache__ | grep -v "^.*#"

# Step 2: Scan for banned models as active values
grep -rn "inclusionai/ring-2.6-1t:free\|nemotron-3-nano-omni-30b-a3b-reasoning:free" \
  --include="*.py" app/ microservices/ \
  | grep -v __pycache__ | grep -v "^.*#" | grep -v test_

# Step 3: Test content=None bug (ISS-069)
python3 -c "
import asyncio, httpx, os
async def test():
    async with httpx.AsyncClient() as c:
        r = await c.post('https://openrouter.ai/api/v1/chat/completions',
            headers={'Authorization': f'Bearer {os.environ[\"OPENROUTER_API_KEY\"]}'},
            json={'model': 'nvidia/nemotron-3-nano-30b-a3b:free',
                  'messages': [{'role': 'system', 'content': 'أستاذ رياضيات.'},
                                {'role': 'user', 'content': 'احسب 2+2'}],
                  'max_tokens': 50}, timeout=15)
        msg = r.json()['choices'][0]['message']
        content = msg.get('content')
        print('content:', repr(content))
        assert content is not None and len(content) > 0, 'BROKEN: content=None'
        print('OK: content is valid')
asyncio.run(test())
"

# Step 4: Live model test (30s)
python3 scripts/benchmark_models.py
```

**Symptom → Root Cause mapping:**

| Symptom | Root Cause |
|---------|-----------|
| `reasoning-agent` returns `{"answer": ""}` | Model rate-limited OR content=None bug |
| `content=None` in any service | Reasoning-only model used as PRIMARY (ISS-069) |
| إجابات فارغة مع system prompt | `nemotron-3-nano-omni-30b-a3b-reasoning:free` كـ PRIMARY |
| `research-agent` returns `{"results": []}` | Tavily key missing OR model broken |
| `429` in service logs | Model rate-limited upstream |
| `Provider returned error` | Model endpoint removed from OpenRouter |
| `No endpoints found` | Model no longer available on OpenRouter |
| Response has no LaTeX | System prompt missing LaTeX instruction |
| Response in English only | System prompt not enforcing Arabic |
| MCTS timeout (>45s) | depth > 1 with free model |

---

## 2. Live Model Benchmark

Run `scripts/benchmark_models.py` to find working models. See `references/model-registry.md` for the current verified model list.

**Quick single-model test:**
```python
import httpx, asyncio, time

async def test(model, api_key):
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    t0 = time.time()
    async with httpx.AsyncClient(timeout=25) as c:
        r = await c.post('https://openrouter.ai/api/v1/chat/completions',
            headers=headers,
            json={
                'model': model,
                'messages': [
                    {'role': 'system', 'content': 'أنت أستاذ رياضيات. أجب بالعربية مع LaTeX.'},
                    {'role': 'user', 'content': 'ما هو مشتق ln(x)؟'}
                ],
                'max_tokens': 150
            })
        d = r.json()
        choices = d.get('choices', [])
        if choices:
            content = choices[0].get('message', {}).get('content', '') or ''
            has_latex = '$$' in content or '\\[' in content or '\\(' in content
            has_arabic = any('\u0600' <= c <= '\u06ff' for c in content)
            print(f'✅ {time.time()-t0:.1f}s | LaTeX:{has_latex} | AR:{has_arabic} | {model}')
        else:
            print(f'❌ {model}: {d.get("error",{}).get("message","?")}')

asyncio.run(test('nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free', 'YOUR_KEY'))
```

---

## 3. Replace Broken Model (Surgical Fix)

When a model is confirmed broken, replace it in all 14 locations. Run `scripts/replace_model.py` for automated replacement, or do it manually:

**Files to update (in order):**

```
app/core/ai_config.py                                          ← PRIMARY + fallback chain
app/services/chat/local_graph.py                               ← system prompts
app/services/chat/agents/orchestrator.py                       ← hardcoded model
app/services/chat/agents/socratic_tutor.py                     ← hardcoded model
microservices/reasoning_agent/src/ai_client.py                 ← OPENROUTER_MODEL default
microservices/reasoning_agent/src/core/config.py               ← DEFAULT_MODEL
microservices/reasoning_agent/src/services/reasoning_service.py ← timeout + depth
microservices/reasoning_agent/src/services/strategies/mcts.py  ← prompts
microservices/research_agent/src/search_engine/super_search.py ← PRIMARY_MODEL
microservices/research_agent/src/search_engine/query_refiner.py ← default model
microservices/planning_agent/settings.py                       ← AI_MODEL
microservices/orchestrator_service/src/core/ai_config.py       ← AvailableModels
microservices/orchestrator_service/src/services/llm/client.py  ← default_model
microservices/orchestrator_service/src/services/overmind/agents/orchestrator.py
microservices/orchestrator_service/src/services/overmind/graph/main.py ← DSPy model
microservices/conversation_service/src/conversation_graph.py   ← model
microservices/auditor_service/src/ai.py                        ← model
```

**Verify no banned model remains:**
```bash
grep -rn "inclusionai/ring-2.6-1t:free" --include="*.py" app/ microservices/ \
  | grep -v __pycache__ | grep -v "^.*#" | grep -v test_
# Must return empty
```

---

## 4. Restart Services with New Model

```bash
export OPENROUTER_API_KEY="..."
export TAVILY_API_KEY="..."
export PYTHONPATH="/workspaces/NAAS-Agentic-Core"

# Kill old instances
kill $(pgrep -f "reasoning_agent.main:app") 2>/dev/null
kill $(pgrep -f "research_agent.main:app") 2>/dev/null
kill $(pgrep -f "planning_agent.main:app") 2>/dev/null
sleep 3

# Restart with explicit model env vars
OPENROUTER_MODEL="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free" \
OPENROUTER_API_KEY="$OPENROUTER_API_KEY" \
PYTHONPATH="$PYTHONPATH" \
nohup python -m uvicorn microservices.reasoning_agent.main:app \
  --host 0.0.0.0 --port 8008 --log-level warning > /tmp/reasoning.log 2>&1 &

# Verify
sleep 8
curl -s http://localhost:8008/health
# Expected: {"llm_backend":"openrouter","mcts_enabled":"true"}
```

---

## 5. Fix System Prompts for Arabic Math

Load `references/system-prompt-templates.md` for the canonical prompt templates.

**Mandatory elements in every educational prompt:**
1. `$$...$$` for standalone equations
2. `\(...\)` for inline symbols
3. `$$\boxed{...}$$` for final results
4. Numbered steps with mathematical principle explanation
5. Arabic فصحى only (no English except technical terms)
6. Geometric/physical interpretation when applicable

**Quick check:**
```bash
python3 -c "
content = open('app/services/chat/local_graph.py').read()
checks = ['\$\$', 'boxed', 'LaTeX', 'educational', 'general', 'chat']
for c in checks:
    print(f'{'✅' if c in content else '❌'} {c}')
"
```

---

## 6. Fix MCTS for Free Models

Free models rate-limit at depth > 1. Always use depth=1.

```python
# microservices/reasoning_agent/src/services/reasoning_service.py

class ReasoningWorkflow(Workflow):
    # depth=1 prevents rate-limit cascade with free models
    def __init__(self, timeout: int = 45, verbose: bool = True):
        super().__init__(timeout=timeout, verbose=verbose)

# In the reason step:
best_node = await self.strategy.execute(
    root_content=f"Analyze: {query}",
    context=context,
    depth=1  # NOT 2 — causes 6+ LLM calls → rate limiting
)
```

---

## 7. Verify End-to-End

```bash
python3 << 'EOF'
import httpx, asyncio, time

async def verify():
    # Health matrix
    for port, name in [(8000,'main'), (8001,'user'), (8002,'planning'),
                       (8007,'research'), (8008,'reasoning')]:
        r = await httpx.AsyncClient(timeout=4).get(f'http://localhost:{port}/health')
        d = r.json()
        status = d.get('status') or d.get('application', '?')
        print(f'  {"✅" if status in ["ok","healthy"] else "❌"} :{port} {name}: {status}')

    # Live reasoning test
    t0 = time.time()
    r = await httpx.AsyncClient(timeout=50).post('http://localhost:8008/execute', json={
        'caller_id': 'verify', 'action': 'reason',
        'query': 'ما هو مشتق ln(x)؟',
        'payload': {'query': 'ما هو مشتق ln(x)؟', 'context': 'رياضيات'}
    })
    d = r.json()
    answer = d.get('data', {}).get('answer', '')
    has_latex = '\\[' in answer or '$$' in answer or '\\(' in answer
    print(f'  {"✅" if d.get("status")=="success" else "❌"} reasoning ({time.time()-t0:.1f}s) | LaTeX:{has_latex}')

asyncio.run(verify())
EOF
```

---

## 8. Update Memory After Fix

After any model change, update these files:
- `CLAUDE.md` — add ISS-NNN entry with benchmark results and permanent rule
- `.memory/issues.md` — full diagnosis + fix + files changed
- `.memory/runtime_truth.md` — D-NNN live verification table
- `.memory/decisions.md` — decision record with rationale and invariants

See `references/memory-update-template.md` for the exact format.

---

## Anti-patterns

- **Never** trust service logs alone — always probe `/health` AND test with a live math question.
- **Never** set MCTS depth > 1 with free models — causes rate-limit cascade.
- **Never** use `inclusionai/ring-2.6-1t:free` — permanently rate-limited on Novita (ISS-068).
- **Never** use `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` as PRIMARY — content=None with system prompt (ISS-069).
- **Never** use any model ending in `:reasoning:free` as PRIMARY without verifying `message.content` is non-None with a system prompt.
- **Never** hardcode a model string without an env var override — use `os.getenv("MODEL_VAR", "default")`.
- **Never** assume a model works because it appears in OpenRouter's model list — test it live with a system prompt.
- **Never** skip the memory update — the next agent session will repeat the same diagnosis.
- **Never** accept `content=None` silently — always fallback to `reasoning` field and log a warning.
