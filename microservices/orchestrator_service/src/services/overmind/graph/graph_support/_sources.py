"""GRAPH_SOURCE_FILES — المانيفست المركّب (D-262 — نمط D-164/D-173/D-252/D-255/D-258/D-260/D-261).

أي بوابة/اختبار يقرأ مصدر الرسم الموحَّد `services/overmind/graph/main.py`
نصًّيا (runtime truth · حراس العقيدة) يقرأ المركّب عبر `read_graph_source()` —
إضافة شريحةٍ جديدة = سطرٌ واحد هنا.

**لماذا هذا المانيفست موجود:** كان الرسم الموحَّد (12 عقدة + شرائط الشروط +
تحميل البحث + سلسلة الـcompile) متكدّسًا في `main.py` (174 سطرًا · درجة 10/10
· `create_unified_graph` churn=14) — hotspot في CodeScene X-Ray job 72
(D-262 · ISS-173). فُكِّك إلى قشرة تفويض + حزمة شرائح نقية هنا، والمانيفست
يضمن أن كل حاجزٍ نصي يقرأ السلوك المفكَّك كاملًا لا القشرة فقط.
"""

from __future__ import annotations

from pathlib import Path

# حزمة الشرائح: microservices/orchestrator_service/src/services/overmind/graph/graph_support
# _SRC = جذر `graph/` (parents: graph_support → graph → overmind → services).
_SRC = Path(__file__).resolve().parents[2]

GRAPH_SOURCE_FILES: tuple[str, ...] = (
    # القشرة: الرسم الموحَّد — تفويض فقط (D-262).
    "graph/main.py",
    # D-262 (2026-08-16): شرائح الشروط الحتمية (`route_intent` مع DEADLOCK
    # FIX · `check_results` · `check_quality` + `ROUTING_MAP` و`FAILURE_PHRASES`).
    "graph/graph_support/_conditions.py",
    # D-262 (2026-08-16): شرائح البحث (تحميل متسامح + البديل الآمن).
    "graph/graph_support/_search_shards.py",
    # D-262 (2026-08-16): تسجيل العقد الاثنتي عشرة + الأسلاك + سلسلة الـcompile.
    "graph/graph_support/_graph.py",
    # D-262 (2026-08-16): هذا المانيفست نفسه.
    "graph/graph_support/_sources.py",
)


def read_graph_source() -> str:
    """المصدر المركَّب للرسم الموحَّد (للبوابات النصية)."""
    return "\n".join((_SRC / name).read_text(encoding="utf-8") for name in GRAPH_SOURCE_FILES)
