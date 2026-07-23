"""اختبارات عقد /health لـ conversation-service بعد الترقية إلى Skill كامل (D-042/D-182).

قبل الترقية كانت الخدمة تعلن `capability_level`/`parity_ready` لأجل admission control
(منع promotion غير مقصود وهي stub). **D-042** رقّاها إلى Skill كامل (v2.0.0، step 12)
فأُزيل حقلا القدرة من `/health`. الاختبارات القديمة ظلّت تؤكّد `capability_level == "stub"`
فصارت red-on-main (KeyError) ومُستبعَدة من البوّابة. **D-182** يُحدّثها إلى العقد الحالي:
الخدمة مُرقّاة ولم تعد stub، وحقول القدرة القديمة لم تعد تُعلَن (الترقية اكتملت) — فتعود
خضراء وتخرج من قائمة deselect (D-105: القوائم تتقلّص فقط بإصلاح مُثبَت).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from microservices.conversation_service.main import app


def test_conversation_health_reports_promoted_full_skill() -> None:
    """بعد D-042: الخدمة Skill كامل (step 12) لا stub — تعلن الهوية والجاهزية."""
    response = TestClient(app).get("/health")
    payload = response.json()

    assert response.status_code == 200
    assert payload["service"] == "conversation-service"
    assert payload["step"] == "12"
    assert payload["version"]
    assert isinstance(payload["graph_ready"], bool)


def test_conversation_health_no_longer_declares_stub_capability(monkeypatch) -> None:
    """حقلا admission control القديمان أُزيلا عند الترقية — لا رجوع صامت إلى stub."""
    # حتى مع ضبط العلم القديم صراحةً، العقد الحالي لا يُعيد إحياء حقول القدرة.
    monkeypatch.setenv("CONVERSATION_CAPABILITY_LEVEL", "parity_ready")
    payload = TestClient(app).get("/health").json()

    assert "capability_level" not in payload
    assert "parity_ready" not in payload
