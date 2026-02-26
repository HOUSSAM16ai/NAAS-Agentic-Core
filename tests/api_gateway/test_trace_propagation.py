"""اختبارات تكامل مصغرة لتأكيد تمرير traceparent داخل بوابة API."""

from __future__ import annotations

from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient

from microservices.api_gateway import main
from microservices.api_gateway.security import verify_gateway_request


def test_gateway_generates_traceparent_when_missing(monkeypatch) -> None:
    """يتأكد من توليد traceparent عند غيابه وتمريره إلى طبقة التحويل."""
    captured: dict[str, str] = {}

    async def fake_forward(request, *_args, **_kwargs):
        captured["traceparent"] = getattr(request.state, "traceparent", "")
        return PlainTextResponse("ok")

    monkeypatch.setattr(main.proxy_handler, "forward", fake_forward)
    main.app.dependency_overrides[verify_gateway_request] = lambda: True
    client = TestClient(main.app)
    response = client.get("/api/v1/planning/test")
    main.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured["traceparent"].startswith("00-")
    assert response.headers["traceparent"] == captured["traceparent"]


def test_gateway_forwards_existing_traceparent(monkeypatch) -> None:
    """يتأكد من الحفاظ على traceparent القادم من العميل دون تعديل."""
    incoming = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    captured: dict[str, str] = {}

    async def fake_forward(request, *_args, **_kwargs):
        captured["traceparent"] = getattr(request.state, "traceparent", "")
        return PlainTextResponse("ok")

    monkeypatch.setattr(main.proxy_handler, "forward", fake_forward)
    main.app.dependency_overrides[verify_gateway_request] = lambda: True
    client = TestClient(main.app)
    response = client.get("/api/v1/planning/test", headers={"traceparent": incoming})
    main.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured["traceparent"] == incoming
    assert response.headers["traceparent"] == incoming
