from __future__ import annotations

from pathlib import Path

"""
M10-S2.1 (ISS-121 / D-154) — معلّم الاحتمالات الحتمي داخل الـ orchestrator.

أول خطوة هجرة roadmap M10-S2: port مستقل (stdlib فقط، صفر import متقاطع) لسُلّم
الكشف التدريجي — خلف علم `ORCHESTRATOR_PROB_TUTOR_ENABLED` (FLAGGED حتى التحقق
الحي في Codespaces — قاعدة الصدق §6.6).
"""

from microservices.orchestrator_service.src.services.overmind.probability_tutor import (
    deterministic_turn,
    fmt_comb,
    norm_for_dedup,
    parse_composition,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_OFFICIAL = (
    _REPO_ROOT / "knowledge_base" / "bac2024_math_experimental_subject1_ex1_ex2.md"
).read_text(encoding="utf-8")


class TestPortIndependence:
    def test_no_cross_imports(self):
        src = (
            _REPO_ROOT
            / "microservices"
            / "orchestrator_service"
            / "src"
            / "services"
            / "overmind"
            / "probability_tutor.py"
        ).read_text(encoding="utf-8")
        assert "from app" not in src and "import app" not in src

    def test_flag_gated_in_synthesizer(self):
        src = (
            _REPO_ROOT
            / "microservices"
            / "orchestrator_service"
            / "src"
            / "services"
            / "overmind"
            / "graph"
            / "search.py"
        ).read_text(encoding="utf-8")
        assert "ORCHESTRATOR_PROB_TUTOR_ENABLED" in src
        assert "probability_tutor" in src


class TestCompositionParsing:
    def test_full_official_content_solution_immune(self):
        comp = parse_composition(_OFFICIAL)
        assert comp is not None
        assert (comp["n"], comp["k"], comp["total"], comp["same"]) == (11, 3, 165, 14)
        labels = {g["label"] for g in comp["groups"]}
        assert labels == {"كرة حمراء", "كرة بيضاء", "كرة خضراء"}

    def test_poisoned_total_rejected_by_denominator_gate(self):
        poisoned = (
            "يحتوي كيس على 14 كرة: أربع كرات حمراء و كرتان بيضاوان و خمس كرات خضراء "
            r"نسحب 3 كرات دفعة واحدة. علماً أن P(B) = \frac{56}{165}"
        )
        assert parse_composition(poisoned) is None

    def test_non_probability_returns_none(self):
        assert parse_composition("ادرس الدالة f(x) = x^2 على المجال [0,1]") is None


class TestProgressiveLadder:
    def test_four_turns_distinct_zero_final_answer(self):
        history: list[str] = []
        texts: list[str] = []
        for turn in ("كيف", "لم أفهم", "لم أفهم", "لم أفهم"):
            t = deterministic_turn(turn, _OFFICIAL, history=history)
            assert t, f"no ladder text for turn {len(texts) + 1}"
            assert "من كل 165" not in t and "14/165" not in t
            for prev in texts:
                assert norm_for_dedup(t) != norm_for_dedup(prev), "verbatim duplicate"
            texts.append(t)
            history.append(t)

    def test_rich_explanation_request_left_to_llm(self):
        rich = (
            "اشرح لي السؤال الأول بالتفصيل الممل مع كل الخطوات والمبررات النظرية "
            "لكل خطوة حتى أفهم المنهجية كاملة ثم اربطها بالدرس"
        )
        assert deterministic_turn(rich, _OFFICIAL) is None

    def test_latex_fmt(self):
        out = fmt_comb(5, 3, 10)
        assert out.startswith("$") and "C_{5}^{3}" in out and "\\dfrac" in out
