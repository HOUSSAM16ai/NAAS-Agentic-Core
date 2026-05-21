"""Generative UI streaming contract — regression tests.

يغطي عقد بثّ مكوّنات الواجهة التوليدية (ui_component) من الخادم للواجهة:

  1. ``UIComponentPayload`` — التحقق الصارم + رفض المكوّن المجهول.
  2. ``OrchestratorClient._detect_probability_tree`` — كشف الطلب + استخراج
     القيم الاحتمالية + بناء شجرة حتمية.
  3. ``OrchestratorClient._normalize_ui_component_event`` — تمرير الحمولة
     النظيفة + إسقاط (noop) للحمولات المشوَّهة/المجهولة/الضخمة.

هذه الطبقة هي خط الدفاع الأول قبل React Error Boundary على الواجهة.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.contracts.streaming import (
    KNOWN_UI_COMPONENTS,
    MessageType,
    UIComponentPayload,
)
from app.infrastructure.clients.orchestrator_client import OrchestratorClient

# ─── UIComponentPayload ───────────────────────────────────────────────────────


def test_ui_component_type_registered() -> None:
    assert MessageType.UI_COMPONENT.value == "ui_component"


def test_known_components_whitelist() -> None:
    assert "probability_tree" in KNOWN_UI_COMPONENTS
    assert "bkt_hint_display" in KNOWN_UI_COMPONENTS


def test_ui_payload_valid() -> None:
    payload = UIComponentPayload(
        component="probability_tree",
        props={"title": "t", "tree": {"label": "root"}},
        fallback_text="بديل",
    )
    assert payload.component == "probability_tree"
    assert payload.fallback_text == "بديل"


def test_ui_payload_rejects_unknown_component() -> None:
    with pytest.raises(ValidationError):
        UIComponentPayload(component="evil_iframe", props={}, fallback_text="x")


def test_ui_payload_requires_fallback_text() -> None:
    with pytest.raises(ValidationError):
        UIComponentPayload(component="probability_tree", props={}, fallback_text="")


# ─── _detect_probability_tree ──────────────────────────────────────────────────


def test_detect_no_trigger_returns_none() -> None:
    assert OrchestratorClient._detect_probability_tree("اشرح لي قانون نيوتن") is None
    assert OrchestratorClient._detect_probability_tree("") is None
    # ذِكر "احتمال" بلا قيمة رقمية ولا عبارة صريحة → لا تفعيل
    assert OrchestratorClient._detect_probability_tree("ما هو الاحتمال؟") is None


def test_detect_explicit_phrase() -> None:
    props = OrchestratorClient._detect_probability_tree("ارسم شجرة الاحتمالات لهذه المسألة")
    assert props is not None
    assert props["title"] == "شجرة الاحتمالات"
    assert props["is_illustrative"] is True  # لا أرقام → توضيحي
    assert isinstance(props["tree"], dict)
    assert len(props["tree"]["children"]) == 2


def test_detect_english_phrase() -> None:
    props = OrchestratorClient._detect_probability_tree("draw a probability tree diagram")
    assert props is not None


def test_detect_extracts_probabilities() -> None:
    props = OrchestratorClient._detect_probability_tree(
        "احتمال الحدث A هو 0.3 واحتمال B بشرط A هو 0.8"
    )
    assert props is not None
    assert props["is_illustrative"] is False
    branch_a = props["tree"]["children"][0]
    assert branch_a["p"] == 0.3
    # المتمم محسوب حتمياً
    branch_not_a = props["tree"]["children"][1]
    assert branch_not_a["p"] == 0.7
    assert branch_a["children"][0]["p"] == 0.8
    assert branch_a["children"][1]["p"] == pytest.approx(0.2)


def test_detect_percentage_extraction() -> None:
    props = OrchestratorClient._detect_probability_tree("شجرة احتمالات مع نسبة 30%")
    assert props is not None
    assert props["tree"]["children"][0]["p"] == 0.3


# ─── _build_calculated_tree_props (D-075 — real probability calculation) ─────────


def test_calculated_tree_real_fraction_4_over_11() -> None:
    """الخلفية تحسب P(حمراء)=4/11 ديناميكياً، لا 0.5 الوهمية."""
    props = OrchestratorClient._build_calculated_tree_props(
        "كيس فيه 11 كرة: كرتان بيضاوان، أربع كرات حمراء، خمس كرات خضراء. احسب احتمال سحب كرة حمراء"
    )
    assert props is not None
    assert props["calculated"] is True
    assert props["is_illustrative"] is False
    red = next(c for c in props["composition"] if c["label"] == "كرة حمراء")
    assert (red["p_num"], red["p_den"]) == (4, 11)
    # عقد الشجرة تحمل الكسر الدقيق (p_num/p_den)
    first = props["tree"]["children"][0]
    assert first["p_num"] == 4 and first["p_den"] == 11


def test_calculated_tree_generalizes_to_dice() -> None:
    """تعميم (V15): النرد يُنتج رقم زوجي 3/6 لا قيمة وهمية."""
    props = OrchestratorClient._build_calculated_tree_props(
        "نرمي حجر نرد مرقم من 1 إلى 6، ما احتمال الحصول على رقم زوجي؟"
    )
    assert props is not None
    assert props["total"] == 6
    labels = {c["label"]: (c["p_num"], c["p_den"]) for c in props["composition"]}
    assert labels.get("رقم زوجي") == (3, 6)


def test_calculated_tree_none_for_non_probability() -> None:
    assert OrchestratorClient._build_calculated_tree_props("اشرح قانون نيوتن") is None


# ─── _normalize_ui_component_event ──────────────────────────────────────────────


def _client() -> OrchestratorClient:
    # نتجاوز __init__ (الذي يتطلب ORCHESTRATOR_SERVICE_URL) — الدوال المختبَرة
    # لا تستخدم حالة المثيل سوى classmethods للتنظيف.
    return OrchestratorClient.__new__(OrchestratorClient)


def test_normalize_valid_ui_component_passthrough() -> None:
    client = _client()
    out = client._normalize_ui_component_event(
        {
            "type": "ui_component",
            "payload": {
                "component": "probability_tree",
                "props": {"title": "t", "tree": {"label": "r"}},
                "fallback_text": "بديل آمن",
            },
        }
    )
    assert out["type"] == "ui_component"
    assert out["payload"]["component"] == "probability_tree"
    assert out["payload"]["props"]["tree"]["label"] == "r"
    assert out["payload"]["fallback_text"] == "بديل آمن"


def test_normalize_malformed_payload_becomes_noop() -> None:
    client = _client()
    # payload ليس dict
    assert (
        client._normalize_ui_component_event({"type": "ui_component", "payload": "x"})["type"]
        == "noop"
    )
    # component مفقود
    assert (
        client._normalize_ui_component_event(
            {"type": "ui_component", "payload": {"props": {}, "fallback_text": "x"}}
        )["type"]
        == "noop"
    )


def test_normalize_unknown_component_becomes_noop() -> None:
    client = _client()
    out = client._normalize_ui_component_event(
        {
            "type": "ui_component",
            "payload": {"component": "iframe_xss", "props": {}, "fallback_text": "x"},
        }
    )
    assert out["type"] == "noop"


def test_normalize_oversized_props_becomes_noop() -> None:
    client = _client()
    huge = {"blob": "x" * 20000, "tree": {"label": "r"}}
    out = client._normalize_ui_component_event(
        {
            "type": "ui_component",
            "payload": {
                "component": "probability_tree",
                "props": huge,
                "fallback_text": "x",
            },
        }
    )
    assert out["type"] == "noop"


def test_normalize_stream_event_routes_ui_component() -> None:
    """_normalize_stream_event يجب أن يوجّه نوع ui_component للمعالج المخصص."""
    client = _client()
    out = client._normalize_stream_event(
        {
            "type": "ui_component",
            "payload": {
                "component": "probability_tree",
                "props": {"tree": {"label": "r"}},
                "fallback_text": "بديل",
            },
        }
    )
    assert out["type"] == "ui_component"


def test_unknown_event_still_becomes_noop() -> None:
    """الأحداث المجهولة (غير ui_component وغير نصية) تبقى noop كما قبل."""
    client = _client()
    out = client._normalize_stream_event({"type": "some_internal_event", "payload": {}})
    assert out["type"] == "noop"
