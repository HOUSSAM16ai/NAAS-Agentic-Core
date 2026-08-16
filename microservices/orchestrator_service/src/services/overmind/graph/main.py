"""
حزمة الرسم البياني لوحدة Overmind — قشرة تفويض نقية (D-262).
D-262 (2026-08-16 — CodeScene X-Ray job 72): `create_unified_graph` كانت أسوأ
نقطةٍ ساخنة في الملف (85 سطرًا · تردد تغيير 14 · ملف بأكمله hotspot 10/10).
فُكِّكت إلى قشرة تفويض فوق حزمة `graph.graph_support` — **صفر تغيير سلوكي**:
كل الأسماء القديمة (nodes · state · الدوال الشرطية · تحميل البحث) أعيد تصديرها
بالاسم نفسه، والرسم البياني المُجمَّع متطابق عقدةً عقدة وحافةً حافة (D-262).
"""

from __future__ import annotations

import logging

from .dspy_compat import dspy  # noqa: F401 — re-export (graph.main.dspy patchable)

# الدوال الشرطية — شرائح نقية (D-262) أعيد تصديرها بأسمائها القديمة.
from .graph_support import (  # noqa: F401
    check_quality,
    check_results,
    route_intent,
)
from .graph_support._graph import build_graph, compile_graph, compile_with_checkpointer

# البدائل الآمنة لشرائح البحث — تبقى متاحة للمستوردين القدامى (D-262).
from .graph_support._search_shards import _PassthroughNode  # noqa: F401
from .nodes import (  # noqa: F401 — D-173 Stage 2c re-export (D-168 late-binding)
    ChatFallbackNode,
    ChatFallbackSignature,
    IntentClassifier,
    QueryRewriterNode,
    QueryRewriterSignature,
    SupervisorNode,
    ToolExecutorNode,
    ValidatorNode,
    _configure_dspy,
)
from .state import (  # noqa: F401 — D-173 Stage 2c re-export
    ADMIN_METRIC_TRIGGERS,
    ADMIN_PATTERNS,
    ARABIC_ANAPHORA,
    ARABIC_PRONOUN_SUFFIXES,
    CHAT_INTENT_TRIGGERS,
    ELLIPTICAL_STARTERS,
    ELLIPTICAL_TERMS,
    ENGLISH_ANAPHORA,
    SHORT_QUERY_THRESHOLD,
    AgentState,
    _contains_anaphora_indicator,
    _contains_compound_indicator,
    _extract_recent_entity_anchor,
    _looks_elliptical_followup,
    _resolve_query_from_history,
    _rewrite_with_entity_anchor,
    _tokenize_query,
    build_conversation_context,
    emergency_intent_guard,
    format_conversation_history,
    get_message_content,
    get_message_role,
)

logger = logging.getLogger(__name__)


# الاسم القديم لحامِل شرائح البحث — يبقى متاحًا للمستوردين القدامى (D-262).
from .graph_support._search_shards import (
    load_search_nodes as _load_search_nodes,  # noqa: F401
)


def create_unified_graph(admin_app=None, checkpointer=None):
    """الرسم البياني الموحّد — تسلسل تفويض فقط (D-262 · صفر تغيير سلوكي)."""
    graph = build_graph(admin_app=admin_app)
    if checkpointer:
        return compile_with_checkpointer(graph, checkpointer)
    return compile_graph(graph)
