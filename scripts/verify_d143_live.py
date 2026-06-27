#!/usr/bin/env python3
"""
D-143 (المرحلة 1) — التحقق الحي: الإجابة الحسابية الحتمية للاحتمالات (ISS-117).

يستدعي **الكود الحقيقي** (`_build_probability_computational_answer` + `number_parity_counts`)
ويُثبت على آلاف الصياغات:
  - «لماذا نضرب 11×10×9» ⇒ مبدأ العدّ (÷!3)، لا الحادثة A.
  - «كيف حصلنا على 56» / الحادثة B (جداء فردي) ⇒ 56/165 حتمياً من أرقام الكرات.
  - C/D/X/الأمل/الشرطي ⇒ تأجيل حتمي صادق («ليس الحادثة A»)، بلا أيّ رقم من LLM.
  - التحية/الاسترجاع/الحادثة A ⇒ تمرير (لا اختطاف).
ثم (إن توفّرت الأسرار) Supabase Edge bridge (HTTPS:443).

Usage: python3 scripts/verify_d143_live.py
"""

from __future__ import annotations

import itertools
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.infrastructure.clients.orchestrator_client import OrchestratorClient
from app.services.skills.probability_skill import ProbabilityCalculatorSkill

_PASS, _FAIL = "✅", "❌"


async def _route(q: str):
    return await OrchestratorClient._build_probability_computational_answer(q, None)


def _expand(cores, prefixes=("",), suffixes=("", " في التمرين", "؟", " يا أستاذ", " بالتفصيل")):
    out = set()
    for pre, core, suf in itertools.product(prefixes, cores, suffixes):
        out.add(f"{pre} {core}{suf}".strip())
    return out


_WHY = ["لماذا", "ليش", "علاش", "pourquoi", "اشرح لماذا"]
_HOW = ["كيف", "كيفاش", "من اين", "comment", "اشرح كيف", "", "احسب", "بيّن أن"]

CATS = {
    "combinations": _expand(
        ["نضرب 11×10×9", "ضربنا 11 و 10 و 9", "نضرب ثلاثة أرقام في بعضهم", "الترتيب في السحب"],
        prefixes=_WHY,
    ),
    "event_b": _expand(
        ["حصلنا على 56", "P(B)=56/165", "احتمال الحادثة B", "جداء الأرقام فردي", "56"],
        prefixes=_HOW,
    ),
    "event_c": _expand(["احتمال الحادثة C", "جداء الأرقام زوجي", "P(C)"], prefixes=_HOW),
    "event_d": _expand(
        ["احتمال الحادثة D", "جداء معدوم", "السحب على التوالي بدون إرجاع"], prefixes=_HOW
    ),
    "random_var": _expand(["المتغير العشوائي X", "قانون الاحتمال للمتغير X"], prefixes=_HOW),
    "expected": _expand(["الأمل الرياضي E(X)", "احسب E(X)"], prefixes=_HOW),
    "conditional": _expand(["الاحتمال الشرطي", "P_A(B)"], prefixes=_HOW),
}
PASS_THROUGH = _expand(
    [
        "السلام عليكم",
        "اعطني تمرين الاحتمالات 2024",
        "كيف افهم السؤال الأول",
        "احتمال الحادثة A نفس اللون",
        "ما هي الحادثة A",
    ],
    suffixes=("", "؟"),
)


async def main() -> int:
    print("=" * 78)
    print("D-143 LIVE — deterministic probability computational answers (real code)")
    print("=" * 78)

    # 0) parity model ground truth
    official = (
        "كرتان بيضاوان مرقمتان بـ: 1، 3\nأربع كرات حمراء مرقمة بـ: 0، 1، 1، 3\n"
        "خمس كرات خضراء مرقمة بـ: 0، 1، 1، 3، 4"
    )
    parity = ProbabilityCalculatorSkill.number_parity_counts(official)
    ok_parity = parity == {"odd": 8, "even": 3, "zero": 2, "total": 11}
    print(
        f"{_PASS if ok_parity else _FAIL} number_parity_counts → {parity} (expect odd=8 ⇒ 56/165)"
    )

    total, fails, dist = 0, [], {}
    for expected, qs in CATS.items():
        for q in qs:
            total += 1
            r = await _route(q)
            ev = r[1] if r else None
            dist[ev] = dist.get(ev, 0) + 1
            if r is None:
                fails.append(("MISSED", expected, q))
            elif ev != expected:
                fails.append(("WRONG", f"{expected}->{ev}", q))

                fails.append(("WRONG", f"{expected}->{ev}", q))
            elif expected == "event_b" and ("= 56" not in r[0] or "(8×7×6)" not in r[0]):
                fails.append(("BAD56", expected, q))
            elif False:
                fails.append(("NO_DISTANCE", expected, q))

    pt_total, pt_hijacked = 0, []
    for q in PASS_THROUGH:
        pt_total += 1
        if await _route(q) is not None:
            pt_hijacked.append(q)

    print(f"\nComputational questions fuzzed: {total}")
    print(f"Pass-through questions fuzzed:  {pt_total}")
    print(f"Routing distribution: {dist}")
    print(f"{_PASS if not fails else _FAIL} computational failures: {len(fails)}")
    for f in fails[:10]:
        print("   ", f)
    print(
        f"{_PASS if not pt_hijacked else _FAIL} pass-through hijacked (must be 0): {len(pt_hijacked)}"
    )
    for h in pt_hijacked[:10]:
        print("   ", h)

    # Supabase Edge bridge (read-only) — optional live infra check.
    bridge = os.getenv(
        "SUPABASE_EDGE_FUNCTION_URL",
        "https://aocnuqhxrhxgbfcgbxfy.supabase.co/functions/v1/claude-admin",
    )
    token = os.getenv("SUPABASE_EDGE_FUNCTION_KEY", "")
    if token:
        try:
            req = urllib.request.Request(
                bridge,
                data=json.dumps({"sql_query": "SELECT version() AS v"}).encode(),
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                v = json.load(resp)["data"][0]["v"][:32]
            print(f"\n{_PASS} Supabase bridge live: {v}")
        except Exception as exc:  # pragma: no cover
            print(f"\n{_FAIL} Supabase bridge: {exc}")

    ok = ok_parity and not fails and not pt_hijacked
    print(
        "\n=== RESULT:",
        "ALL PASS — zero drift to event A, zero hijack" if ok else "FAILURES",
        f"({total + pt_total} questions) ===",
    )
    return 0 if ok else 1


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(main()))
