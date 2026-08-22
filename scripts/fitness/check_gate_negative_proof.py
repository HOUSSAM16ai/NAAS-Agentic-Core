#!/usr/bin/env python3
"""البوّابة تُثبِت أنّها تحجب (D-270 L4).

**لماذا هذه البوّابة موجودة:**

ISS-148 هي الدرس المؤسِّس: عقود ترانسكريبت كانت **خضراء** بينما مسار التسريب
(``_stage_escape_hatch``) خارج مرمى كلّ واحدٍ منها. فالخُضرة لم تكن دليل سلامة —
كانت دليل **عمى**. وسمّى `ENGINEERING_DOCTRINE.md` هذا «الثمن الثاني»: فارضٌ بلا مرمى.

وD-266 طبّق الدرس على **تنفيذ** البوّابات (أتُشغَّل أصلاً؟). لكن بقي السؤال الأصعب
بلا فارض: **هل تحجب البوّابة حين يُخرَق قانونها؟** بوّابةٌ تُشغَّل وتخرج بصفر دائماً
تجتاز كلّ فحصٍ في المستودع وهي لا تحرس شيئاً.

**القياس (2026-08-19):** من **٧٧** بوّابة على القرص، **٢٦** فقط تملك اختباراً يؤكّد
فشلاً صريحاً. و**٢٠** مذكورةٌ في اختبارٍ يتوقّع **نجاحها** — وهو يُثبِت أنّها تعمل
ولا يُثبِت أنّها تحجب. و**٣١** بلا أيّ اختبار. أي أنّ ثلثَي منظومة الحراسة لم يُبرهَن
عليه، بينما المستودع يفرض على الكود برهاناً ثلاثياً.

**لماذا سجلٌّ ودَين لا منعٌ فوري:** كتابة ٥١ برهاناً سلبياً في دفعةٍ واحدة تعني ٥١
اختباراً غير مُراجَع يدخل معاً — وهو أخطر من الدَّين المُعلَن. فالقائمة **مُجمَّدة
وتتقلّص فقط، وفي الاتجاهين**: بوّابةٌ اكتسبت برهاناً وبقيت في الدَّين ⇒ CI أحمر
(نمط ``check_correlated_http`` — D-189).

⛔ ولا يُقبَل «اختبارٌ يستدعي البوّابة» برهاناً: البرهان السلبي يؤكّد **رمز خروجٍ
غير صفري** أو **قائمة فشلٍ غير فارغة** على مُدخَلٍ مكسورٍ عمداً.

المصدر القانوني: ``docs/governance/NEGATIVE_PROOFS.json``.
تُشغَّل ضمن وظيفة ``guardrails``. Exit 0 = نظيف · 1 = انتهاك.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
POLICY = REPO_ROOT / "docs" / "governance" / "NEGATIVE_PROOFS.json"
GATE_HOMES = ("scripts/fitness", "tools/ci")
TESTS_ROOT = REPO_ROOT / "tests"

#: ما يُعَدّ تأكيداً على **الفشل**. أيّ منها يكفي؛ وغيابها جميعاً يعني أنّ الاختبار
#: يُثبِت أنّ البوّابة تعمل لا أنّها تحجب.
NEGATIVE_ASSERTION = re.compile(
    r"==\s*1\b|!=\s*0\b|exit_code\s*==\s*1|_FAILURES|returncode\s*==\s*1"
    r"|failures\s*==\s*1|failures\s*>=\s*1|len\(failures\)\s*>=\s*1"
)

_FAILURES: list[str] = []


def _fail(msg: str) -> None:
    _FAILURES.append(msg)
    print(f"❌ {msg}")


def _pass(msg: str) -> None:
    print(f"✅ {msg}")


def _gates_on_disk() -> set[str]:
    return {
        path.name
        for home in GATE_HOMES
        if (REPO_ROOT / home).is_dir()
        for path in (REPO_ROOT / home).glob("check_*.py")
    }


def _proves_blocking(test_path: Path, gate_stem: str) -> bool:
    """هل يذكر الاختبارُ البوّابةَ **ويؤكّد فشلاً**؟"""
    try:
        text = test_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        # ⛔ ملفٌّ لم يُقرأ لا يُشهَد له ببرهان (D-208 §6).
        return False
    return gate_stem in text and bool(NEGATIVE_ASSERTION.search(text))


def _check_coverage(policy: dict, gates: set[str]) -> tuple[dict, dict]:
    proven: dict = policy.get("proven", {})
    debt: dict = policy.get("frozen_debt", {})

    if uncovered := sorted(gates - set(proven) - set(debt)):
        _fail(f"بوّابات بلا صفٍّ في السجلّ: {uncovered} — الغياب يُعلَن ولا يُصمَت عنه (D-206 L11)")
    if ghost := sorted((set(proven) | set(debt)) - gates):
        _fail(f"السجلّ يسمّي بوّابات غير موجودة: {ghost}")
    if both := sorted(set(proven) & set(debt)):
        _fail(f"بوّابات في `proven` و`frozen_debt` معاً: {both} — حالةٌ واحدة لا اثنتان")
    return proven, debt


def _proof_defect(gate: str, test_files: list[str]) -> str | None:
    """`"broken"` إن أحال إلى ملفٍّ محذوف · `"weak"` إن لم يؤكّد فشلاً · `None` إن سليم."""
    paths = [REPO_ROOT / rel for rel in test_files]
    if any(not path.is_file() for path in paths):
        return "broken"
    return None if any(_proves_blocking(path, gate[:-3]) for path in paths) else "weak"


def _check_proven(proven: dict) -> None:
    """كل برهانٍ مُعلَن موجودٌ فعلاً ويؤكّد فشلاً — لا إحالةً إلى ملفٍّ محذوف."""
    defects = {gate: _proof_defect(gate, files) for gate, files in sorted(proven.items())}
    broken = [f"{gate} → {proven[gate]}" for gate, kind in defects.items() if kind == "broken"]
    weak = [gate for gate, kind in defects.items() if kind == "weak"]
    if broken:
        _fail(f"براهين مُعلَنة تُحيل إلى ملفّات غير موجودة (خريطةٌ تكذب — ISS-149): {broken}")
    if weak:
        _fail(
            f"براهين لا تؤكّد فشلاً: {weak} — اختبارٌ يتوقّع نجاح البوّابة يُثبِت أنّها تعمل لا أنّها تحجب"
        )


def _acquired_proof(gate: str) -> bool:
    stem = gate[:-3]
    return any(_proves_blocking(path, stem) for path in TESTS_ROOT.rglob("test_*.py"))


def _check_debt_shrinks(debt: dict) -> None:
    """الاتجاه الآخر: دَينٌ أُغلق بلا تحديث السجلّ كذبٌ أيضاً (D-189)."""
    if empty := sorted(name for name, reason in debt.items() if not str(reason).strip()):
        _fail(f"دَينٌ بلا سببٍ منطوق: {empty} — الخانة الفارغة تُقرأ نجاحاً")
    if closed := sorted(gate for gate in debt if _acquired_proof(gate)):
        _fail(
            f"بوّابات اكتسبت براهين سلبية وبقيت في الدَّين: {closed} — "
            "انقلها إلى `proven` في نفس الـPR"
        )


def main() -> int:
    if not POLICY.is_file():
        print(f"❌ سجلّ البراهين السلبية مفقود: {POLICY.relative_to(REPO_ROOT)}")
        return 1
    try:
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"❌ `NEGATIVE_PROOFS.json` ليس JSON صالحاً: {exc}")
        return 1

    gates = _gates_on_disk()
    if not gates:
        print("❌ لم يُعثر على أيّ بوّابة — مواطن البوّابات خاطئة أو المستودع مبتور")
        return 1

    proven, debt = _check_coverage(policy, gates)
    _check_proven(proven)
    _check_debt_shrinks(debt)

    if _FAILURES:
        print(f"\n❌ البرهان السلبي (D-270 L4): {len(_FAILURES)} انتهاكاً")
        return 1
    print(
        f"\n✅ البرهان السلبي (D-270 L4): {len(proven)}/{len(gates)} بوّابة مُبرهَنٌ أنّها "
        f"تحجب · دَينٌ مُعلَن يتقلّص: {len(debt)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
