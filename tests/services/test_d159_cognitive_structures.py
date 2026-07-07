"""D-159 — الهياكل المعرفية الحقيقية (D-158 Phase 2): اختبارات الانحدار.

تحرس القفزة من «هياكل مزيفة» إلى هياكل معرفية حقيقية:
- WP-A: مخطط `kc_progress` المُهيكَل (stdlib dataclasses، fail-open، توافق خلفي).
- WP-B: FSM التصعيد الدائم (delivered_levels من tutor_state — يَنجو من نافذة التاريخ).
- WP-C: الحالة الدائمة سلطة `understanding_state` (مسح النصّ fallback).
- WP-D: الـ graph الحقيقي بالحواف + `diagnose_root` (التدخّل يستهدف الجذر لا العرَض).
- WP-E: محرّك الدور متعدد العُقد (A→B) — آلة حالات معرفية حقيقية.
- التفعيل: `cognitive_turn_enabled` افتراضه True (قرار المالك بعد E2E) + رافعة الرجوع.

كل الاختبارات حتمية، صفر LLM، صفر شبكة (المحرك الرمزي + التمرين الرسمي المحلي).
"""

from __future__ import annotations

from typing import ClassVar

import pytest

from app.services.skills.answer_redaction_skill import redact_final_answers
from app.services.skills.kc_progress_schema import (
    KCEntry,
    escalation_levels_of,
    make_pending,
    parse_kc_entry,
    pending_of,
)
from app.services.skills.pedagogical_escalation_skill import (
    EscalationInput,
    get_pedagogical_escalation_skill,
)
from app.services.skills.semantic_property_skill import (
    MISCONCEPTION_EDGES,
    MISCONCEPTION_GRAPH,
    PROPERTY_REGISTRY,
    diagnose_root,
)
from app.services.skills.understanding_state_skill import get_understanding_state_skill


# ── WP-A: المخطط المُهيكَل ─────────────────────────────────────────────────────
class TestKCProgressSchema:
    def test_legacy_entry_parses_safely(self):
        entry = parse_kc_entry({"state": "explained", "attempts": 2, "evidence": "weak"})
        assert entry.state == "explained"
        assert entry.attempts == 2
        assert entry.escalation_levels == []  # حقل D-159 غائب في الصفوف القديمة — آمن

    def test_garbage_normalizes_to_safe_defaults(self):
        assert parse_kc_entry({"state": "garbage", "attempts": "x"}).state == "not_addressed"
        assert parse_kc_entry(None).state == "not_addressed"
        assert parse_kc_entry("nonsense").attempts == 0

    def test_round_trip_preserves_payload(self):
        entry = KCEntry(state="understood", attempts=3, evidence="verified")
        entry.mark_delivered("numerator")
        again = parse_kc_entry(entry.to_dict())
        assert again.state == "understood"
        assert again.representations_delivered == ["numerator"]

    def test_to_dict_backward_compatible_keys(self):
        # مفاتيح D-158 كما هي؛ escalation_levels يُكتب فقط عند وجوده (لا تغيير للصفوف القائمة).
        payload = KCEntry().to_dict()
        assert set(payload) == {
            "state",
            "attempts",
            "evidence",
            "difficulty",
            "representations_delivered",
            "last_emitted_hash",
            "updated_turn",
        }
        with_levels = KCEntry(escalation_levels=["L1"]).to_dict()
        assert with_levels["escalation_levels"] == ["L1"]

    def test_mark_delivered_never_duplicates(self):
        entry = KCEntry()
        entry.mark_delivered("numerator")
        entry.mark_delivered("numerator")
        assert entry.representations_delivered == ["numerator"]

    def test_pending_helpers(self):
        assert pending_of({"_pending": make_pending("kc", "step")}) == ("kc", "step")
        assert pending_of({"_pending": {}}) is None
        assert pending_of("bad") is None

    def test_escalation_levels_of_sorted_ints(self):
        kcp = {"c": {"escalation_levels": ["L3", "L1", "bad", "Lx"]}}
        assert escalation_levels_of(kcp, "c") == [1, 3]
        assert escalation_levels_of({}, "c") == []


# ── WP-B: FSM التصعيد الدائم ──────────────────────────────────────────────────
class TestPersistentEscalationFSM:
    BASE: ClassVar[dict] = {
        "concept_id": "conditional_probability",
        "title": "الاحتمال الشرطي",
        "definition": "الاحتمال الشرطي هو إعادة حساب داخل فضاء تقلّص بعد علمنا بوقوع حادثة.",
        "example": "مثال: 10 طلاب، 6 بنظّارة — بعلم النادي العلمي يتقلّص الفضاء.",
        "micro_sim": "محاكاة: 5 أعضاء 3 بنظّارة ⇒ 3 من 5.",
        "intent": "confusion",
        "history": [],  # نافذة فارغة تُحاكي إعادة التشغيل/تجاوز نافذة الـ50 رسالة
    }

    def test_persistent_levels_survive_empty_window(self):
        skill = get_pedagogical_escalation_skill()
        no_mem = skill.decide(EscalationInput(**self.BASE))
        with_mem = skill.decide(EscalationInput(**self.BASE, delivered_levels=[1]))
        assert no_mem.strategy_level == 1  # بلا ذاكرة ⇒ يبدأ من التعريف
        assert with_mem.strategy_level == 2  # الذاكرة الدائمة تمنع تكرار L1

    def test_all_levels_persisted_exhausts_ladder(self):
        skill = get_pedagogical_escalation_skill()
        decision = skill.decide(EscalationInput(**self.BASE, delivered_levels=[1, 2, 3]))
        assert decision.action == "exhausted"

    def test_text_scan_fallback_still_unions(self):
        # الأدوار السابقة على التخزين: مسح النصّ يبقى شبكة أمان (الاتحاد).
        skill = get_pedagogical_escalation_skill()
        payload = dict(self.BASE)
        payload["history"] = [{"role": "assistant", "content": self.BASE["definition"]}]
        decision = skill.decide(EscalationInput(**payload))
        assert decision.strategy_level == 2  # L1 مُكتشَف من النصّ رغم غياب الحالة الدائمة


# ── WP-D: الـ graph الحقيقي بالحواف ────────────────────────────────────────────
class TestMisconceptionGraphEdges:
    def test_edges_exist_and_reference_known_concepts(self):
        assert len(MISCONCEPTION_EDGES) >= 10
        known = {spec.concept_id for spec in PROPERTY_REGISTRY.values()}
        known |= {n.bkt_concept for nodes in MISCONCEPTION_GRAPH.values() for n in nodes}
        known |= set(MISCONCEPTION_GRAPH.keys())
        for edge in MISCONCEPTION_EDGES:
            assert edge.relation in ("prerequisite_of", "confused_with")
            assert edge.source in known, f"unknown source {edge.source}"
            assert edge.target in known, f"unknown target {edge.target}"

    def test_root_diagnosis_targets_weak_prerequisite(self):
        kcp = {"product_meaning": {"state": "explained", "evidence": "weak"}}
        root = diagnose_root("product_zero", kcp)
        assert root is not None
        assert root.root_concept_id == "product_meaning"
        assert "جذر الصعوبة" in root.intervention_text

    def test_no_persistent_record_means_no_blind_intervention(self):
        assert diagnose_root("product_zero", {}) is None
        assert diagnose_root("product_zero", None) is None

    def test_verified_prerequisite_is_not_weak(self):
        kcp = {"product_meaning": {"state": "explained", "evidence": "verified"}}
        assert diagnose_root("product_zero", kcp) is None

    def test_root_intervention_survives_redaction(self):
        kcp = {"product_meaning": {"state": "explained", "evidence": "weak"}}
        root = diagnose_root("product_zero", kcp)
        redacted, hits = redact_final_answers(root.intervention_text)
        assert redacted == root.intervention_text
        assert hits == 0


# ── WP-C: سلطة الحالة الدائمة في understanding_state ──────────────────────────
class TestUnderstandingStatePersistentAuthority:
    @pytest.fixture()
    def combo(self):
        from app.infrastructure.clients.orchestrator_client import OrchestratorClient

        combo = OrchestratorClient._load_canonical_combinations("كيف نحسب الحادثة A", [])
        assert combo is not None
        return combo

    def test_persistent_state_wins_over_empty_window(self, combo):
        skill = get_understanding_state_skill()
        kcs = skill.knowledge_components(combo)
        first = sorted(kcs, key=lambda c: c.order)[0]
        no_mem = skill.understanding_state([], kcs)
        with_mem = skill.understanding_state(
            [], kcs, kc_progress={first.kc_id: {"state": "understood"}}
        )
        assert no_mem[first.kc_id] == "not_addressed"
        assert with_mem[first.kc_id] == "understood"

    def test_monotone_upgrade_only(self, combo):
        # الدائم يرفع ولا يُنزِل ما أثبته النصّ (مناعة من سجل قديم فاسد).
        skill = get_understanding_state_skill()
        kcs = skill.knowledge_components(combo)
        first = sorted(kcs, key=lambda c: c.order)[0]
        history = [
            {"role": "assistant", "content": first.representations[0]},
            {"role": "user", "content": " ".join(first.evidence_markers[:1])},
        ]
        states = skill.understanding_state(
            history, kcs, kc_progress={first.kc_id: {"state": "not_addressed"}}
        )
        assert states[first.kc_id] == "understood"  # النصّ أثبت — الدائم لا يُنزِل

    def test_decision_reports_understood_kc(self, combo):
        skill = get_understanding_state_skill()
        kcs = skill.knowledge_components(combo)
        first = sorted(kcs, key=lambda c: c.order)[0]
        history = [{"role": "assistant", "content": first.representations[0]}]
        decision = skill.decide(
            question=" ".join(first.evidence_markers[:1]),
            history=history,
            combo=combo,
            kc_progress={},
        )
        assert decision is not None
        if decision.action in ("advance", "mastered"):
            assert decision.understood_kc_id == first.kc_id


# ── WP-A/WP-E: محرّك الدور متعدد العُقد A→B ────────────────────────────────────
class TestMultiKCCognitiveTurn:
    def _drive(self, questions: list[str]) -> tuple[list[str], dict]:
        from app.infrastructure.clients.orchestrator_client import (
            OrchestratorClient as TutorClient,
        )

        tutor_state: dict = {"kc_progress": {}, "turn_count": 0}
        history: list[dict] = []
        emitted: list[str] = []
        for question in questions:
            text, delta = TutorClient._cognitive_turn(question, history, tutor_state)
            if text:
                history.append({"role": "user", "content": question})
                history.append({"role": "assistant", "content": text})
                emitted.append(text)
                kcp = tutor_state.setdefault("kc_progress", {})
                for key, val in (delta or {}).items():
                    kcp[key] = val
                tutor_state["turn_count"] = int(tutor_state.get("turn_count") or 0) + 1
                tutor_state.pop("kc_progress_delta", None)
        return emitted, tutor_state

    def test_full_a_to_b_state_machine(self):
        emitted, state = self._drive(
            [
                "كيف نحسب الحادثة A",
                "هل هي 14 على 165",
                "الكرات الفردية عددها 8",
                "هل هي 56 من 165",
            ]
        )
        assert len(emitted) == 4
        kcp = state["kc_progress"]
        assert parse_kc_entry(kcp.get("prob_event_a")).state == "understood"
        assert parse_kc_entry(kcp.get("prob_event_b")).state == "understood"
        # صفر تكرار حرفي + الانتقال A→B مذكور
        assert len(set(emitted)) == len(emitted)
        assert "الحادثة B" in emitted[1]

    def test_b_seeded_with_pending_after_a_mastered(self):
        _, state = self._drive(["كيف نحسب الحادثة A", "هل هي 14 على 165"])
        kcp = state["kc_progress"]
        entry_b = parse_kc_entry(kcp.get("prob_event_b"))
        assert "diagnostic_probe" in entry_b.representations_delivered
        assert pending_of(kcp) == ("prob_event_b", "parity")

    def test_b_texts_survive_redaction(self):
        emitted, _ = self._drive(
            [
                "كيف نحسب الحادثة A",
                "هل هي 14 على 165",
                "الكرات الفردية عددها 8",
                "هل هي 56 من 165",
            ]
        )
        for text in emitted[2:]:
            redacted, _hits = redact_final_answers(text)
            assert redacted == text  # نمط _fmt_comb + أسئلة توليد — لا كشف يُحجب

    def test_probe_has_no_computed_numbers(self):
        emitted, _ = self._drive(["كيف نحسب الحادثة A"])
        assert "165" not in emitted[0]
        assert "14" not in emitted[0]


# ── التفعيل (D-159): الافتراض ON + رافعة الرجوع ────────────────────────────────
class TestActivationDefaults:
    def test_flag_default_on(self, monkeypatch):
        monkeypatch.delenv("COGNITIVE_TURN_ENABLED", raising=False)
        from app.core.feature_flags import cognitive_turn_enabled

        assert cognitive_turn_enabled() is True

    def test_env_rollback_lever(self, monkeypatch):
        monkeypatch.setenv("COGNITIVE_TURN_ENABLED", "0")
        from app.core.feature_flags import cognitive_turn_enabled

        assert cognitive_turn_enabled() is False

    def test_settings_default_matches_flag(self):
        # لا افتراض متعارض بين settings و feature_flags (جذر ISS-124 #4 لا يعود).
        from app.core.settings.base import AppSettings

        assert AppSettings.model_fields["COGNITIVE_TURN_ENABLED"].default is True
