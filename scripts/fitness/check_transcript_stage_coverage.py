#!/usr/bin/env python3
"""ISS-148 — كل مرحلة حتمية في دور الطالب يبلغها مُشغِّل عقود الترانسكريبت.

## لماذا هذه البوّابة موجودة

عقود الترانسكريبت (D-186) هي شبكة الأمان التي تحوّل كل كارثة مُبلَّغ عنها إلى اختبار
دائم. لكنّ المُشغِّل كان يقف عند `_stage_concept_example` — **٧ مراحل من ١٢** — بينما
`chat_turn.py` يُشغّل الاثنتي عشرة. فبقيت `_stage_escape_hatch` (موطن
`_build_probability_direct_explanation`) خارج مرمى **كل** عقد.

النتيجة مُبرهَنة لا مُفترَضة: عقد ISS-144 أخضر في CI بينما كان الطالب في الإنتاج
(المحادثة 837، 2026-08-02 16:51 UTC) يتلقّى `C(4,3)=4` و`C(5,3)=10` و`165` مسرَّبةً،
ثمّ دوراً من ١٣٦ حرفاً يَعِد بالخطوات ولا يُعطي خطوة، ثمّ تكراراً لـ165. **بوّابة بلا
مرمى ليست بوّابة** — وشبكةُ أمانٍ لا يعرف أحدٌ أين ثقبها أسوأ من غيابها، لأنها تشتري
طمأنينةً بلا تغطية.

## ما تفرضه

كل مرحلة في سلسلة `chat_turn.py` إمّا:
  1. مشمولة في `_DETERMINISTIC_STAGES` (يبلغها المُشغِّل)، أو
  2. مُستثناة **بسببٍ منطوق** في `_LLM_DEPENDENT_STAGES`.

لا خيار ثالث: مرحلةٌ جديدة تُضاف إلى `chat_turn.py` بلا قرارٍ مكتوب تُفشِل CI
(D-206·L11 — الغياب لا يعني الغموض؛ سببُ الاستثناء يُصرَّح ولا يُصادَف).

تقرأ بـ**AST** لا بـgrep: قائمةٌ في تعليق ليست عقداً.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHAT_TURN = REPO_ROOT / "app/infrastructure/clients/orchestrator/chat_turn.py"
HARNESS = REPO_ROOT / "tests/test_transcript_contracts.py"


def _pipeline_stages() -> list[str]:
    """أسماء المراحل بترتيب تشغيلها في `chat_turn.chat_with_agent`.

    تُستخرَج من حلقة `for _stage in ( self._stage_x, ... ):` — المصدر الحيّ نفسه،
    فلا تتقادم قائمةٌ ثانية.
    """
    tree = ast.parse(CHAT_TURN.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.For) or not isinstance(node.iter, ast.Tuple):
            continue
        names = [
            element.attr
            for element in node.iter.elts
            if isinstance(element, ast.Attribute) and element.attr.startswith("_stage_")
        ]
        if len(names) == len(node.iter.elts) and names:
            return names
    return []


def _harness_sets() -> tuple[list[str], dict[str, str]]:
    """يقرأ `_DETERMINISTIC_STAGES` و`_LLM_DEPENDENT_STAGES` من المُشغِّل."""
    tree = ast.parse(HARNESS.read_text(encoding="utf-8"))
    covered: list[str] = []
    excluded: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not node.targets:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if target.id == "_DETERMINISTIC_STAGES" and isinstance(node.value, ast.Tuple):
            covered = [
                element.value
                for element in node.value.elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            ]
        elif target.id == "_LLM_DEPENDENT_STAGES" and isinstance(node.value, ast.Dict):
            for key, value in zip(node.value.keys, node.value.values, strict=False):
                if isinstance(key, ast.Constant) and isinstance(value, ast.Constant):
                    excluded[str(key.value)] = str(value.value)
    return covered, excluded


def main() -> int:
    failures: list[str] = []

    pipeline = _pipeline_stages()
    if not pipeline:
        print("❌ تعذّر استخراج سلسلة المراحل من chat_turn.py — تغيّرت بنية الحلقة؟")
        return 1

    covered, excluded = _harness_sets()
    if not covered:
        print("❌ تعذّر قراءة _DETERMINISTIC_STAGES من مُشغِّل العقود.")
        return 1

    for stage in pipeline:
        if stage in covered or stage in excluded:
            continue
        failures.append(
            f"المرحلة {stage!r} تعمل في دور الطالب ولا يبلغها مُشغِّل العقود ولا هي "
            f"مُستثناة بسبب. أضِفها إلى _DETERMINISTIC_STAGES، أو إلى "
            f"_LLM_DEPENDENT_STAGES مع سببٍ منطوق."
        )

    # الاتجاه الآخر: اسمٌ في المُشغِّل لم يعد موجوداً في السلسلة = حراسةُ وهمٍ.
    for stage in [*covered, *excluded]:
        if stage not in pipeline:
            failures.append(
                f"المُشغِّل يذكر {stage!r} وليست في سلسلة chat_turn.py — "
                f"أُعيدت تسميتها أو حُذفت، فالحراسة تخصّ مرحلةً لا وجود لها."
            )

    # الاستثناء بلا سبب ليس استثناءً.
    for stage, reason in excluded.items():
        if not reason.strip():
            failures.append(f"المرحلة {stage!r} مُستثناة بسببٍ فارغ (D-206·L11).")

    if failures:
        print("❌ تغطية عقود الترانسكريبت ناقصة (ISS-148):\n")
        for failure in failures:
            print(f"  • {failure}")
        return 1

    print(
        f"✅ تغطية عقود الترانسكريبت: {len(covered)}/{len(pipeline)} مرحلة محروسة، "
        f"{len(excluded)} مُستثناة بسببٍ منطوق."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
