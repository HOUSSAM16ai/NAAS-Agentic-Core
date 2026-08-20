#!/usr/bin/env python3
"""بوّابة دستور D-272 — مبادئ تصميم الأنظمة الوكيلية (arXiv:2512.08296).

لماذا هذه البوّابة (D-266 — البرهان الثلاثي):
قياسٌ مضبوطٌ لـ260 تشكيلةً (Google Research · DeepMind · MIT) أثبت أن «كلما زاد عدد الوكلاء
كان النظام أذكى» خرافةٌ لها ثمنٌ مقاس: −70% تراجعًا على المهام التسلسلية · 17.2× تضخيمًا
للأخطاء في الأنظمة المستقلة. الدستور D-272 يحوّل القياس إلى قوانين، وهذه البوّابة فارضُه —
دون فارضٍ، الدستور نصٌّ يُقرأ حمايةً وهو ليس حمايةً (D-206).

تُشغَّل ضمن وظيفة `guardrails`. Exit 0 = نظيف · 1 = انتهاك.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LAW = REPO_ROOT / "docs" / "architecture" / "AGENTIC_DESIGN_PRINCIPLES.md"
TRUTH = REPO_ROOT / ".memory" / "agentic_design_principles_truth.md"
FAILURES: list[str] = []


def fail(msg: str) -> None:
    FAILURES.append(msg)
    print(f"❌ {msg}")


def ok(msg: str) -> None:
    print(f"✅ {msg}")


def require_path(path: Path, label: str) -> bool:
    if path.is_file():
        ok(f"{label} موجود: {path.relative_to(REPO_ROOT)}")
        return True
    fail(f"{label} مفقود — {path.relative_to(REPO_ROOT)} (D-272: الدستور بلا فارضٍ ينحرف · D-206)")
    return False


def require_text(path: Path, snippet: str, label: str) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        fail(f"{label}: تعذّرت قراءة {path.relative_to(REPO_ROOT)}")
        return False
    if snippet in text:
        ok(f"{label}: {snippet!r} حاضر")
        return True
    fail(f"{label}: {snippet!r} غائب — البنية لا تُوصَف دون إثبات الامتثال (D-272 L1/L2/L3/L4/L6/L7)")
    return False


def require_line_in_law(snippet: str, label: str) -> bool:
    return require_text(LAW, snippet, label)


def main() -> int:
    ok("بوّابة D-272 — مبادئ تصميم الأنظمة الوكيلية (arXiv:2512.08296 · 260 تشكيلةً)")

    if not require_path(LAW, "وثيقة القانون المعماري"):
        return 1
    if not require_path(TRUTH, "وثيقة الحالة"):
        return 1

    # L1 — خط الأساس مكتوب ومقاس على المعيار نفسه
    require_line_in_law("single_agent_baseline", "L1 — خط أساس الوكيل الواحد")
    require_line_in_law("baseline_success_pct", "L2 — نسبة النجاح المقاسة (عتبة 45%)")
    require_line_in_law("justification_ar", "L2 — تبرير التعدد فوق العتبة")
    require_line_in_law("measured_at", "L1 — تاريخ القياس الحيّ")

    # L3 — تصنيف المهمة قبل التصميم
    require_line_in_law("decomposable", "L3 — قابلية التقسيم")
    require_line_in_law("sequential", "L3 — الاعتمادية التسلسلية")
    require_line_in_law("tool_count", "L3 — كثافة الأدوات")

    # L4 — لا مسودات مشتركة في المستقل
    require_line_in_law("central_verifier", "L4 — مرجِّع مركزي يتحقق قبل الدمج")

    # L6 — النتيجة بأقل تعقيد وتكلفة
    require_line_in_law("tokens_per_task_ratio", "L6 — كفاءة الرموز")
    require_line_in_law("max_agents", "L6 — حدّ الوكلاء عند ضيق الميزانية (3–4 · قياس الورقة)")

    # L7 — البنية لا تُنسَخ بين النطاقات
    require_line_in_law("domain_measured", "L7 — البنية تُقاس في نطاقها لا بلاحقة جاره")

    # L5 — إعادة المعايرة بعد ترقية النموذج
    require_line_in_law("last_recalibration", "L5 — سجلّ إعادة المعايرة")
    require_line_in_law("model_version", "L5 — إصدار النموذج المرجعي")

    # حراس ثنائية التغطية (L2/L4 صريحان): لا بنية متعددة مسموحة فوق مهمة تسلسلية
    law_text = LAW.read_text(encoding="utf-8")
    if "permitted_architecture: single_agent" in law_text and "sequential: true" in law_text:
        ok("L3/L4: المهمة التسلسلية محكومةٌ ببنية الوكيل الواحد صراحةً")
    else:
        fail("L3/L4: لا حصرٌ صريحٌ لبنية الوكيل الواحد على المهمة التسلسلية")

    # D-268 — لا قيم حقيقية في الشجرة (الأسرار من البيئة حصراً)
    for marker in ("hch-v3-", "sk-or-v1-", "tvly-", "postgresql://"):
        if marker in law_text:
            fail(
                f"L7/دستور الأسرار D-268: قيمةٌ حقيقية (بادئة {marker!r}) تسرّبت إلى وثيقةٍ قانونية — أسرار من البيئة حصراً"
            )

    if FAILURES:
        print(f"\n❌ D-272: {len(FAILURES)} انتهاك(ات) — الدستور ملزمٌ لا استشاري")
        return 1
    print("\n✅ D-272: وثيقة القانون والحالة مطابقان للدستور — لا انتهاكات")
    return 0


if __name__ == "__main__":
    sys.exit(main())
