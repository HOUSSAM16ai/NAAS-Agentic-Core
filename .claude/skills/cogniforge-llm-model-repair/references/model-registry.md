# CogniForge LLM Model Registry

> Last verified: **2026-05-15** via live benchmark on OpenRouter (ISS-069)
> Update this file after every model benchmark session.

## Active Models (Verified Working)

| Rank | Model ID | TTFT | Arabic | LaTeX | content≠None | Notes |
|------|----------|------|--------|-------|--------------|-------|
| 1 | `nvidia/nemotron-3-nano-30b-a3b:free` | 3.1s | ✅ | ✅ | ✅ | **PRIMARY** — جودة 4/4 |
| 2 | `arcee-ai/trinity-large-thinking:free` | 4.7s | ✅ | ✅ | ✅ | FALLBACK_1 |
| 3 | `nvidia/nemotron-3-super-120b-a12b:free` | 22s | ✅ | ✅ | ✅ | FALLBACK_2 |
| 4 | `openai/gpt-oss-120b:free` | 25s | ✅ | ✅ | ✅ | FALLBACK_3 |
| 5 | `openai/gpt-oss-20b:free` | 27s | ✅ | ✅ | ✅ | FALLBACK_4 |
| 6 | `z-ai/glm-4.5-air:free` | ~15s | ✅ | ✅ | ✅ | FALLBACK_5 |

---

## Banned Models

| Model ID | Reason | Date | ISS |
|----------|--------|------|-----|
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | content=None مع system prompt | 2026-05-15 | ISS-069 |
| `inclusionai/ring-2.6-1t:free` | Rate-limited upstream on Novita | 2026-05-15 | ISS-068 |
| `google/gemini-2.0-flash-exp:free` | No endpoints on OpenRouter | 2026-05-15 | ISS-068 |
| `deepseek/deepseek-v4-flash:free` | TTFT=56s — unusable | 2026-05-15 | ISS-069 |
| `google/gemma-4-31b-it:free` | HTTP 429 — rate-limited | 2026-05-15 | ISS-069 |
| `qwen/qwen3-next-80b-a3b-instruct:free` | HTTP 429 — rate-limited | 2026-05-15 | ISS-069 |

### Reasoning-Only Model Warning (ISS-069)

Any model with `reasoning` in the name must pass this test before use as PRIMARY:

```python
import asyncio, httpx, os
async def test_content_not_none(model_id):
    async with httpx.AsyncClient() as c:
        r = await c.post('https://openrouter.ai/api/v1/chat/completions',
            headers={'Authorization': f'Bearer {os.environ["OPENROUTER_API_KEY"]}'},
            json={'model': model_id,
                  'messages': [{'role': 'system', 'content': 'أستاذ رياضيات.'},
                                {'role': 'user', 'content': 'احسب 2+2'}],
                  'max_tokens': 50}, timeout=15)
        msg = r.json()['choices'][0]['message']
        content = msg.get('content')
        assert content is not None and len(content) > 0, f'BANNED: content=None'
        print(f'OK: {repr(content[:50])}')
asyncio.run(test_content_not_none('nvidia/nemotron-3-nano-30b-a3b:free'))
```

---

## Benchmark Methodology

**Pass criteria (ALL must be true):**
1. `message.content` non-None and non-empty with system prompt
2. Response in < 30s
3. Arabic text present
4. LaTeX present (`$$` or `\[` or `\(`)
5. Correct answer (F=12N for m=3kg, a=4m/s²)

**Standard test question:**
```
System: أنت أستاذ رياضيات للبكالوريا الجزائرية. أجب بالعربية مع LaTeX.
User: جسم كتلته 3kg يتسارع بـ 4m/s². احسب القوة المؤثرة عليه.
Expected: $$\boxed{F = 12\,\text{N}}$$
```

---

## Fallback Chain (current — ISS-069)

```python
# app/core/ai_config.py
PRIMARY = "nvidia/nemotron-3-nano-30b-a3b:free"
GATEWAY_FALLBACK_1 = "arcee-ai/trinity-large-thinking:free"
GATEWAY_FALLBACK_2 = "nvidia/nemotron-3-super-120b-a12b:free"
GATEWAY_FALLBACK_3 = "openai/gpt-oss-120b:free"
GATEWAY_FALLBACK_4 = "openai/gpt-oss-20b:free"
GATEWAY_FALLBACK_5 = "z-ai/glm-4.5-air:free"
```

### Bulk model replacement command
```bash
OLD="current-model:free"
NEW="new-model:free"
find . -name "*.py" | grep -v __pycache__ | grep -v .git | \
  xargs grep -l "$OLD" | while read f; do
    sed -i "s|$OLD|$NEW|g" "$f" && echo "Updated: $f"
  done
```
