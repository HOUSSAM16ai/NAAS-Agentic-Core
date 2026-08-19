#!/usr/bin/env python3
"""الحرفية السحرية ممنوعة (D-270 L5).

**لماذا هذه البوّابة موجودة:**

هذا المستودع دفع ثمن الحرفية المُكرَّرة **أربع مرّات**، وفي كلّ مرّة كُتِبت بوّابةٌ
لحادثةٍ بعينها بدل قانونٍ للصنف:

===========  ==========================================================================
القرار        العطب المقيس
===========  ==========================================================================
**D-185**     رمزٌ يطبعه المعلّم ولا يعرف تعريفه — لأنّ المفتاح كان **اسم المفهوم** لا
              الرمز، فمن لا يعرف الاسم لا يستطيع السؤال (دائرةٌ مغلقة · ISS-138).
**D-186**     **ثلاث قوائم** لنيّةٍ واحدة (23 · 13 · 27 علامة) لا تتّفق أيّ اثنتين،
              فصُنِّف سؤالٌ تعريفي `unknown` وأُجيب الطالب بمثالٍ عارٍ (ISS-139).
**D-191**     ``CANONICAL_EXERCISE_QUERY`` في **٧ مواضع** تُغذّي **١٢** نقطة استدعاء،
              فتعلّم الطالبُ مسألةً ليست مسألته (ISS-140).
**D-193**     **ثلاثة** تعاريف متنافرة لـ``concept_id``، فسقطت أسئلة الفيزياء والعلوم
              كلّها إلى ``"general"`` — أي أنّ الطبقة المعرفية لا تقيس شيئاً في مادةٍ
              معاملها **٦**.
===========  ==========================================================================

الجذر واحد في الأربع: **نصٌّ يقرؤه البرنامج بلا موطنٍ واحد**. والفرق بين موطنٍ واحد
وسبعة هو الفرق بين تغييرٍ واحد وسبعة — وواحدٌ منها يُنسى دائماً.

فهذه البوّابة تُعمّم القاعدة بدل انتظار الحادثة الخامسة: أيّ مُعرِّفٍ برمجي (اسم
متغيّر بيئة · ترويسة ``X-`` · ثابتٌ بصيغة ``SCREAMING_SNAKE``) يظهر **حرفياً في
ملفّين أو أكثر** هو دَين.

**القياس (2026-08-19):** **١٧٤** مُعرِّفاً مُكرَّراً — على رأسها ``OPENROUTER_API_KEY``
في ١٣ ملفّاً و``DATABASE_URL`` في ١٠ و``X-Correlation-ID`` في ٨. فالمنع الفوري يعني
إعادة هيكلةٍ عبر ١٢٧٣ ملفّاً في دفعةٍ واحدة، وهو أخطر من الدَّين. القائمة **مُجمَّدة
وتتقلّص فقط، وفي الاتجاهين**: حرفيةٌ جديدة مُكرَّرة ⇒ أحمر، وحرفيةٌ وُحِّدت وبقيت في
القائمة ⇒ أحمر أيضاً.

⛔ ``tests/`` مُستثناة عمداً: تعداد الصيغ فيها **حارسٌ لا نسخة** (سابقة D-186).

المصدر القانوني: ``docs/governance/MAGIC_STRINGS.json``.
تُشغَّل ضمن وظيفة ``guardrails``. Exit 0 = نظيف · 1 = انتهاك.
"""

from __future__ import annotations

import ast
import collections
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
POLICY = REPO_ROOT / "docs" / "governance" / "MAGIC_STRINGS.json"

_FAILURES: list[str] = []


def _fail(msg: str) -> None:
    _FAILURES.append(msg)
    print(f"❌ {msg}")


def _pass(msg: str) -> None:
    print(f"✅ {msg}")


def _is_identifier_literal(value: str) -> bool:
    """مُعرِّفٌ يقرؤه البرنامج: `SCREAMING_SNAKE` أو ترويسة `X-`."""
    if value.lower().startswith("x-") and len(value) >= 5:
        return True
    return value.isupper() and len(value) >= 6 and "_" in value and value.replace("_", "").isalnum()


def _duplicated(scopes: list[str]) -> tuple[dict[str, set[str]], list[str]]:
    """المُعرِّفات الظاهرة في ملفّين+، ومعها الملفّات التي تعذّر تحليلها."""
    seen: dict[str, set[str]] = collections.defaultdict(set)
    unreadable: list[str] = []
    for scope in scopes:
        root = REPO_ROOT / scope
        if not root.is_dir():
            _fail(f"`scopes` يسمّي مجلّداً غير موجود: {scope}")
            continue
        for path in root.rglob("*.py"):
            rel = str(path.relative_to(REPO_ROOT))
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, OSError, UnicodeDecodeError) as exc:
                # ⛔ ملفٌّ لم يُحلَّل يُبلَّغ عنه — بوّابةٌ لا تقرأ ملفاً لا تُبلِّغ أنه
                #    نظيف (D-208 §6؛ كانت `except SyntaxError: return []` في ١٣ فارضاً).
                unreadable.append(f"{rel}: {type(exc).__name__}")
                continue
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and _is_identifier_literal(node.value)
                ):
                    seen[node.value].add(rel)
    return {key: value for key, value in seen.items() if len(value) > 1}, unreadable


def main() -> int:
    if not POLICY.is_file():
        print(f"❌ سجلّ الحرفيات مفقود: {POLICY.relative_to(REPO_ROOT)}")
        return 1
    try:
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"❌ `MAGIC_STRINGS.json` ليس JSON صالحاً: {exc}")
        return 1

    scopes = list(policy.get("scopes", []))
    if not scopes:
        print("❌ `scopes` فارغة — نطاقٌ خاطئ يُقرأ نجاحاً")
        return 1

    duplicated, unreadable = _duplicated(scopes)
    if unreadable:
        _fail(f"ملفّات تعذّر تحليلها — لا تُعَدّ نظيفة (D-208 §6): {unreadable[:6]}")

    declared = set(policy.get("frozen_debt", []))
    actual = set(duplicated)

    if new := sorted(actual - declared):
        detail = {name: sorted(duplicated[name])[:3] for name in new[:6]}
        _fail(
            f"حرفيات مُكرَّرة جديدة ({len(new)}): {detail} — "
            "لكلّ مُعرِّفٍ موطنٌ مُسمّى واحد يُستورَد، لا نسخةٌ في كل ملفّ"
        )
    if closed := sorted(declared - actual):
        _fail(
            f"حرفيات وُحِّدت وبقيت في الدَّين ({len(closed)}): {closed[:8]} — "
            "احذفها من `MAGIC_STRINGS.json` في نفس الـPR (الدَّين ثنائي الاتجاه — D-189)"
        )

    if _FAILURES:
        print(f"\n❌ الحرفية السحرية (D-270 L5): {len(_FAILURES)} انتهاكاً")
        return 1
    print(
        f"\n✅ الحرفية السحرية (D-270 L5): صفر حرفيةٍ مُكرَّرة جديدة · دَينٌ مُجمَّد يتقلّص: {len(declared)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
