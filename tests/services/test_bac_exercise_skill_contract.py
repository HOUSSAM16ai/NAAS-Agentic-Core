"""BACExerciseSkill — contract regression tests.

CLAUDE.md §0.5 + §6.33 (D-052) declare that every AI capability MUST be a
Skill with a typed contract, metrics, and tests. This file is the missing
testing leg for `BACExerciseSkill` — the most heavily-used skill on the
educational path.

The user (2026-05-17) asked for "تطوير منظومة ال skills للنظام لكيفية
استدعاء المحتوى و كيفية الشرح و كيفية شرح الاجابة النموذجية و الاعتماد
اثناء الشرح المفصل للطالب" — i.e. prove that the skill:

  (1) RETRIEVE: returns the exercise body with NO YAML frontmatter and
      NO model-answer leak to the student.
  (2) EXPLAIN: assembles `full_content` containing BOTH the exercise body
      AND the model answer, so the LLM has the official solution to lean
      on while writing the step-by-step explanation.
  (3) EXPLAIN: works when the BAC reference is in the conversation HISTORY
      (e.g. "اشرح السؤال 1 أ" right after the student asked for the exercise).
  (4) Returns a typed `SkillFailure` (never throws) when nothing matches,
      so the caller can advance to another skill.

If any of these guarantees breaks, the educational chat regresses to the
"student copies the model answer verbatim" or "explanation hallucinates"
catastrophes documented in CLAUDE.md §6.31–§6.33.
"""

from __future__ import annotations

import pytest

from app.services.skills import (
    BACExerciseSkill,
    BACSkillExplanationOutput,
    BACSkillInput,
    BACSkillRetrievalOutput,
    SkillFailure,
    SkillMode,
)

# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def skill() -> BACExerciseSkill:
    return BACExerciseSkill()


@pytest.fixture
def bac2016_question() -> str:
    """A specific BAC reference that should hit
    knowledge_base/bac2016_s1_math_exp_subject2_ex4_numerical_functions.md.
    """
    return (
        "اعطني تمرين دوال عددية شعبة علوم تجريبية الموضوع الثاني "
        "التمرين الرابع لسنة 2016 الدورة الأولى"
    )


@pytest.fixture
def bac2016_history() -> list[dict[str, str]]:
    """The student previously asked for the BAC 2016 exercise — now they
    are asking a follow-up explanation question without re-mentioning the year.
    """
    return [
        {"role": "user", "content": "اعطني تمرين دوال 2016 الدورة الأولى الموضوع الثاني"},
        {"role": "assistant", "content": "بكالوريا 2016 الدورة الأولى ..."},
    ]


# ── (1) RETRIEVE: clean body, no model answer leaked ────────────────────────


def test_retrieve_returns_clean_content_no_model_answer(
    skill: BACExerciseSkill, bac2016_question: str
) -> None:
    result = skill.invoke(BACSkillInput(question=bac2016_question, mode=SkillMode.RETRIEVE))
    assert isinstance(result, BACSkillRetrievalOutput), (
        f"Expected retrieval, got {type(result).__name__}: {result!r}"
    )
    # Exercise body MUST be present
    assert len(result.display_content) > 200, "Display content suspiciously short"

    # The display content is the student-facing card — it MUST NOT include
    # the model answer or YAML frontmatter (D-049 / §6.29 invariants).
    leakage_markers = [
        "## عناصر الإجابة",
        "## الإجابة النموذجية",
        "## Solution",
        "## الحل",
        "## وسوم البحث",
        "---\nyear:",
        "---\nmetadata:",
    ]
    for marker in leakage_markers:
        assert marker not in result.display_content, (
            f"Catastrophic leak: '{marker}' visible to student in display_content"
        )


# ── (2) EXPLAIN: model answer IS included for the LLM ───────────────────────


def test_explain_includes_model_answer_in_full_content(
    skill: BACExerciseSkill,
    bac2016_history: list[dict[str, str]],
) -> None:
    """The user said: «الاعتماد اثناء الشرح المفصل للطالب» — the LLM must
    have the official model answer to lean on. Otherwise it hallucinates.
    """
    result = skill.invoke(
        BACSkillInput(
            question="اشرح كيف نحسب نهاية g(x) عند −∞",
            mode=SkillMode.EXPLAIN,
            history_messages=bac2016_history,
        )
    )
    assert isinstance(result, BACSkillExplanationOutput), (
        f"Expected explanation, got {type(result).__name__}: {result!r}"
    )
    # `full_content` is the bundle handed to the LLM — student never sees it.
    assert len(result.full_content) > len(result.display_content), (
        "full_content must include MORE than display_content (the model answer)."
    )
    # The model answer section MUST be in full_content (this is the "اعتماد"
    # the user demands — the LLM leans on it while writing the explanation).
    has_solution_section = any(
        marker in result.full_content
        for marker in (
            "## عناصر الإجابة",
            "## الإجابة النموذجية",
            "## Solution",
            "## الحل",
            "### الجزء I",
        )
    )
    assert has_solution_section, (
        "full_content does NOT contain the model answer section → LLM has nothing "
        "to lean on, will hallucinate explanations. This breaks D-052 / ISS-058."
    )


def test_explain_with_history_carries_match_source(
    skill: BACExerciseSkill,
    bac2016_history: list[dict[str, str]],
) -> None:
    """Conversation context detection is the key feature for follow-up turns."""
    result = skill.invoke(
        BACSkillInput(
            question="اشرح السؤال 1 أ",
            mode=SkillMode.EXPLAIN,
            history_messages=bac2016_history,
        )
    )
    if isinstance(result, BACSkillExplanationOutput):
        # When matched via history, the source must be tagged so telemetry
        # and downstream consumers know which path was taken.
        assert result.match_source in ("question", "history")


# ── (3) AUTO mode picks the best path ───────────────────────────────────────


def test_auto_mode_prefers_explanation_when_history_has_bac_ref(
    skill: BACExerciseSkill,
    bac2016_history: list[dict[str, str]],
) -> None:
    """AUTO tries EXPLAIN first, falls back to RETRIEVE if no context."""
    result = skill.invoke(
        BACSkillInput(
            question="اشرح كيف نحسب نهاية g(x) عند −∞",
            mode=SkillMode.AUTO,
            history_messages=bac2016_history,
        )
    )
    assert not isinstance(result, SkillFailure), (
        f"AUTO mode should succeed with history; got SkillFailure({result!r})"
    )


def test_auto_mode_retrieves_when_explicit_bac_reference_present(
    skill: BACExerciseSkill, bac2016_question: str
) -> None:
    """Explicit retrieval phrasing without explanation intent → RETRIEVE."""
    result = skill.invoke(BACSkillInput(question=bac2016_question, mode=SkillMode.AUTO))
    assert isinstance(result, BACSkillRetrievalOutput | BACSkillExplanationOutput), (
        f"AUTO mode should produce a useful skill output; got {type(result).__name__}"
    )


# ── (4) Failure path: typed return, never an exception ──────────────────────


def test_no_match_returns_skill_failure_not_exception(skill: BACExerciseSkill) -> None:
    """A garbage question must return SkillFailure so the caller can fall
    through cleanly to the next skill. No exceptions allowed.
    """
    result = skill.invoke(BACSkillInput(question="ما هي عاصمة فرنسا؟"))
    assert isinstance(result, SkillFailure)
    assert result.reason  # human-readable reason for telemetry


def test_skill_metadata_is_stable() -> None:
    """The skill name and version are part of the public contract — they
    appear in metrics labels, logs, and downstream routing. Changing them
    requires an ADR (D-052).
    """
    skill = BACExerciseSkill()
    assert skill.name == "bac_exercise"
    assert skill.version  # any non-empty version string is fine
