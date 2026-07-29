from __future__ import annotations

"""
D-185 — عقد `notation-service` (:8011): الخدمة المصغّرة الثالثة عشرة، API-first.

تُثبت هذه الاختبارات عقد الخدمة كما يستهلكه الغير: `/resolve` · `/define` · `/symbols`
· `/health` بحقول جاهزية حقيقية · `/metrics` بسجلّ مستقلّ. وتُثبت كذلك قوانين المهارات
(CLAUDE.md §0.5): مسؤولية واحدة · بلا LLM · fail-open · بلا قاعدة بيانات أو مفاتيح ·
كل نداء مُسجَّل في Prometheus · واستقلال تام عن المونوليث (نسخة مُوَرَّدة من السجلّ).
"""

import pytest
from fastapi.testclient import TestClient

from microservices.notation_service.main import app

_CATASTROPHE_Q = "ماذا نقصد بحرف C"


@pytest.fixture
def client() -> TestClient:
    """عميل اختبار يمرّ بدورة الحياة كاملة (فيُثبَّت `startup_info`)."""
    with TestClient(app) as test_client:
        yield test_client


class TestHealthContract:
    """«Degraded ≠ Dead» — الصحّة تُبلِّغ جاهزية حقيقية لا `{"status":"ok"}` فقط."""

    def test_health_exposes_readiness_fields(self, client: TestClient) -> None:
        body = client.get("/health").json()
        assert body["status"] == "healthy"
        assert body["service"] == "notation-service"
        assert body["startup_state"] == "ready"
        assert body["symbols_loaded"] > 0
        assert body["registry_version"]

    def test_health_declares_no_llm(self, client: TestClient) -> None:
        """الحقيقة الرمزية قبل اللغة — الخدمة حتمية بالكامل."""
        assert client.get("/health").json()["llm_backend"] == "none"


class TestResolveContract:
    """`/resolve`: نصّ الطالب الحرّ ⇒ رمز مُعرَّف أو `found=false` (لا 500 أبداً)."""

    def test_catastrophe_question_resolves(self, client: TestClient) -> None:
        body = client.post("/resolve", json={"text": _CATASTROPHE_Q}).json()
        assert body["found"] is True
        assert body["symbol"]["symbol"] == "C(n,k)"
        assert "التوافيق" in body["symbol"]["title"]

    def test_resolution_leaks_no_exercise_numbers(self, client: TestClient) -> None:
        body = client.post("/resolve", json={"text": _CATASTROPHE_Q}).json()
        shown = body["symbol"]["definition"] + body["symbol"]["example"]
        for number in ("14", "165", "56"):
            assert number not in shown

    def test_event_letter_is_not_notation(self, client: TestClient) -> None:
        body = client.post("/resolve", json={"text": "ما هي الحادثة C"}).json()
        assert body["found"] is False
        assert body["symbol"] is None

    def test_unmatched_text_is_a_valid_answer(self, client: TestClient) -> None:
        """fail-open: عدم المطابقة جواب مشروع، لا خطأ."""
        response = client.post("/resolve", json={"text": "مرحبا كيف حالك"})
        assert response.status_code == 200
        assert response.json()["found"] is False

    def test_correlation_id_is_propagated(self, client: TestClient) -> None:
        body = client.post(
            "/resolve",
            json={"text": _CATASTROPHE_Q},
            headers={"X-Correlation-ID": "trace-d185"},
        ).json()
        assert body["trace_id"] == "trace-d185"

    def test_trace_id_generated_when_absent(self, client: TestClient) -> None:
        assert client.post("/resolve", json={"text": "مرحبا"}).json()["trace_id"]

    def test_empty_text_is_rejected_by_contract(self, client: TestClient) -> None:
        assert client.post("/resolve", json={"text": ""}).status_code == 422


class TestDefineContract:
    """`/define`: رمز ⇒ تعريف، أو خطأ **مُهيكَل** `{code, message, trace_id}`."""

    def test_known_symbol(self, client: TestClient) -> None:
        body = client.post("/define", json={"symbol": "C(n,k)"}).json()
        assert body["found"] is True
        assert body["symbol"]["concept_id"] == "combinations"

    def test_alias_resolves(self, client: TestClient) -> None:
        assert client.post("/define", json={"symbol": "c"}).json()["found"] is True

    def test_unknown_symbol_returns_structured_error(self, client: TestClient) -> None:
        response = client.post("/define", json={"symbol": "zzz"})
        assert response.status_code == 200, "خطأ مجال ليس 500 — fail-open"
        body = response.json()
        assert body["found"] is False
        assert body["error"]["code"] == "NOTATION_SYMBOL_UNKNOWN"
        assert body["error"]["trace_id"]


class TestSymbolsContract:
    """`/symbols`: السجلّ كاملاً — يُغذّي بوّابات CI والوكلاء."""

    def test_lists_every_symbol(self, client: TestClient) -> None:
        body = client.get("/symbols").json()
        assert body["count"] == len(body["symbols"]) > 0
        assert "C(n,k)" in {item["symbol"] for item in body["symbols"]}

    def test_every_symbol_is_complete(self, client: TestClient) -> None:
        for item in client.get("/symbols").json()["symbols"]:
            assert item["title"] and item["definition"] and item["example"]


class TestMetricsContract:
    """قانون المهارات ٤: كل نداء مُسجَّل — وبسجلّ مستقلّ لا مشترك."""

    def test_metrics_expose_startup_info(self, client: TestClient) -> None:
        assert "cogniforge_notation_startup_info" in client.get("/metrics").text

    def test_resolution_is_recorded(self, client: TestClient) -> None:
        client.post("/resolve", json={"text": _CATASTROPHE_Q})
        body = client.get("/metrics").text
        assert 'cogniforge_notation_resolutions_total{result="hit"}' in body
        assert "cogniforge_notation_symbol_hits_total" in body

    def test_miss_is_recorded(self, client: TestClient) -> None:
        client.post("/resolve", json={"text": "مرحبا كيف حالك"})
        assert "cogniforge_notation_unknown_total" in client.get("/metrics").text

    def test_registry_is_independent(self) -> None:
        """ممنوع مشاركة `CollectorRegistry` بين الخدمات المصغّرة."""
        from prometheus_client import REGISTRY as GLOBAL_REGISTRY

        from microservices.notation_service.prom_metrics import REGISTRY

        assert REGISTRY is not GLOBAL_REGISTRY


class TestServiceIndependence:
    """قانون الحدود: الخدمة لا تستورد المونوليث ولا خدمةً أخرى."""

    def test_service_source_has_no_app_import(self) -> None:
        from pathlib import Path

        service_dir = Path(__file__).resolve().parents[3] / "microservices/notation_service"
        for path in service_dir.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "from app." not in source, f"{path.name} يستورد المونوليث"
            assert "import app." not in source, f"{path.name} يستورد المونوليث"

    def test_vendored_registry_matches_canonical(self) -> None:
        """النسخة المُوَرَّدة مطابقة للمصدر القانوني (بوّابة `check_notation_parity`)."""
        from pathlib import Path

        root = Path(__file__).resolve().parents[3]
        canonical = (root / "shared/notation/registry.py").read_bytes()
        vendored = (root / "microservices/notation_service/src/notation/registry.py").read_bytes()
        assert canonical == vendored
