"""تجميد سلوك توأمَي WS بالحرف — قبل تفكيكهما (ISS-155).

## لماذا هذا الملفّ موجود

`chat_ws_stategraph` (148 سطراً · cc 20) و`admin_chat_ws_stategraph` (153 · cc 23)
شبه متطابقتين: قياسٌ آليّ بـ`difflib` يُظهر أنّ الفرق **ستّة أشياء لا غير** وأنّ ~120
سطراً بينهما متطابقة **بالبايت**. وهما على وشك أن يصيرا غلافَين رفيعَين فوق مسارٍ
واحد. والقاعدة التي تحكم ذلك (Feathers): **الكود بلا اختبارات هو Legacy** — فالشبكة
تُبنى **قبل** أوّل حركة لا بعدها.

الاختبارات الخمسة القائمة في `test_orchestrator_chat_stategraph.py` تغطّي المسار
السعيد ×2 ورفض غير-الإدمن وتعقيم الخطأ. ولا تلمس: المحادثة اللاصقة · تبديل المحادثة ·
الحمولة الفاسدة · السؤال الغائب · فشل `_ensure_conversation` · `mission_type` ·
حارس الترطيب · تمرير `admin_payload` · `route_name` · `chat_scope`. وهذه العشرة هي
**بالضبط** ما يجب أن يبقى ثابتاً كي يكون ضغط الفروق الستّة في `ChatWsScope` آمناً.

## ما الذي يُجمَّد بالضبط

الترانسكريبت = تسلسل الإطارات التي بثّها المقبس **+ وسائط** كلّ نداء
`_stream_chat_langgraph` و`_emit_identity_diagnostic_log`. أي: **ما يصل الطالبَ وما
يصل المحرّك**، لا مخرَجات الرسم — فالرسم مُرقَّع بجاسوسٍ لا يبثّ شيئاً. وبذلك يقيس
العقد الدورَ نفسه لا LangGraph.

البنود «تمرير `admin_payload`» و«`route_name`» و«`chat_scope`» هي **الترميز الآليّ
للفروق الستّة**، وهي السبب الوحيد للاعتقاد بأنّ الضغط في كائنٍ واحد لا يُغيّر سلوكاً.

## لماذا golden master وليس dual-run

البروتوكول يقترح إبقاء التنفيذ القديم خلف راية. المستودع يمنع كوداً بلا مستدعٍ حيّ
(§6.8 — وKagent حُذف لهذا)، فالتجميد هنا على **ملفّ مرجعي مُلتزَم**: نفس برهان
التكافؤ 100٪ بلا كودٍ ميت، وأيّ انحراف يظهر **diff مقروءاً** في المراجعة بدل أن
يُبتلع (D-237 · البند ٦).

**قاعدة البرهان:** هذا الملفّ والمرجع يُولَّدان على الكود **قبل** النقل، والتزام
النقل يجب أن يترك `chat_ws_transcript_golden.json` **بلا تغيّر بايتٍ واحد**.

## قاعدة late-binding (D-168)

كلّ ترقيعٍ هنا يمرّ بـ`patch_caller` من `caller_modules.py`، لا بـ
`monkeypatch.setattr(routes, …)`. بعد النقل تُحَلّ الأسماء من globals الوحدة الجديدة
بينما `routes` ما زال يُعيد تصديرها — فالترقيع المباشر ينجح **ولا يفعل شيئاً**،
والاختبار يمسّ قاعدة بيانات حقيقية بدل أن يفشل.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from microservices.orchestrator_service.main import app
from microservices.orchestrator_service.src.core.config import get_settings
from tests.microservices.caller_modules import patch_caller

GOLDEN_FILE = Path(__file__).parent / "fixtures" / "chat_ws_transcript_golden.json"

CUSTOMER_URL = "/api/chat/ws"
ADMIN_URL = "/admin/api/chat/ws"

#: مُعرّف المحادثة الذي تُرجعه `_ensure_conversation` المزيّفة لكلّ نطاق.
_SCOPE_CONVERSATION_ID = {"customer": 123, "admin": 456}

#: تاريخٌ ثابت تُرجعه `_ensure_conversation` كي يُقاس حارس الترطيب على مُدخَلٍ معروف.
_DB_HISTORY: list[dict[str, str]] = [
    {"role": "user", "content": "سؤال سابق"},
    {"role": "assistant", "content": "جواب سابق"},
]


def _token(scope: str) -> str:
    claims: dict[str, object] = {"sub": "1", "user_id": 1}
    if scope == "admin":
        claims |= {"role": "admin", "is_admin": True}
    return jwt.encode(claims, get_settings().SECRET_KEY, algorithm="HS256")


def _url(scope: str) -> str:
    return f"{ADMIN_URL if scope == 'admin' else CUSTOMER_URL}?token={_token(scope)}"


def _canonical(value: object) -> object:
    """يحوّل قيمةً مُسجَّلة إلى شكلٍ قابل للمقارنة بالبايت.

    ما ليس JSON (مقبسٌ · رسمٌ مزيّف · دالّة) يُختزَل إلى اسم نوعه: العقد يقيس
    **بنية** الوسائط لا هويّة الكائنات العابرة، وهويّة `admin_payload` تُفحَص
    صراحةً في اختبارها الخاصّ لا عبر المرجع.
    """
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, dict):
        return {str(k): _canonical(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, list | tuple):
        return [_canonical(item) for item in value]
    return f"<{type(value).__name__}>"


class _Recorder:
    """يجمع ما بثّه المقبس وما وصل المحرّك في دورٍ واحد."""

    def __init__(self) -> None:
        self.stream_calls: list[dict[str, object]] = []
        self.identity_calls: list[dict[str, object]] = []
        #: الوسائط الخام (بلا تحويل) — لفحوص الهويّة التي لا يعبّر عنها المرجع.
        self.raw_stream_calls: list[dict[str, Any]] = []

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _fake_stream(_websocket: object, **kwargs: Any) -> None:
            self.raw_stream_calls.append(kwargs)
            self.stream_calls.append(_canonical(kwargs))  # type: ignore[arg-type]

        def _fake_identity(**kwargs: Any) -> None:
            self.identity_calls.append(_canonical(kwargs))  # type: ignore[arg-type]

        patch_caller(monkeypatch, "_stream_chat_langgraph", _fake_stream)
        patch_caller(monkeypatch, "_emit_identity_diagnostic_log", _fake_identity)


def _install_conversation(
    monkeypatch: pytest.MonkeyPatch,
    scope: str,
    *,
    raises: BaseException | None = None,
) -> list[dict[str, object]]:
    """يُرقّع `_ensure_conversation` ويعيد سجلّ استدعاءاتها."""
    seen: list[dict[str, object]] = []

    async def _fake_ensure(**kwargs: Any) -> tuple[int, list[dict[str, str]]]:
        seen.append(
            {
                "chat_scope": kwargs.get("chat_scope"),
                "user_id": kwargs.get("user_id"),
                "question": kwargs.get("question"),
                "requested_conversation_id": kwargs.get("requested_conversation_id"),
            }
        )
        if raises is not None:
            raise raises
        requested = kwargs.get("requested_conversation_id")
        resolved = requested if isinstance(requested, int) else _SCOPE_CONVERSATION_ID[scope]
        return resolved, list(_DB_HISTORY)

    patch_caller(monkeypatch, "_ensure_conversation", _fake_ensure)
    return seen


def _drain(ws: object, count: int) -> list[dict[str, object]]:
    """يقرأ عدداً محدّداً من الإطارات — الجاسوس لا يبثّ، فالعدد معروفٌ سلفاً."""
    return [ws.receive_json() for _ in range(count)]  # type: ignore[attr-defined]


# ─────────────────────────────────────────────────────────────────────────────
# السيناريوهات — جدولٌ لا سلسلة `elif`
#
# كلّ سيناريو رسالةٌ واحدة أو أكثر تُرسَل على المقبس، وكم إطاراً يُنتظَر بعد كلٍّ.
# الجدول يجعل «ما الذي يُختبَر» قابلاً للقراءة في مكانٍ واحد، ويجعل إضافة حالةٍ
# سطراً لا فرعاً — وهو نفس منطق `SCENARIOS` كقائمةٍ مُصرَّحة (L12).
# ─────────────────────────────────────────────────────────────────────────────

#: `{اسم السيناريو: (الرسائل المُرسَلة بالترتيب, هل تفشل `_ensure_conversation`؟)}`
#: الرسالة قد تكون أيّ JSON — قائمةٌ مثلاً تُمثّل «حمولة غير قاموسية».
_SCENARIO_MESSAGES: dict[str, tuple[list[object], bool]] = {
    "sticky_conversation": ([{"question": "الأوّل"}, {"question": "الثاني"}], False),
    "conversation_switch": (
        [{"question": "الأوّل"}, {"question": "الثاني", "conversation_id": 999}],
        False,
    ),
    # بعد إطار الخطأ تُرسَل رسالةٌ صالحة: المقبس يجب أن يبقى حيّاً.
    "invalid_payload": ([[1, 2, 3], {"question": "بعد الخطأ"}], False),
    "missing_question": ([{"foo": 1}, {"question": "بعد الخطأ"}], False),
    "ensure_conversation_raises": ([{"question": "سؤال"}], True),
    "mission_type_top_level": ([{"question": "سؤال", "mission_type": "research"}], False),
    "mission_type_from_metadata": (
        [{"question": "سؤال", "metadata": {"mission_type": "from_metadata"}}],
        False,
    ),
    "mission_type_both_top_level_wins": (
        [{"question": "سؤال", "mission_type": "top", "metadata": {"mission_type": "nested"}}],
        False,
    ),
    "hydration_guard_falls_back": (
        [{"question": "سؤال", "context_messages": [{"role": "user", "c": "x"}]}],
        False,
    ),
    "client_context_present": ([{"question": "سؤال", "context": {"session_id": "sess-9"}}], False),
}

SCENARIOS: tuple[str, ...] = tuple(_SCENARIO_MESSAGES)


def _run_scenario(monkeypatch: pytest.MonkeyPatch, scope: str, name: str) -> dict[str, object]:
    """يقود سيناريو واحداً على مقبسٍ واحد ويُرجِع ترانسكريبته."""
    messages, ensure_fails = _SCENARIO_MESSAGES[name]

    recorder = _Recorder()
    recorder.install(monkeypatch)
    ensure_calls = _install_conversation(
        monkeypatch,
        scope,
        raises=HTTPException(status_code=409, detail="محادثة مقفلة") if ensure_fails else None,
    )

    if name == "hydration_guard_falls_back":

        def _boom(_incoming: object) -> list[dict[str, str]]:
            raise RuntimeError("انهيار الترطيب")

        patch_caller(monkeypatch, "_extract_client_context_messages", _boom)

    frames: list[dict[str, object]] = []
    with TestClient(app).websocket_connect(_url(scope)) as ws:
        for message in messages:
            ws.send_json(message)
            frames += _drain(ws, 1)  # الجاسوس لا يبثّ، فكلّ رسالة تُنتج إطاراً واحداً

    return {
        "frames": frames,
        "ensure_calls": ensure_calls,
        "stream_calls": recorder.stream_calls,
        "identity_calls": recorder.identity_calls,
    }


SCOPES: tuple[str, ...] = ("customer", "admin")


@pytest.mark.parametrize("scope", SCOPES)
@pytest.mark.parametrize("name", SCENARIOS)
def test_ws_turn_matches_the_golden_transcript(
    monkeypatch: pytest.MonkeyPatch, name: str, scope: str
) -> None:
    """أيّ انحرافٍ عن المرجع المُلتزَم يظهر diff مقروءاً بدل أن يُبتلع."""
    golden = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))
    key = f"{scope}::{name}"
    assert key in golden, (
        f"المرجع لا يحمل {key!r}. يُولَّد على الكود **قبل** أيّ نقل:\n"
        f"   python scripts/contracts/regenerate_ws_transcript_golden.py"
    )
    assert _run_scenario(monkeypatch, scope, name) == golden[key]


def test_the_golden_file_covers_every_scenario_and_scope() -> None:
    """مرجعٌ ناقصٌ يمرّ بصمت — والفراغ يُقرأ نجاحاً (D-207 · «الثمن الثالث»)."""
    golden = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))
    expected = {f"{scope}::{name}" for scope in SCOPES for name in SCENARIOS}
    assert set(golden) == expected, (
        f"ناقصٌ في المرجع: {sorted(expected - set(golden))}\n"
        f"زائدٌ في المرجع: {sorted(set(golden) - expected)}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# فحوص لا يعبّر عنها المرجع (هويّة كائنات · تكافؤ التوأمين)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("scope", SCOPES)
def test_admin_payload_reaches_the_engine_only_for_admin(
    monkeypatch: pytest.MonkeyPatch, scope: str
) -> None:
    """`admin_payload` هو الفرق الرابع بين التوأمين — يُقاس بالهويّة لا بالشكل."""
    recorder = _Recorder()
    recorder.install(monkeypatch)
    _install_conversation(monkeypatch, scope)

    with TestClient(app).websocket_connect(_url(scope)) as ws:
        ws.send_json({"question": "سؤال"})
        ws.receive_json()

    (call,) = recorder.raw_stream_calls
    payload = call.get("admin_payload")
    if scope == "admin":
        assert isinstance(payload, dict) and payload.get("is_admin") is True, (
            "المسار الإداري يجب أن يمرّر الـJWT المفكوكة نفسها إلى المحرّك."
        )
    else:
        assert payload is None, (
            "مسار العميل يجب ألّا يحمل أيّ مفتاح إدارة (fail-closed — D-171/ISS-132)."
        )


def test_the_twins_differ_only_in_the_six_measured_things(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """التكافؤ التفاضلي: بعد تحييد الفروق الستّة، يتطابق الدوران بالكامل.

    هذا هو الاختبار الذي يجعل ضغط الفروق في `ChatWsScope` قراراً مقيساً لا رهاناً:
    إن أدخل التفكيك أيّ فرقٍ **سابع** بين المسارين، يسقط هنا.
    """
    seen: dict[str, dict[str, object]] = {}
    for scope in SCOPES:
        with monkeypatch.context() as patch:
            recorder = _Recorder()
            recorder.install(patch)
            _install_conversation(patch, scope)
            with TestClient(app).websocket_connect(_url(scope)) as ws:
                ws.send_json({"question": "سؤال", "mission_type": "research"})
                ws.receive_json()
            (call,) = recorder.stream_calls
            (identity,) = recorder.identity_calls
            seen[scope] = {"stream": dict(call), "identity": dict(identity)}

    for scope in SCOPES:
        stream = seen[scope]["stream"]
        identity = seen[scope]["identity"]
        assert isinstance(stream, dict) and isinstance(identity, dict)
        # الفروق المعروفة تُحيَّد صراحةً — وما بقي يجب أن يتطابق.
        stream.pop("admin_payload", None)  # الفرق ٤
        stream["chat_scope"] = "<scope>"  # الفرق ٣
        identity["route_name"] = "<route>"  # الفرق ٥
        context = stream.get("context")
        if isinstance(context, dict):
            context["conversation_id"] = "<conversation>"
            context["thread_id"] = "<thread>"
        stream["conversation_id"] = "<conversation>"
        identity["conversation_id"] = "<conversation>"
        identity["thread_id"] = "<thread>"

    assert seen["customer"] == seen["admin"], (
        "ظهر فرقٌ **سابع** بين التوأمين خارج الستّة المقيسة (ISS-155).\n"
        "   إمّا أنّ التفكيك غيّر سلوكاً، أو أنّ الفرق الجديد مقصودٌ ويحتاج قراراً مكتوباً."
    )
