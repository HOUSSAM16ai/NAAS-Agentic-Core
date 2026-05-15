#!/usr/bin/env python3
"""
بنشمارك حي للنماذج المجانية على OpenRouter.
يختبر كل نموذج بسؤال رياضيات عربي ويُصنِّفها حسب السرعة والجودة.

الاستخدام:
    OPENROUTER_API_KEY=sk-or-... python3 benchmark_models.py
    python3 benchmark_models.py --key sk-or-... --question "ما هو مشتق ln(x)؟"
"""
import argparse
import asyncio
import os
import time

import httpx


CANDIDATES = [
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "openai/gpt-oss-20b:free",
    "openai/gpt-oss-120b:free",
    "z-ai/glm-4.5-air:free",
    "arcee-ai/trinity-large-thinking:free",
    "inclusionai/ring-2.6-1t:free",  # known broken — included to verify
]

SYSTEM = (
    "أنت أستاذ رياضيات للبكالوريا الجزائرية. "
    "أجب بالعربية الفصحى مع LaTeX ($$...$$ للمعادلات)."
)

DEFAULT_QUESTION = (
    "اشرح: إذا كانت f(x) = x*ln(x) - x، أوجد f'(x) وادرس إشارتها"
)


async def test_model(model: str, api_key: str, question: str) -> dict:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://cogniforge.local",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": question},
        ],
        "max_tokens": 400,
        "stream": False,
    }
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            d = r.json()
            elapsed = time.time() - t0
            choices = d.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "") or ""
                has_latex = "$$" in content or "\\[" in content or "\\(" in content
                has_arabic = any("\u0600" <= c <= "\u06ff" for c in content)
                score = (has_latex * 3) + (has_arabic * 2) + (len(content) > 100)
                return {
                    "model": model,
                    "elapsed": elapsed,
                    "score": score,
                    "has_latex": has_latex,
                    "has_arabic": has_arabic,
                    "content_len": len(content),
                    "preview": content[:200],
                    "ok": True,
                }
            else:
                err = d.get("error", {}).get("message", "unknown")[:80]
                return {"model": model, "elapsed": elapsed, "ok": False, "error": err}
    except Exception as e:
        return {"model": model, "elapsed": time.time() - t0, "ok": False, "error": str(e)[:80]}


async def main(api_key: str, question: str) -> None:
    print(f"Testing {len(CANDIDATES)} models with question:")
    print(f"  {question[:80]}...\n")

    results = []
    for model in CANDIDATES:
        result = await test_model(model, api_key, question)
        if result["ok"]:
            print(
                f"✅ {result['elapsed']:.1f}s | "
                f"LaTeX:{result['has_latex']} | AR:{result['has_arabic']} | "
                f"score:{result['score']} | {model}"
            )
        else:
            print(f"❌ {model}: {result.get('error', '?')}")
        results.append(result)

    good = [r for r in results if r["ok"] and r["has_latex"] and r["has_arabic"]]
    good.sort(key=lambda x: (-x["score"], x["elapsed"]))

    print("\n" + "=" * 70)
    print("RANKING (quality × speed):")
    print("=" * 70)
    for i, r in enumerate(good, 1):
        print(f"  {i}. {r['elapsed']:.1f}s score={r['score']} → {r['model']}")
        print(f"     {r['preview'][:120]}")
        print()

    if good:
        best = good[0]
        print(f"RECOMMENDED PRIMARY: {best['model']}")
        print(f"  TTFT={best['elapsed']:.1f}s | LaTeX={best['has_latex']} | Arabic={best['has_arabic']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark OpenRouter free models")
    parser.add_argument("--key", default=os.environ.get("OPENROUTER_API_KEY", ""))
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    args = parser.parse_args()

    if not args.key:
        print("ERROR: Set OPENROUTER_API_KEY env var or pass --key")
        raise SystemExit(1)

    asyncio.run(main(args.key, args.question))
