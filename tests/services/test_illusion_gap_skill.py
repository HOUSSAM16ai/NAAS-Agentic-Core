"""D-212 — `IllusionGapSkill`: الخريطة تُبنى، وتمتنع، ولا تكسر دوراً أبداً."""

from __future__ import annotations

import pytest

from app.services.skills.illusion_gap_skill import (
    IllusionGapInput,
    IllusionGapSkill,
    get_illusion_gap_skill,
)

STREAM = "experimental_sciences"
CONCEPT = "sequences"


def _skill() -> IllusionGapSkill:
    return get_illusion_gap_skill()


class TestIdentity:
    def test_is_a_singleton_base_skill(self) -> None:
        assert get_illusion_gap_skill() is get_illusion_gap_skill()
        assert _skill().name == "illusion_gap"

    def test_run_delegates_to_build(self) -> None:
        payload = IllusionGapInput(stream=STREAM, measurements=[])
        assert _skill().run(payload).model_dump() == _skill().build(payload).model_dump()


class TestHappyPath:
    def test_dangerous_concept_surfaces(self) -> None:
        report = _skill().build(
            IllusionGapInput(
                stream=STREAM,
                measurements=[
                    {
                        "concept_id": CONCEPT,
                        "confidence": 0.9,
                        "durable_mastery": 0.2,
                        "unaided_observations": 6,
                    }
                ],
            )
        )
        assert report.index == pytest.approx(0.7)
        assert [c.concept_id for c in report.dangerous] == [CONCEPT]
        assert report.quadrants["dangerous"] == 1
        assert report.reason == "built"

    def test_decay_applied_when_history_is_known(self) -> None:
        """مع تاريخ مراجعة: نفس الأرقام تُنتج خانةً مختلفة — الخريطة تصف اليوم."""
        base = {
            "concept_id": CONCEPT,
            "confidence": 0.9,
            "durable_mastery": 0.9,
            "unaided_observations": 6,
        }
        fresh = _skill().build(IllusionGapInput(stream=STREAM, measurements=[base]))
        stale = _skill().build(
            IllusionGapInput(
                stream=STREAM,
                measurements=[{**base, "elapsed_days": 42.0, "stability": 6.0}],
            )
        )
        assert fresh.concepts[0].quadrant == "mastered"
        assert stale.concepts[0].quadrant == "dangerous"


class TestHonestAbstention:
    def test_immature_is_counted_and_reported_not_hidden(self) -> None:
        report = _skill().build(
            IllusionGapInput(
                stream=STREAM,
                measurements=[
                    {
                        "concept_id": CONCEPT,
                        "confidence": 0.99,
                        "durable_mastery": 0.01,
                        "unaided_observations": 2,
                    }
                ],
            )
        )
        assert report.concepts == []
        assert report.index is None
        assert report.immature_suppressed == 1
        assert report.reason == "no_mature_measurement"

    def test_empty_input_says_so(self) -> None:
        report = _skill().build(IllusionGapInput(stream=STREAM, measurements=[]))
        assert report.reason == "no_measurements"
        assert report.index is None


class TestNeverBreaksATurn:
    def test_unknown_stream_degrades_to_a_spoken_reason(self) -> None:
        """شعبةٌ مجهولة تُبلَّغ ولا تُسقِط التقرير (نفس عزل BKT — D-074)."""
        report = _skill().build(
            IllusionGapInput(
                stream="not_a_real_stream",
                measurements=[
                    {
                        "concept_id": CONCEPT,
                        "confidence": 0.9,
                        "durable_mastery": 0.2,
                        "unaided_observations": 6,
                    }
                ],
            )
        )
        assert report.index is None
        assert report.reason.startswith("illusion_error")

    def test_unknown_concept_is_rejected_without_killing_the_map(self) -> None:
        report = _skill().build(
            IllusionGapInput(
                stream=STREAM,
                measurements=[
                    {
                        "concept_id": "not_a_real_concept",
                        "confidence": 0.9,
                        "durable_mastery": 0.2,
                        "unaided_observations": 6,
                    },
                    {
                        "concept_id": CONCEPT,
                        "confidence": 0.9,
                        "durable_mastery": 0.2,
                        "unaided_observations": 6,
                    },
                ],
            )
        )
        assert report.reason.startswith("partial")
        assert [c.concept_id for c in report.concepts] == [CONCEPT]
