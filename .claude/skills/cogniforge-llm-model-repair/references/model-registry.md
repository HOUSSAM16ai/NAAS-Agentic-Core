# CogniForge LLM Model Registry

> Last verified: **2026-05-15** via live benchmark on OpenRouter
> Update this file after every model benchmark session.

## Table of Contents
1. [Active Models (Verified Working)](#active-models)
2. [Banned Models](#banned-models)
3. [Benchmark Methodology](#benchmark-methodology)
4. [Fallback Chain Configuration](#fallback-chain)

---

## Active Models (Verified Working) {#active-models}

| Rank | Model ID | TTFT | Arabic | LaTeX | Reasoning | Notes |
|------|----------|------|--------|-------|-----------|-------|
| 1 | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | 4s | ✅ | ✅ | ✅ tokens | **PRIMARY** — reasoning tokens, fast |
| 2 | `nvidia/nemotron-3-super-120b-a12b:free` | 14s | ✅ | ✅ | — | FALLBACK_1 — high quality |
| 3 | `openai/gpt-oss-20b:free` | 25s | ✅ | ✅ | — | FALLBACK_2 — reliable |
| 4 | `openai/gpt-oss-120b:free` | 40s | ✅ | ✅ | — | FALLBACK_3 — highest quality |
| 5 | `nvidia/nemotron-3-nano-30b-a3b:free` | 4s | ✅ | ✅ | — | FALLBACK_4 — fast, no reasoning |

## Banned Models {#banned-models}

| Model ID | Reason | Date Banned | ISS |
|----------|--------|-------------|-----|
| `inclusionai/ring-2.6-1t:free` | Rate-limited upstream on Novita — permanent | 2026-05-15 | ISS-068 |
| `google/gemini-2.0-flash-exp:free` | No endpoints on OpenRouter | 2026-05-15 | ISS-068 |
| `tngtech/deepseek-r1t2-chimera:free` | No endpoints on OpenRouter | 2026-05-15 | ISS-068 |
| `qwen/qwen3-coder:free` | Provider returned error | 2026-05-15 | ISS-068 |
| `deepseek/deepseek-v4-flash:free` | Provider returned error | 2026-05-15 | ISS-068 |
| `google/gemma-4-26b-a4b-it:free` | Provider returned error | 2026-05-15 | ISS-068 |

---

## Benchmark Methodology {#benchmark-methodology}

Run `scripts/benchmark_models.py` to re-verify. Manual test criteria:

**Pass criteria (all must be true):**
- Response received in < 30s
- Arabic text present (`any('\u0600' <= c <= '\u06ff' for c in content)`)
- LaTeX present (`'$$' in content or '\\[' in content or '\\(' in content`)
- No error in `d.get('error')` or `d.get('choices', [])` non-empty

**Test question (use this exact question for consistency):**
```
System: أنت أستاذ رياضيات للبكالوريا الجزائرية. أجب بالعربية مع LaTeX.
User: اشرح: إذا كانت f(x) = x*ln(x) - x، أوجد f'(x) وادرس إشارتها
```

**When to re-benchmark:**
- Any service returns empty answers
- A model appears in logs with `429` or `rate-limited`
- OpenRouter announces model changes
- Monthly verification (models come and go)

---

## Fallback Chain Configuration {#fallback-chain}

### app/core/ai_config.py
```python
PRIMARY = _resolve_primary_model("nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free")
GATEWAY_FALLBACK_1 = "nvidia/nemotron-3-super-120b-a12b:free"
GATEWAY_FALLBACK_2 = "openai/gpt-oss-20b:free"
GATEWAY_FALLBACK_3 = "openai/gpt-oss-120b:free"
GATEWAY_FALLBACK_4 = "nvidia/nemotron-3-nano-30b-a3b:free"
```

### microservices env vars (for manual restart)
```bash
OPENROUTER_MODEL="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
PRIMARY_MODEL="nvidia/nemotron-3-super-120b-a12b:free"   # research-agent
PLANNING_AI_MODEL="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
AUDITOR_LLM_MODEL="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
CONVERSATION_LLM_MODEL="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
```
