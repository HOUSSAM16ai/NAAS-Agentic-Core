"""D-171 (ISS-132) — هوية الإدمن تعبر الرسم الـ13-node.

الكارثة: أداة الإدمن كانت **تُنفَّذ** (`TOOL EXECUTED`) ثم يرفضها `ValidateAccessNode`
بـ `ADMIN_ACCESS_DENIED` لسببين بنيويين منذ D-025:
1. `AgentState` لا يُصرّح `is_admin/user_role/scope` — LangGraph يُسقط المفاتيح
   غير المُصرَّحة فلا تصل عبر `AdminAgentNode` إلى الرسم الفرعي الإداري.
2. handler `/api/chat/messages` كان يتجاهل `_jwt_payload` ولا يمرّر
   `admin_payload` إلى `_run_chat_langgraph`.

الإصلاح: تصريح الحقول الثلاثة في `AgentState` + تمرير الحمولة **فقط** حين
`_is_admin_payload` (least-privilege + fail-closed — نمط D-169: نقل حقيقة
مُتحقَّقة من JWT موقَّع، لا تصعيد).
"""

from __future__ import annotations

from pathlib import Path

from microservices.orchestrator_service.src.api.api_sources import read_api_source
from microservices.orchestrator_service.src.api.identity_access import (
    _coerce_admin_state,
    _is_admin_payload,
    _merge_admin_inputs,
)
from microservices.orchestrator_service.src.services.overmind.graph.admin import (
    _is_admin_state,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
# D-173 Stage 2c: graph/main.py فُكِّك إلى شرائح (dspy_compat/state/nodes) —
# نقرأ المصدر المُركَّب عبر المانيفست فتصمد التأكيدات النصية بعد النقل الحرفي.
from microservices.orchestrator_service.src.services.overmind.graph.graph_sources import (
    read_graph_source,
)

GRAPH_MAIN = read_graph_source()
ROUTES_SRC = read_api_source()


class TestAgentStateDeclaresAdminIdentity:
    """الفجوة 1: LangGraph يُسقط المفاتيح غير المُصرَّحة في `AgentState`."""

    def test_agent_state_declares_all_admin_fields(self):
        for field in ("is_admin: bool", "user_role: str", "scope: str"):
            assert field in GRAPH_MAIN, f"D-171 broken: AgentState lost `{field}` (ISS-132)"

    def test_agent_state_import_carries_annotations(self):
        from microservices.orchestrator_service.src.services.overmind.graph.main import (
            AgentState,
        )

        for key in ("is_admin", "user_role", "scope"):
            assert key in AgentState.__annotations__, (
                f"D-171 broken: AgentState.__annotations__ misses {key!r} — "
                "LangGraph channels drop it silently"
            )

    def test_coerced_admin_state_keys_subset_of_agent_state(self):
        """عقد التكافؤ: كل مفتاح يحقنه `_coerce_admin_state` مُصرَّح في `AgentState`."""
        from microservices.orchestrator_service.src.services.overmind.graph.main import (
            AgentState,
        )

        coerced = _coerce_admin_state({"is_admin": True, "role": "admin", "scope": "admin:tools"})
        missing = [k for k in coerced if k not in AgentState.__annotations__]
        assert not missing, (
            f"D-171 broken: `_coerce_admin_state` injects {missing} — undeclared in AgentState"
        )


class TestHandlerPassesAdminPayload:
    """الفجوة 2: handler `/api/chat/messages` كان يتجاهل `_jwt_payload`."""

    def test_handler_gates_payload_on_is_admin(self):
        assert (
            "_admin_payload = _jwt_payload if _is_admin_payload(_jwt_payload) else None"
            in ROUTES_SRC
        ), "D-171 broken: handler no longer gates admin payload on _is_admin_payload"

    def test_handler_forwards_admin_payload_to_engine(self):
        assert "admin_payload=_admin_payload" in ROUTES_SRC, (
            "D-171 broken: _run_chat_langgraph call lost admin_payload=_admin_payload"
        )


class TestFailClosedBehaviour:
    """least-privilege: المستخدم العادي لا يحمل أي مفاتيح إدارة في الحالة."""

    def test_regular_jwt_is_not_admin(self):
        assert _is_admin_payload({"sub": "7", "roles": ["USER"]}) is False

    def test_admin_jwt_is_admin(self):
        assert _is_admin_payload({"sub": "1", "is_admin": True}) is True

    def test_merged_admin_inputs_pass_validate_access(self):
        inputs = _merge_admin_inputs(
            {"query": "كم عدد ملفات بايثون؟"}, {"is_admin": True, "role": "admin"}
        )
        assert _is_admin_state(inputs) is True

    def test_unmerged_inputs_fail_validate_access(self):
        assert _is_admin_state({"query": "كم عدد ملفات بايثون؟"}) is False

    def test_none_payload_merges_nothing(self):
        base = {"query": "سؤال عادي"}
        assert _merge_admin_inputs(base, None) == base
