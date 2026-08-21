"""اختبارات لوحة وليّ الأمر — D-196.

ثلاثة عقود تُختبَر هنا، وكلّها أمنية قبل أن تكون وظيفية:

1. **الرضا شرطٌ بنيوي** — لا مسار يربط حساب طالب بحساب آخر دون رمزٍ يُصدره الطالب.
2. **مُعرَّف المسار ليس تفويضاً** — قراءة تقرير طالبٍ غير مرتبط تُرفَض.
3. **التقرير لا يحمل نصّاً** — الوليّ ليس باباً خلفياً إلى الحلّ الذي مُنع منه الطالب
   (D-113). الحماية بنيوية: الخدمة لا تستعلم عن عمود `content` إطلاقاً.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.services.guardian import GuardianLinkService, GuardianReportService
from app.services.guardian.linking import (
    CODE_LENGTH,
    GuardianLinkError,
    generate_link_code,
)
from app.services.guardian.report import FRAGILE_ILLUSION_GAP

NOW = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)


async def _make_user(db_session, email: str) -> int:
    result = await db_session.execute(
        text(
            "INSERT INTO users (external_id, full_name, email, password_hash, "
            "is_admin, is_active, status) VALUES (:e, :n, :e, 'x', 0, 1, 'active')"
        ),
        {"e": email, "n": email.split("@", maxsplit=1)[0]},
    )
    await db_session.commit()
    return int(result.lastrowid)


def _run(event_loop, coro):
    return event_loop.run_until_complete(coro)


# ── رمز الربط ───────────────────────────────────────────────────────────────────


def test_link_codes_are_unguessable_and_unambiguous() -> None:
    """
    الرمز عشوائي تعمويّاً وبلا محارف مُلتبِسة.

    رمزٌ متسلسل أو مُشتقّ من المُعرَّف يسمح بربط حساب قاصر بالتخمين — وهو أخطر عطبٍ
    ممكن هنا. والالتباس (0/O · 1/I) يجعل الرمز غير قابل للإملاء صوتياً.
    """
    codes = {generate_link_code() for _ in range(400)}
    assert len(codes) > 390  # عمليّاً بلا تصادم
    for code in codes:
        assert len(code) == CODE_LENGTH
        assert not set(code) & set("01OIL")


def test_the_link_starts_from_the_student(event_loop, db_session) -> None:
    async def scenario() -> None:
        student = await _make_user(db_session, "student-link@example.com")
        guardian = await _make_user(db_session, "guardian-link@example.com")
        service = GuardianLinkService(db_session)

        code = await service.issue_code(student)
        assert await service.is_linked(guardian, student) is False

        linked = await service.redeem_code(guardian, code)
        assert linked.student_user_id == student
        assert await service.is_linked(guardian, student) is True

    _run(event_loop, scenario())


def test_a_code_can_only_be_redeemed_once(event_loop, db_session) -> None:
    """من رأى الرمز مرّةً لا يستطيع الربط لاحقاً."""

    async def scenario() -> None:
        student = await _make_user(db_session, "once-student@example.com")
        first = await _make_user(db_session, "once-guardian@example.com")
        second = await _make_user(db_session, "once-intruder@example.com")
        service = GuardianLinkService(db_session)

        code = await service.issue_code(student)
        await service.redeem_code(first, code)

        with pytest.raises(GuardianLinkError, match="already been used"):
            await service.redeem_code(second, code)
        assert await service.is_linked(second, student) is False

    _run(event_loop, scenario())


def test_an_unknown_code_is_rejected_loudly(event_loop, db_session) -> None:
    async def scenario() -> None:
        guardian = await _make_user(db_session, "unknown-code@example.com")
        with pytest.raises(GuardianLinkError, match="unknown link code"):
            await GuardianLinkService(db_session).redeem_code(guardian, "ZZZZZZZZ")

    _run(event_loop, scenario())


def test_a_student_cannot_become_their_own_guardian(event_loop, db_session) -> None:
    async def scenario() -> None:
        student = await _make_user(db_session, "self-link@example.com")
        service = GuardianLinkService(db_session)
        code = await service.issue_code(student)
        with pytest.raises(GuardianLinkError, match="own guardian"):
            await service.redeem_code(student, code)

    _run(event_loop, scenario())


def test_codes_are_matched_case_insensitively_after_trimming(event_loop, db_session) -> None:
    """الوليّ يكتب الرمز يدوياً — المسافة أو حالة الأحرف ليست خطأ ربط."""

    async def scenario() -> None:
        student = await _make_user(db_session, "case-student@example.com")
        guardian = await _make_user(db_session, "case-guardian@example.com")
        service = GuardianLinkService(db_session)
        code = await service.issue_code(student)
        linked = await service.redeem_code(guardian, f"  {code.lower()}  ")
        assert linked.student_user_id == student

    _run(event_loop, scenario())


def test_revoking_keeps_the_row_as_an_access_trail(event_loop, db_session) -> None:
    async def scenario() -> None:
        student = await _make_user(db_session, "revoke-student@example.com")
        guardian = await _make_user(db_session, "revoke-guardian@example.com")
        service = GuardianLinkService(db_session)
        code = await service.issue_code(student)
        await service.redeem_code(guardian, code)

        assert await service.revoke(student_user_id=student, guardian_user_id=guardian) is True
        assert await service.is_linked(guardian, student) is False

        remaining = await db_session.scalar(
            text("SELECT status FROM guardian_links WHERE student_user_id = :s"),
            {"s": student},
        )
        assert remaining == "revoked"

    _run(event_loop, scenario())


def test_revoking_a_link_that_does_not_exist_returns_false(event_loop, db_session) -> None:
    async def scenario() -> None:
        student = await _make_user(db_session, "norevoke-s@example.com")
        guardian = await _make_user(db_session, "norevoke-g@example.com")
        assert (
            await GuardianLinkService(db_session).revoke(
                student_user_id=student, guardian_user_id=guardian
            )
            is False
        )

    _run(event_loop, scenario())


def test_linked_students_lists_only_active_links(event_loop, db_session) -> None:
    async def scenario() -> None:
        guardian = await _make_user(db_session, "multi-guardian@example.com")
        kept = await _make_user(db_session, "kept-child@example.com")
        dropped = await _make_user(db_session, "dropped-child@example.com")
        service = GuardianLinkService(db_session)

        await service.redeem_code(guardian, await service.issue_code(kept))
        await service.redeem_code(guardian, await service.issue_code(dropped))
        await service.revoke(student_user_id=dropped, guardian_user_id=guardian)

        listed = await service.linked_students(guardian)
        assert [item.student_user_id for item in listed] == [kept]

    _run(event_loop, scenario())


# ── التقرير الأسبوعي ────────────────────────────────────────────────────────────


async def _seed_progress(
    db_session, user_id: int, *, concept: str, assisted: float, durable: float, when: datetime
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO student_bkt_analytics (user_id, session_id, concept_id,"
            " cognitive_load_estimate, student_mastery_probability, interaction_count,"
            " durable_mastery, support_level, novel_item, interaction_timestamp)"
            " VALUES (:u, 1, :c, 'medium', :a, 1, :d, 3, 0, :t)"
        ),
        {"u": user_id, "c": concept, "a": assisted, "d": durable, "t": when},
    )
    await db_session.commit()


def test_report_is_a_deterministic_aggregate(event_loop, db_session) -> None:
    async def scenario() -> None:
        student = await _make_user(db_session, "report-student@example.com")
        await _seed_progress(
            db_session,
            student,
            concept="probability",
            assisted=0.4,
            durable=0.2,
            when=NOW - timedelta(days=3),
        )
        await _seed_progress(
            db_session,
            student,
            concept="probability",
            assisted=0.8,
            durable=0.6,
            when=NOW - timedelta(days=1),
        )

        report = await GuardianReportService(db_session).build(student, now=NOW)

        assert report.student_user_id == student
        assert report.concepts_practised == 1
        progress = report.all_concepts[0]
        assert progress.concept_id == "probability"
        assert progress.title == "الاحتمالات"
        assert progress.subject == "mathematics"
        assert progress.interactions == 2
        assert progress.assisted_mastery == pytest.approx(0.8)
        assert progress.durable_mastery == pytest.approx(0.6)
        assert progress.improved is True

    _run(event_loop, scenario())


def test_the_illusion_gap_is_shown_to_the_guardian_not_hidden(event_loop, db_session) -> None:
    """
    أداءٌ مدعوم مرتفع مع إتقانٍ دائم منخفض هو **التحذير** الذي يجب أن يراه الوليّ.

    إخفاؤه خلف رقمٍ واحدٍ مُطمئن يبيع للوليّ نفس وَهْم الطلاقة الذي تحارب المنصّة.
    """

    async def scenario() -> None:
        student = await _make_user(db_session, "fragile-student@example.com")
        await _seed_progress(
            db_session,
            student,
            concept="integration",
            assisted=0.9,
            durable=0.3,
            when=NOW - timedelta(days=1),
        )

        report = await GuardianReportService(db_session).build(student, now=NOW)
        fragile = report.all_concepts[0]
        assert fragile.illusion_gap == pytest.approx(0.6)
        assert fragile.illusion_gap >= FRAGILE_ILLUSION_GAP
        assert fragile.fragile is True
        assert report.needs_attention[0].concept_id == "integration"

    _run(event_loop, scenario())


def test_activity_outside_the_window_is_excluded(event_loop, db_session) -> None:
    async def scenario() -> None:
        student = await _make_user(db_session, "window-student@example.com")
        await _seed_progress(
            db_session,
            student,
            concept="probability",
            assisted=0.5,
            durable=0.5,
            when=NOW - timedelta(days=30),
        )
        report = await GuardianReportService(db_session).build(student, now=NOW)
        assert report.concepts_practised == 0
        assert report.all_concepts == ()

    _run(event_loop, scenario())


def test_a_concept_outside_the_registry_is_reported_without_a_subject(
    event_loop, db_session
) -> None:
    """صفٌّ خُزِّن قبل توحيد المنهاج يظهر في التقرير بدل أن يُسقِطه."""

    async def scenario() -> None:
        student = await _make_user(db_session, "legacy-concept-report@example.com")
        await _seed_progress(
            db_session,
            student,
            concept="phlogiston",
            assisted=0.5,
            durable=0.5,
            when=NOW - timedelta(days=1),
        )
        report = await GuardianReportService(db_session).build(student, now=NOW)
        assert report.all_concepts[0].subject == "unknown"
        assert report.all_concepts[0].title == "phlogiston"

    _run(event_loop, scenario())


def test_an_empty_week_reports_zeroes_rather_than_failing(event_loop, db_session) -> None:
    async def scenario() -> None:
        student = await _make_user(db_session, "quiet-student@example.com")
        report = await GuardianReportService(db_session).build(student, now=NOW)
        assert report.active_days == 0
        assert report.current_streak == 0
        assert report.sessions == 0
        assert report.reviews_completed == 0
        assert report.strongest == ()

    _run(event_loop, scenario())


def test_the_report_service_never_reads_message_content() -> None:
    """
    حماية بنيوية لا مُرشِّح نصّي.

    لو استعلم التقرير يوماً عن `content` لصار مقتطفُ حلٍّ قابلاً للتسرّب إلى شاشة
    الوليّ — ومنها إلى الطالب الذي مُنع منه عمداً (D-113). المنع يجب أن يكون في
    غياب الاستعلام نفسه.
    """
    from pathlib import Path

    source = Path("app/services/guardian/report.py").read_text(encoding="utf-8")
    assert "CustomerMessage.content" not in source
    assert ".content" not in source


# ── التفويض على نقاط النهاية ────────────────────────────────────────────────────


def test_weekly_report_requires_authentication(client) -> None:
    assert client.get("/api/v1/guardian/students/1/weekly").status_code in (401, 403)


def test_a_guardian_cannot_read_an_unlinked_students_report(
    event_loop, client, db_session, register_and_login_test_user
) -> None:
    """مُعرَّف الطالب في المسار ليس تفويضاً — تعدادُ الأرقام لا يفتح تقدّم أيّ طفل."""

    async def seed() -> tuple[str, int]:
        token = await register_and_login_test_user(db_session, "stranger@example.com")
        victim = await _make_user(db_session, "victim-child@example.com")
        return token, victim

    token, victim = _run(event_loop, seed())

    response = client.get(
        f"/api/v1/guardian/students/{victim}/weekly",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_the_full_consent_flow_over_http(
    event_loop, client, db_session, register_and_login_test_user
) -> None:
    """الدورة الحقيقية: الطالب يُصدر، الوليّ يستبدل، ثمّ يقرأ التقرير."""

    async def seed() -> tuple[str, str, int]:
        student_token = await register_and_login_test_user(db_session, "flow-student@example.com")
        guardian_token = await register_and_login_test_user(db_session, "flow-guardian@example.com")
        student_id = await db_session.scalar(
            text("SELECT id FROM users WHERE email = 'flow-student@example.com'")
        )
        return student_token, guardian_token, int(student_id)

    student_token, guardian_token, student_id = _run(event_loop, seed())

    issued = client.post(
        "/api/v1/guardian/link-code", headers={"Authorization": f"Bearer {student_token}"}
    )
    assert issued.status_code == 200, issued.text
    code = issued.json()["link_code"]

    linked = client.post(
        "/api/v1/guardian/link",
        json={"link_code": code},
        headers={"Authorization": f"Bearer {guardian_token}"},
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["student_user_id"] == student_id

    listed = client.get(
        "/api/v1/guardian/students", headers={"Authorization": f"Bearer {guardian_token}"}
    )
    assert [item["student_user_id"] for item in listed.json()] == [student_id]

    report = client.get(
        f"/api/v1/guardian/students/{student_id}/weekly",
        headers={"Authorization": f"Bearer {guardian_token}"},
    )
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["student_user_id"] == student_id
    # العقد لا يحمل حقلاً نصّياً حرّاً من المحادثة.
    assert "messages" not in body
    assert "content" not in body

    revoked = client.delete(
        f"/api/v1/guardian/students/{student_id}",
        headers={"Authorization": f"Bearer {guardian_token}"},
    )
    assert revoked.status_code == 204

    after = client.get(
        f"/api/v1/guardian/students/{student_id}/weekly",
        headers={"Authorization": f"Bearer {guardian_token}"},
    )
    assert after.status_code == 404


def test_redeeming_a_bad_code_over_http_is_a_400(
    event_loop, client, db_session, register_and_login_test_user
) -> None:
    token = _run(event_loop, register_and_login_test_user(db_session, "bad-code@example.com"))
    response = client.post(
        "/api/v1/guardian/link",
        json={"link_code": "ZZZZZZZZ"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400


def test_revoking_an_unlinked_student_over_http_is_a_404(
    event_loop, client, db_session, register_and_login_test_user
) -> None:
    token = _run(event_loop, register_and_login_test_user(db_session, "norevoke-http@example.com"))
    response = client.delete(
        "/api/v1/guardian/students/98765", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404


# ── معالِجات الموجِّه مباشرةً ────────────────────────────────────────────────────
#
# اختبارات HTTP أعلاه تُثبت السلوك من طرف العميل، لكنّ معالِجات ASGI تعمل في خيط
# عامل تحت `TestClient` فلا يتتبّعها `coverage`. النداء المباشر يُثبِّت **فروع الخطأ**
# نفسها في الخيط الرئيسي — فيصير المنع مُختبَراً لا مأمولاً.


class _StubLinks:
    def __init__(self, *, linked: bool = False, revoked: bool = False) -> None:
        self._linked = linked
        self._revoked = revoked

    async def is_linked(self, guardian_user_id: int, student_user_id: int) -> bool:
        return self._linked

    async def revoke(self, *, student_user_id: int, guardian_user_id: int) -> bool:
        return self._revoked

    async def redeem_code(self, guardian_user_id: int, code: str):
        raise GuardianLinkError("unknown link code")


class _StubUser:
    def __init__(self, user_id: int = 1) -> None:
        self.user = type("U", (), {"id": user_id})()


def test_handler_rejects_an_unlinked_student_with_404(event_loop) -> None:
    from fastapi import HTTPException

    from app.api.routers.guardian import weekly_report

    with pytest.raises(HTTPException) as excinfo:
        _run(
            event_loop,
            weekly_report(
                student_user_id=42,
                current=_StubUser(),  # type: ignore[arg-type]
                links=_StubLinks(linked=False),  # type: ignore[arg-type]
                reports=None,  # type: ignore[arg-type]
            ),
        )
    assert excinfo.value.status_code == 404


def test_handler_turns_a_link_error_into_a_400(event_loop) -> None:
    from fastapi import HTTPException

    from app.api.routers.guardian import LinkRequest, redeem_link_code

    with pytest.raises(HTTPException) as excinfo:
        _run(
            event_loop,
            redeem_link_code(
                payload=LinkRequest(link_code="ZZZZZZZZ"),
                current=_StubUser(),  # type: ignore[arg-type]
                service=_StubLinks(),  # type: ignore[arg-type]
            ),
        )
    assert excinfo.value.status_code == 400
    assert "unknown link code" in excinfo.value.detail


def test_handler_revoke_returns_204_on_success_and_404_otherwise(event_loop) -> None:
    from fastapi import HTTPException

    from app.api.routers.guardian import revoke_link

    ok = _run(
        event_loop,
        revoke_link(
            student_user_id=7,
            current=_StubUser(),  # type: ignore[arg-type]
            service=_StubLinks(revoked=True),  # type: ignore[arg-type]
        ),
    )
    assert ok.status_code == 204

    with pytest.raises(HTTPException) as excinfo:
        _run(
            event_loop,
            revoke_link(
                student_user_id=7,
                current=_StubUser(),  # type: ignore[arg-type]
                service=_StubLinks(revoked=False),  # type: ignore[arg-type]
            ),
        )
    assert excinfo.value.status_code == 404
