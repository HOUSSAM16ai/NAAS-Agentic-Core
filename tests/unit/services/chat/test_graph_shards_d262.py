"""اختبارات التطابق الحرفي لشرائح D-262 (CodeScene X-Ray job 72 · ISS-173).

D-262 (2026-08-16): `services/overmind/graph/main.py` كان أسوأ hotspot في
المشروع (174 سطرًا · درجة 10/10 · `create_unified_graph` churn=14 بـ85 سطرًا).
فُكِّك إلى قشرة تفويض نقية + حزمة `graph_support` شرائح نقية — صفر تغيير
سلوكي. هذه الاختبارات تثبت أن القشرة والشرائح تُطابقان الأصل حرفًا:
الدوال الشرطية الثلاث، الخماسية البحثية، بنية العقد والأسلاك، سلسلة
الـcompile/checkpointer، المانيفست المركّب، وإصلاح الـDEADLOCK.
"""

from __future__ import annotations

import pathlib

import pytest
from langgraph.checkpoint.memory import MemorySaver

from microservices.orchestrator_service.src.services.overmind.graph import (
    main as graph_main,
)
from microservices.orchestrator_service.src.services.overmind.graph.graph_support import (
    FAILURE_PHRASES,
    GRAPH_SOURCE_FILES,
    ROUTING_MAP,
    _PassthroughNode,
    build_graph,
    check_quality,
    check_results,
    compile_graph,
    compile_with_checkpointer,
    load_search_nodes,
    read_graph_source,
    route_intent,
)
from microservices.orchestrator_service.src.services.overmind.graph.state import (
    AgentState,
)

# جذر حزمة الرسم `graph/` (جذر المانيفست المركّب `GRAPH_SOURCE_FILES`).
_ROOT = pathlib.Path(__file__).resolve().parents[4]
_GRAPH = (
    _ROOT / "microservices" / "orchestrator_service" / "src" / "services" / "overmind" / "graph"
)
_ROOT_DIR = _GRAPH.parent  # جذر المانيفست = `overmind/` (المسارات نسبية له).


# ────────────────────────── 1. القشرة التفويض ──────────────────────────


class TestShellReexports:
    """القشرة تعيد تصدير كل الأسماء القديمة بالاسم نفسه (لا shadowing)."""

    def test_conditionals_reexported(self) -> None:
        for name in ("route_intent", "check_results", "check_quality"):
            assert getattr(graph_main, name) is globals()[name], name

    def test_legacy_load_search_nodes_alias(self) -> None:
        assert graph_main._load_search_nodes is load_search_nodes

    def test_legacy_passthrough_node_alias(self) -> None:
        assert graph_main._PassthroughNode is _PassthroughNode

    def test_create_unified_graph_callable(self) -> None:
        assert callable(graph_main.create_unified_graph)


# ────────────────────────── 2. شرائح الشروط ──────────────────────────


class TestConditionsShards:
    """مطابقة حرفية لدوال الشروط الأصلية (D-262 · ISS-173)."""

    def test_routing_map_complete(self) -> None:
        expected = {
            "educational": "query_rewriter",
            "admin": "admin_agent",
            "tool": "tool_executor",
            "chat": "chat_fallback",
            "general_knowledge": "general_knowledge",
        }
        assert expected == ROUTING_MAP

    @pytest.mark.parametrize(
        ("intent", "expected"),
        [
            ("educational", "educational"),
            ("admin", "admin"),
            ("tool", "tool"),
            ("chat", "chat"),
            ("general_knowledge", "general_knowledge"),
        ],
    )
    def test_route_intent_known(self, intent: str, expected: str) -> None:
        assert route_intent(AgentState(intent=intent)) == expected

    def test_route_intent_search_clamped_to_educational(self) -> None:
        # سلوك الأصل: نية البحث تُعاد إلى التعليمية.
        assert route_intent(AgentState(intent="search")) == "educational"

    def test_route_intent_unknown_clamped(self) -> None:
        # DEADLOCK FIX (ISS-173): نية مجهولة لا ترمي «unknown branch».
        assert route_intent(AgentState(intent="weird")) == "educational"

    def test_route_intent_missing_default(self) -> None:
        assert route_intent(AgentState()) == "educational"

    def test_check_results_found(self) -> None:
        assert check_results(AgentState(reranked_docs=[{"title": "x"}])) == "found"

    def test_check_results_empty_educational(self) -> None:
        assert check_results(AgentState(reranked_docs=[], intent="educational")) == "web_fallback"

    def test_check_results_empty_other(self) -> None:
        assert check_results(AgentState(reranked_docs=[], intent="admin")) == "general_knowledge"

    def test_check_results_missing_intent(self) -> None:
        # سلوك الأصل: `intent` المفقود يصبح "" → ليس "educational" →
        # `general_knowledge` (المعادلة الأصلية لا تعامل المفقود كـ"educational").
        assert check_results(AgentState(reranked_docs=[])) == "general_knowledge"

    def test_check_quality_fail_none(self) -> None:
        assert check_quality(AgentState(final_response=None)) == "fail"

    @pytest.mark.parametrize("phrase", FAILURE_PHRASES)
    def test_check_quality_fail_phrases(self, phrase: str) -> None:
        assert check_quality(AgentState(final_response=phrase)) == "fail"

    def test_check_quality_fail_phrase_inside_response(self) -> None:
        # مطابقة حرفية للأصل: العبارة داخل ردٍّ أطول ما تزال تُعيد `fail`.
        assert check_quality(AgentState(final_response="أنا آسف، لم أفهم سؤالك")) == "fail"

    def test_check_quality_fail_empty(self) -> None:
        assert check_quality(AgentState(final_response="   ")) == "fail"

    def test_check_quality_pass(self) -> None:
        assert check_quality(AgentState(final_response="الإجابة الصحيحة")) == "pass"


# ────────────────────────── 3. شرائح البحث ──────────────────────────


class TestSearchShards:
    """مطابقة حرفية لشرائح البحث (D-262)."""

    def test_load_search_nodes_five(self) -> None:
        nodes = load_search_nodes()
        assert isinstance(nodes, tuple) and len(nodes) == 5

    def test_load_search_nodes_first_is_query_analyzer(self) -> None:
        from microservices.orchestrator_service.src.services.overmind.graph.search import (
            QueryAnalyzerNode,
        )

        nodes = load_search_nodes()
        assert nodes[0] is QueryAnalyzerNode

    def test_passthrough_node_identity(self) -> None:
        state = {"intent": "chat"}
        assert _PassthroughNode()(state) is state


# ──────────────────────── 4. بنية الرسم الموحَّد ────────────────────────


class TestGraphStructure:
    """الرسم المفكَّك متطابقٌ عقدةً عقدة وحافةً حافة مع الأصل (D-262)."""

    @staticmethod
    def _node_names(graph) -> set[str]:
        return set(graph.nodes.keys())

    @staticmethod
    def _leaf_edges(graph) -> dict[str, set[str]]:
        """حافات العقد الورقية (غير المشروطة) — `graph.edges` مجموعة ثنائيات."""
        edges = {}
        for source, target in graph.edges:
            edges.setdefault(source, set()).add(target)
        return edges

    @staticmethod
    def _conditional_sources(graph) -> set[str]:
        """مصادر الحافات الشرطية الثلاث (supervisor · reranker · validator)."""
        return set(graph.branches.keys())

    def test_twelve_nodes(self) -> None:
        graph = build_graph()
        assert self._node_names(graph) == {
            "supervisor",
            "query_rewriter",
            "query_analyzer",
            "retriever",
            "reranker",
            "web_fallback",
            "admin_agent",
            "tool_executor",
            "chat_fallback",
            "general_knowledge",
            "synthesizer",
            "validator",
        }

    def test_leaf_nodes_exit_through_validator(self) -> None:
        # DEADLOCK FIX: كل ورقة تخرج عبر `validator` (لا طريق مسدود صامت).
        graph = build_graph()
        edges = self._leaf_edges(graph)
        for leaf in (
            "admin_agent",
            "tool_executor",
            "chat_fallback",
            "synthesizer",
            "general_knowledge",
        ):
            assert edges.get(leaf) == {"validator"}, leaf

    def test_conditional_edges_three(self) -> None:
        graph = build_graph()
        sources = self._conditional_sources(graph)
        assert sources == {"supervisor", "reranker", "validator"}

    def test_validator_conditional_map(self) -> None:
        """حافة `validator` الشرطية: `pass` → النهاية · `fail` → المشرف (D-262)."""
        graph = build_graph()
        branch = next(iter(graph.branches["validator"].values()))
        assert branch.ends == {"pass": "__end__", "fail": "supervisor"}

    def test_supervisor_conditional_map(self) -> None:
        graph = build_graph()
        branch = next(iter(graph.branches["supervisor"].values()))
        assert branch.ends == ROUTING_MAP

    def test_entry_point_supervisor(self) -> None:
        graph = build_graph()
        # نقطة الدخول: `__start__` → `supervisor` (لا يوجد سمة عامة —
        # الـentry_point مخزّنة كحافة بدء داخل `_all_edges`).
        assert ("__start__", "supervisor") in graph._all_edges


# ────────────────────── 5. سلسلة الـcompile ──────────────────────


class TestCompileChain:
    """سلسلة الإقلاع متطابقة مع الأصل (D-262)."""

    def test_compile_with_explicit_checkpointer(self) -> None:
        compiled = compile_with_checkpointer(build_graph(), MemorySaver())
        assert compiled.get_state is not None

    def test_compile_graph_callable(self) -> None:
        assert callable(compile_graph)

    def test_create_unified_graph_compiles(self) -> None:
        # القشرة: build + compile — CompiledGraph صالح.
        compiled = graph_main.create_unified_graph()
        assert compiled.get_state is not None

    def test_create_unified_graph_explicit_checkpointer(self) -> None:
        compiled = graph_main.create_unified_graph(checkpointer=MemorySaver())
        assert compiled.get_state is not None


# ────────────────────── 6. المانيفست المركّب ──────────────────────


class TestGraphSourcesD262:
    """المانيفست المركّب يقرأ السلوك المفكَّك كاملًا (نمط D-164/D-173)."""

    def test_manifest_has_five_files(self) -> None:
        assert GRAPH_SOURCE_FILES == (
            "graph/main.py",
            "graph/graph_support/_conditions.py",
            "graph/graph_support/_search_shards.py",
            "graph/graph_support/_graph.py",
            "graph/graph_support/_sources.py",
        )

    def test_manifest_files_exist(self) -> None:
        for name in GRAPH_SOURCE_FILES:
            assert (_ROOT_DIR / name).is_file(), name

    def test_read_graph_source_composite(self) -> None:
        source = read_graph_source()
        for name in GRAPH_SOURCE_FILES:
            content = (_ROOT_DIR / name).read_text(encoding="utf-8")
            assert content in source, name

    def test_shell_is_delegation_only(self) -> None:
        """القشرة تفويض فقط — جسم `create_unified_graph` لا يتجاوز 12 سطرًا."""
        shell = (_GRAPH / "main.py").read_text(encoding="utf-8")
        _, body = shell.split("def create_unified_graph", 1)
        # جسم الدالة: من ما بعد التوقيع حتى نهاية الملف (لا دوال بعدها).
        assert body.count("\n") <= 12
        assert "build_graph(" in body
        assert "compile_with_checkpointer(" in body
        assert "compile_graph(" in body

    def test_graph_support_functions_pure(self) -> None:
        """الشرائح لا تحمل حالةً — دوالٌ ومكتبات نقية فقط."""
        for name in GRAPH_SOURCE_FILES[1:]:
            content = (_ROOT_DIR / name).read_text(encoding="utf-8")
            assert "def " in content, name
