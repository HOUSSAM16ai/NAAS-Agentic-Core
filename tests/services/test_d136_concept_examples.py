"""
D-136 — أمثلة واعية بالمفهوم + كبح محرّك حالة الفهم regression tests.

يثبت إصلاح regression الـ transcript:
  • المثال واعٍ بالمفهوم: «اعطني مثال» عن product_even ⇒ مثال product_even (لا الحادثة A الأعمى).
  • كل مفهوم في PROPERTY_REGISTRY له `example` ملموس (data-driven).
  • detect_active_concept: «اعطني مثال» (بلا marker) ⇒ المفهوم من السياق (آخر تعريف).
  • كبح D-135: سؤال عن مفهوم خارج مسار نفس-اللون ⇒ decide=None (لا اختطاف لمثال الحادثة A).
  • فحص بنيوي للتوصيل + نجاة حجب D-113.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.services.skills.semantic_property_skill import (
    PROPERTY_REGISTRY,
    get_semantic_property_skill,
)
from app.services.skills.understanding_state_skill import get_understanding_state_skill

ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass
class _G:
    label: str
    count: int
    favorable_combinations: int
    is_possible: bool


@dataclass
class _Combo:
    n: int = 11
    k: int = 3
    total_combinations: int = 165
    same_group_favorable: int = 14
    groups: tuple = (
        _G("كرة حمراء", 4, 4, True),
        _G("كرة بيضاء", 2, 0, False),
        _G("كرة خضراء", 5, 10, True),
    )


# ── B) أمثلة واعية بالمفهوم (PropertySpec.example) ───────────────────────────
class TestConceptExamples:
    def test_every_concept_has_example(self) -> None:
        for pid, spec in PROPERTY_REGISTRY.items():
            assert spec.example.strip(), f"المفهوم {pid} بلا example (D-136)"

    def test_interpret_returns_example(self) -> None:
        out = get_semantic_property_skill().interpret("ماذا نقصد بجداء أرقامها زوجي")
        assert out is not None and out.property_id == "product_even"
        assert out.example and "زوجي" in out.example

    def test_product_even_example_is_not_event_a(self) -> None:
        # جوهر إصلاح الكارثة: مثال product_even ليس مثال الحادثة A (نفس اللون).
        spec = PROPERTY_REGISTRY["product_even"]
        assert "زوجي" in spec.example
        assert "نفس اللون" not in spec.example

    def test_expected_value_example_distinct(self) -> None:
        spec = PROPERTY_REGISTRY["expected_value"]
        assert spec.example and "نفس اللون" not in spec.example


# ── detect_active_concept (من السياق) ────────────────────────────────────────
class TestDetectActiveConcept:
    def test_concept_from_current_message(self) -> None:
        out = get_semantic_property_skill().detect_active_concept("ماذا نقصد بالأمل الرياضي")
        assert out is not None and out.property_id == "expected_value"

    def test_concept_from_history_when_message_has_no_marker(self) -> None:
        # «اعطني مثال» بلا marker ⇒ المفهوم من آخر تعريف في التاريخ (product_even).
        history = [
            {"role": "user", "content": "ماذا نقصد بجداء أرقامها زوجي"},
            {"role": "assistant", "content": "حاصل ضرب الأرقام زوجي إذا حملت كرة رقماً زوجياً."},
        ]
        out = get_semantic_property_skill().detect_active_concept("اعطني مثال لكي أفهم", history)
        assert out is not None and out.property_id == "product_even"

    def test_none_when_no_concept_anywhere(self) -> None:
        out = get_semantic_property_skill().detect_active_concept("اعطني مثال", [])
        assert out is None


# ── A) كبح محرّك حالة الفهم (لا اختطاف) ───────────────────────────────────────
class TestUnderstandingStateNoHijack:
    def test_no_hijack_for_offpath_example_request(self) -> None:
        # سؤال «اعطني مثال» (لا مكوّن مسار شُرح) ⇒ decide=None (لا مثال الحادثة A الافتراضي).
        d = get_understanding_state_skill().decide(
            question="اعطني مثال لكي أفهم",
            history=[
                {"role": "user", "content": "ماذا نقصد بجداء أرقامها زوجي"},
                {"role": "assistant", "content": "حاصل ضرب الأرقام زوجي إذا حملت كرة رقماً زوجياً."},
            ],
            combo=_Combo(),
        )
        assert d is None  # لا اختطاف — يُسلَّم للمعالج الواعي بالمفهوم

    def test_no_hijack_for_offpath_confusion(self) -> None:
        # «لم أفهم» بعد مثال product_even (ليس مكوّن مسار) ⇒ None.
        d = get_understanding_state_skill().decide(
            question="لم أفهم",
            history=[
                {"role": "assistant", "content": "مثال ملموس: الكرة الخضراء رقمها 4 زوجي."},
            ],
            combo=_Combo(),
        )
        assert d is None

    def test_still_acts_on_real_path_gap(self) -> None:
        # لا انحدار: سؤال مسار نفس-اللون الحقيقي ⇒ D-135 يعمل.
        d = get_understanding_state_skill().decide(
            question="لماذا قسمنا على 3!", history=[], combo=_Combo()
        )
        assert d is not None and d.kc_id == "kc_factorial"


# ── فحص بنيوي + نجاة حجب D-113 ───────────────────────────────────────────────
class TestWiringAndRedaction:
    def test_orchestrator_concept_example_handler(self) -> None:
        src = (ROOT / "app/infrastructure/clients/orchestrator_client.py").read_text(
            encoding="utf-8"
        )
        assert "_build_concept_example" in src
        assert "detect_active_concept" in (
            ROOT / "app/services/skills/semantic_property_skill.py"
        ).read_text(encoding="utf-8")

    def test_examples_survive_d113(self) -> None:
        from app.services.skills.answer_redaction_skill import redact_final_answers

        for spec in PROPERTY_REGISTRY.values():
            redacted, _ = redact_final_answers(spec.example, support_level=5)
            assert redacted.strip()  # لا يُمحى المثال بالكامل

    def test_doctrine_version_bumped(self) -> None:
        from app.services.skills.doctrine import (
            SEMANTIC_PROPERTY_DOCTRINE,
            SEMANTIC_PROPERTY_DOCTRINE_VERSION,
            SKILL_DOCTRINE_MANIFEST,
        )

        assert SEMANTIC_PROPERTY_DOCTRINE_VERSION == "1.2.0"
        entry = SKILL_DOCTRINE_MANIFEST["semantic_property"]
        assert entry["version"] == "1.2.0"
        assert entry["rules_count"] == len(SEMANTIC_PROPERTY_DOCTRINE)
