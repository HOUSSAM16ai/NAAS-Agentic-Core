"""اختبارات سلوك مكافئ لشرائح `orchestrator_client_support/` (D-256).

تثبت أن القلب النقي المفكَّك من `orchestrator_client.py` (CodeScene X-Ray job 72)
مطابق للسلوك السابق حرفًا: 404 ⇒ None/[]، خطأ HTTP ⇒ يُرمى حرفًا، JWT payload
يحمل المفاتيح الرسمية مع claim الإدمن عند is_admin، وقرار الاسترجاع المفهرَس
يعالج المسارات الثلاثة (غير معروف · مطابقة محلية · إشارة بنيوية بـ Supabase).
"""

from __future__ import annotations

import httpx
import pytest

from app.infrastructure.clients.orchestrator_client_support.missions import (
    MissionRequestArgs,
    ServiceJwtPayload,
    _request_mission,
)
from app.infrastructure.clients.orchestrator_client_support.preempts import (
    resolve_indexed_anchor,
)


def _make_fake_client(responses: list[dict]) -> tuple[object, list[dict]]:
    """عميل وهمي يسجّل النداءات ويُعيد الردود بالترتيب."""
    calls: list[dict] = []

    class _Resp:
        def __init__(self, status: int, body: object) -> None:
            self.status_code = status
            self._body = body

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"{self.status_code}",
                    request=httpx.Request("GET", "x"),
                    response=self,
                )

        def json(self) -> object:
            return self._body

    class _FakeClient:
        async def get(self, url: str) -> _Resp:
            calls.append({"method": "GET", "url": url})
            return _Resp(**responses[len(calls) - 1])

    async def _fake_getter() -> _FakeClient:
        return _FakeClient()

    # `_request_mission` يستدعي `await get_client()` — نمرّر الدالة نفسها.
    return _fake_getter, calls


def _make_post_client(response: dict) -> tuple[object, list[dict]]:
    """عميل وهمي post يسجّل الوسائط ويعيد response واحدًا."""
    calls: list[dict] = []

    class _Resp:
        def __init__(self, status: int, body: object) -> None:
            self.status_code = status
            self._body = body

        def raise_for_status(self) -> None:
            pass

        def json(self) -> object:
            return self._body

    class _Client:
        async def post(self, url: str, json: object, headers: dict) -> _Resp:
            calls.append({"url": url, "json": json, "headers": headers})
            return _Resp(**response)

    async def _fake_getter() -> _Client:
        return _Client()

    # `_request_mission` يستدعي `await get_client()` — نمرّر الدالة نفسها.
    return _fake_getter, calls


_NO_MATCH_QUESTION = "أريد ex_xyz تمرين غريب جداً"


@pytest.mark.asyncio
async def test_request_mission_404_returns_empty_value() -> None:
    """404 ⇒ `empty_value` — مطابقة سلوك get_mission سابقًا (يعيد None)."""
    fake, calls = _make_fake_client([{"status": 404, "body": None}])
    result = await _request_mission(
        fake,  # type: ignore[arg-type]
        "http://x",
        "GET",
        "/missions/7",
        empty_value=None,
        log_prefix="Fetching mission",
    )
    assert result is None
    assert calls[0]["url"] == "http://x/missions/7"


@pytest.mark.asyncio
async def test_request_mission_events_404_returns_empty_list() -> None:
    """404 ⇒ [] للأحداث — مطابقة حرفية للسلوك القديم `get_mission_events`."""
    fake, _ = _make_fake_client([{"status": 404, "body": None}])
    result = await _request_mission(
        fake,  # type: ignore[arg-type]
        "http://x",
        "GET",
        "/missions/7/events",
        empty_value=[],
        log_prefix="Fetching mission events",
    )
    assert result == []


@pytest.mark.asyncio
async def test_request_mission_http_error_raises() -> None:
    """خطأ HTTP غير 404 ⇒ يُرمى حرفًا كما في السلوك القديم (raise_for_status).

    D-256: القلب النقي بلا try/catch — الاستثناء الأصلي يصل قشرة التفويض لتتعامل
    معه كما كانت (`logger.error + raise` في create_mission، أو يرميه get_mission
    كما كان سابقًا)."""
    fake, _ = _make_fake_client([{"status": 500, "body": None}])
    with pytest.raises(httpx.HTTPStatusError):
        await _request_mission(
            fake,  # type: ignore[arg-type]
            "http://x",
            "GET",
            "/missions/7",
            empty_value=None,
            log_prefix="Fetching mission",
        )


@pytest.mark.asyncio
async def test_request_mission_post_sends_payload_and_headers() -> None:
    """create_mission: payload والـ idempotency header يمرّان حرفيًا."""
    fake, calls = _make_post_client({"status": 200, "body": {"id": 1, "status": "created"}})
    result = await _request_mission(
        fake,  # type: ignore[arg-type]
        "http://x",
        "POST",
        "/missions",
        json_body={"objective": "O", "context": {}, "priority": 1},
        headers={"X-Correlation-ID": "k1"},
        empty_value=None,
        log_prefix="Dispatching mission to Orchestrator",
    )
    assert result == {"id": 1, "status": "created"}
    assert calls[0]["headers"] == {"X-Correlation-ID": "k1"}


def test_mission_request_args_is_frozen() -> None:
    """نمط D-249: بيانات معلنة مجمّدة."""
    args = MissionRequestArgs(objective="O", context={}, priority=1, idempotency_key="k")
    with pytest.raises(AttributeError):
        args.objective = "X"  # type: ignore[misc]


def test_service_jwt_payload_official_keys() -> None:
    """الحمولة الرسمية لـ JWT تطابق السلوك القديم حرفًا (sub/user_id/iat/exp/iss)."""
    payload = ServiceJwtPayload(user_id=42, is_admin=False).as_dict(now=1_000_000)
    assert payload["sub"] == "42"
    assert payload["user_id"] == 42
    assert payload["iat"] == 1_000_000
    assert payload["exp"] == 1_000_300
    assert payload["iss"] == "cogniforge-monolith"
    assert "is_admin" not in payload
    assert "role" not in payload


def test_service_jwt_payload_carries_admin_claim() -> None:
    """ISS-131 (D-169): claim الإدمن صريح — ValidateAccessNode fail-closed."""
    payload = ServiceJwtPayload(user_id=7, is_admin=True).as_dict(now=0)
    assert payload["is_admin"] is True
    assert payload["role"] == "admin"


def test_service_jwt_encodes_hs256_same_secret_as_monolith() -> None:
    """العميل يوقّع بنفس SECRET_KEY المشترك (نفس سلوك _build_service_jwt)."""
    import jwt as pyjwt

    token = ServiceJwtPayload(user_id=1, is_admin=False).encode("secret", now=0)
    decoded = pyjwt.decode(
        token,
        "secret",
        algorithms=["HS256"],
        options={"verify_exp": False},
    )
    assert decoded["user_id"] == 1
    assert decoded["iss"] == "cogniforge-monolith"


def test_resolve_indexed_anchor_unrecognized() -> None:
    """سؤال عادي بلا نية استرجاع ⇒ لا preempt (السلوك القديم: return False)."""
    decision = resolve_indexed_anchor("ما هو عاصمة الجزائر؟")
    assert not decision.recognized
    assert decision.matched_entry is None
    assert not decision.db_anchored


def test_resolve_indexed_anchor_supabase_path_when_no_local_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """intent+signal ⇒ المسار القابل للتوسع (Supabase) — السلوك القديم try/except.

    ISS-056: عند نية استرجاع مؤكدة بلا تطابق محلي نجرّب `extract_db_facets`،
    وإن فشل فالبث الفارغ يسقط للمسار العادي."""
    from app.services.capabilities import bac_db_retriever, exercise_retrieval

    fake_decision = exercise_retrieval.ExerciseRetrievalDecision(
        recognized=True,
        matched_entry=None,
        support_level="standard",
    )
    # patch اسم الاستخدام داخل `preempts` نفسه — مكان استدعاء resolve_indexed_anchor
    # الحرفي، لأن الدالة مستوردة صراحة في الشريحة لا من الوحدة الأصلية.
    monkeypatch.setattr(
        "app.infrastructure.clients.orchestrator_client_support.preempts.detect_exercise_retrieval",
        lambda _req, **_kw: fake_decision,
    )

    class _Facets:
        is_anchored = True

    monkeypatch.setattr(
        bac_db_retriever,
        "extract_db_facets",
        lambda _q: _Facets(),
    )
    # سؤال نية استرجاع موثوقة بلا أي إشارة بنيوية (سنة/دورة/موضوع/رقم) وبلا
    # كلمات شائعة تطابق find_best_match — يضمن دخول مسار Supabase بدل المطابقة
    # المفهرَسة الفورية (tag-fallback).
    decision = resolve_indexed_anchor(_NO_MATCH_QUESTION)
    assert decision.recognized
    assert decision.db_anchored


def test_resolve_indexed_anchor_supabase_failure_returns_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """فشل Supabase ⇒ False — السلوك القديم `except Exception: return False`."""
    from app.services.capabilities import bac_db_retriever, exercise_retrieval

    monkeypatch.setattr(
        "app.infrastructure.clients.orchestrator_client_support.preempts.detect_exercise_retrieval",
        lambda _req, **_kw: exercise_retrieval.ExerciseRetrievalDecision(
            recognized=True,
            matched_entry=None,
            support_level="standard",
        ),
    )
    monkeypatch.setattr(
        bac_db_retriever,
        "extract_db_facets",
        lambda _q: 1 / 0,
    )
    # نفس سؤال لا-تطابق المعرفة — نثبت أن فشل Supabase يُسقِط القرار إلى False.
    decision = resolve_indexed_anchor(_NO_MATCH_QUESTION)
    assert decision.recognized
    assert not decision.db_anchored


def test_resolve_indexed_anchor_local_match_returns_true_without_supabase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """المطابقة المحلية ⇒ True فوري بلا محاولة Supabase (سلوك D-049 الأصلي).

    (CodeRabbit PR #19 — اختُبر مسار `matched_entry is not None`)
    """
    from app.services.capabilities import exercise_retrieval

    call_args: list = []
    real_detect = exercise_retrieval.detect_exercise_retrieval

    def _spying_detect(req, **kw):
        call_args.append((req.question, kw))
        return real_detect(req, **kw)

    monkeypatch.setattr(
        "app.infrastructure.clients.orchestrator_client_support.preempts.detect_exercise_retrieval",
        _spying_detect,
    )
    # سؤال يطابق تمرين الاحتمالات 2024 في الفهرس المنسق (مطابقة محلية حقيقية).
    decision = resolve_indexed_anchor("اعطني تمرين الاحتمالات 2024")
    assert decision.recognized
    assert decision.matched_entry is not None
    assert decision.matched_entry.exercise_number == 1
    assert decision.db_anchored
    assert call_args, "detect_exercise_retrieval لم يُستدعَ"
