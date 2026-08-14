"""ORCHESTRATOR_AGENT_SOURCE_FILES — manifest (D-253، نمط D-164/D-173/D-252).

أي بوّابة/اختبار يقرأ مصدر وكيل التنسيق `OrchestratorAgent` نصيًا
(حراس العقيدة · legacy noop · canonical/ownership fences) يقرأ
المُركَّب عبر `read_orchestrator_agent_source()` — إضافة شريحة جديدة =
سطر واحد هنا.

**لماذا هذه البوّابة موجودة:** كان كل منطق الدور الواحد (استخراج فلاتر البحث،
بناء الشرح، المحادثة الاحتياطية، تاريخ السياق) داخل `agents/orchestrator.py`
— hotspot بتردد تغييرٍ عالٍ وتعقيدٍ متجاوز حد الدستور (D-253). فُكِّك إلى هذه
الحزمة، والمانيفست يضمن أن كل حاجزٍ نصي يقرأ السلوك المفكك كاملًا لا القشرة
فقط.
"""

from __future__ import annotations

from pathlib import Path

_AGENTS = Path(__file__).resolve().parents[2]

ORCHESTRATOR_AGENT_SOURCE_FILES: tuple[str, ...] = (
    # القشرة: الاستقبال + كشف النيّة + التفويض (D-253).
    "agents/orchestrator.py",
    # D-253 (2026-08-14): شرائح دورة الدور — الشرح التربوي.
    "agents/orchestrator_support/explanation.py",
    # D-253 (2026-08-14): شرائح دورة الدور — استخلاص فلاتر البحث.
    "agents/orchestrator_support/search_params.py",
    # D-253 (2026-08-14): شرائح دورة الدور — المحادثة الاحتياطية (Smart Tutor).
    "agents/orchestrator_support/chat_fallback.py",
    # D-253 (2026-08-14): شرائح دورة الدور — استرجاع المحتوى (القلب).
    "agents/orchestrator_support/content_retrieval.py",
    # D-253 (2026-08-14): شرائح دورة الدور — سياق التاريخ (المرجعية والموجز).
    "agents/orchestrator_support/history_context.py",
)


def read_orchestrator_agent_source() -> str:
    """المصدر المُركَّب لوكيل التنسيق (للبوابات النصية)."""
    return "\n".join(
        (_AGENTS / name).read_text(encoding="utf-8") for name in ORCHESTRATOR_AGENT_SOURCE_FILES
    )
