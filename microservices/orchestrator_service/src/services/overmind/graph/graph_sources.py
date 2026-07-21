"""GRAPH_SOURCE_FILES — manifest of the unified-chat-graph package (D-173 Stage 2c).

نمط D-164/D-168: `graph/main.py` (12 عقدة) فُكِّك حرفياً إلى شرائح متجاورة —
`dspy_compat.py` (شيم DSPy) + `state.py` (AgentState + ثوابت النية + مساعدات
التاريخ) + `nodes.py` (عقد الرسم + توقيعات DSPy). `main.py` يعيد تصدير كل الرموز
(noqa F401) فيبقى `graph.main.<name>` و monkeypatch فعّالَين. أي بوّابة/اختبار
يقرأ مصدر الرسم نصياً يقرأ المُركَّب عبر `read_graph_source()`.
"""

from __future__ import annotations

from pathlib import Path

_PKG = Path(__file__).resolve().parent

GRAPH_SOURCE_FILES: tuple[str, ...] = (
    "main.py",
    "dspy_compat.py",
    "state.py",
    "nodes.py",
)


def read_graph_source() -> str:
    """المصدر المُركَّب للرسم الموحَّد (للبوّابات النصية)."""
    return "\n".join((_PKG / name).read_text(encoding="utf-8") for name in GRAPH_SOURCE_FILES)
