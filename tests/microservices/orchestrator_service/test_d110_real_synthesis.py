"""D-110 (Real Synthesis) — اختبارات _compose_answer.

التركيب الحقيقي المرتّب: دمج reasoning (الحل) + research (المراجع) بدل أول-ناجح،
مع composition_confidence ∈ [0,1] دالةً من عدد النواتج الناجحة وتداخلها. حتمي.
"""

from __future__ import annotations

from microservices.orchestrator_service.src.services.skills_pipeline import (
    SkillResult,
    _compose_answer,
)


def _ok(skill: str, data: dict) -> SkillResult:
    return SkillResult(skill=skill, status="success", data=data, duration_ms=1.0)


def _fail(skill: str) -> SkillResult:
    return SkillResult(skill=skill, status="fallback", data={}, duration_ms=0.0)


def test_three_successes_merge_high_confidence() -> None:
    answer, conf = _compose_answer(
        "س",
        _ok("planning", {"plan_steps": ["خطوة"]}),
        _ok("research", {"summary": "مرجع مهم"}),
        _ok("reasoning", {"answer": "الحل العميق"}),
    )
    assert "الحل العميق" in answer
    assert "مرجع مهم" in answer  # دمج حقيقي لا انتقاء
    assert conf >= 0.9


def test_reasoning_plus_research_merges() -> None:
    answer, conf = _compose_answer(
        "س",
        _fail("planning"),
        _ok("research", {"summary": "خلفية"}),
        _ok("reasoning", {"answer": "الجواب"}),
    )
    assert "الجواب" in answer and "خلفية" in answer
    assert 0.7 <= conf < 0.9  # ركنان، reasoning ضمنهما


def test_research_only_lower_confidence() -> None:
    answer, conf = _compose_answer(
        "س", _fail("planning"), _ok("research", {"summary": "ملخص"}), _fail("reasoning")
    )
    assert answer == "ملخص"
    assert conf < 0.55  # ركن واحد بلا reasoning


def test_all_fail_fallback_low_confidence() -> None:
    answer, conf = _compose_answer(
        "سؤالي", _fail("planning"), _fail("research"), _fail("reasoning")
    )
    assert "سؤالي" in answer
    assert conf <= 0.1


def test_fallback_plan_data_only_low_confidence() -> None:
    """لا skill نجح لكن fallback يحمل plan_steps ⇒ نص مهيكل بثقة منخفضة صريحة (0.25)."""
    answer, conf = _compose_answer(
        "س",
        SkillResult("planning", "fallback", {"plan_steps": ["خطة افتراضية"]}, 0.0),
        _fail("research"),
        _fail("reasoning"),
    )
    assert "خطة افتراضية" in answer
    assert conf == 0.25  # n==0 successes — لا يدّعي ثقة عالية


def test_deterministic() -> None:
    args = (
        "س",
        _ok("planning", {"plan_steps": ["أ"]}),
        _ok("research", {"summary": "ب"}),
        _ok("reasoning", {"answer": "ج"}),
    )
    assert _compose_answer(*args) == _compose_answer(*args)


def test_plan_only_structures_answer() -> None:
    answer, conf = _compose_answer(
        "س",
        _ok("planning", {"plan_steps": ["خطوة 1", "خطوة 2"]}),
        _fail("research"),
        _fail("reasoning"),
    )
    assert "خطوة 1" in answer
    assert 0.0 < conf <= 0.55
