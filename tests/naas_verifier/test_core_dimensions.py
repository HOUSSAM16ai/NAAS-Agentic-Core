"""القلب — حالةُ نجاحٍ وحالةُ فشلٍ لكلّ بُعدٍ من الخمسة (D-267 §5 · شرط ترقية الوحدة 1).

⛔ **القانون المُختبَر هنا:** «نظامٌ يفحص `final outcome` وحده هو **مُصحِّح**، لا
مُتحقِّق.» ولذلك أهمّ اختبارٍ في الملفّ هو
`test_final_outcome_alone_never_reports_holds`: مجموعةٌ تفحص النتيجة النهائية وحدها
**لا تستطيع** أن تُصدر `HOLDS` مهما كانت النتيجة صحيحة.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from naas_verifier.core import (
    Constraint,
    ConstraintError,
    ConstraintSet,
    Dimension,
    Evidence,
    EvidenceError,
    EvidenceKind,
    Outcome,
    Step,
    Trajectory,
    TrajectoryError,
    verify,
)


def _trajectory(**overrides) -> Trajectory:
    payload = {
        "trajectory_id": "t-probe",
        "steps": (
            Step(0, "receive", "idle", "normalizing", output="مدخل"),
            Step(1, "normalize", "normalizing", "matching", tool="normalizer", output="مدخل"),
            Step(2, "decide", "matching", "decided", tool="control", output="fired"),
        ),
        "final_output": "fired",
        "language": "ar",
    }
    payload.update(overrides)
    return Trajectory(**payload)


def _always(outcome: Outcome):
    return lambda _trajectory: outcome


def _set(*constraints: Constraint) -> ConstraintSet:
    """مجموعةٌ تُغطّي كلّ بُعدٍ لم يُذكَر بسببٍ منطوق — البوّابة تفرض ذلك."""
    covered = {item.dimension for item in constraints}
    return ConstraintSet(
        constraints=constraints,
        uncovered_reason={
            dimension: "not exercised by this focused unit test"
            for dimension in Dimension
            if dimension not in covered
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# الأبعاد الخمسة — نجاحٌ وفشلٌ لكلٍّ
# ══════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("dimension", list(Dimension))
def test_each_dimension_can_hold(dimension: Dimension):
    verdict = verify(
        _trajectory(),
        _set(Constraint(f"c::{dimension.value}", dimension, "holds", _always(Outcome.HOLDS))),
    )
    row = next(item for item in verdict.dimensions if item.dimension is dimension)
    assert row.outcome is Outcome.HOLDS


@pytest.mark.parametrize("dimension", list(Dimension))
def test_each_dimension_can_be_violated(dimension: Dimension):
    verdict = verify(
        _trajectory(),
        _set(Constraint(f"c::{dimension.value}", dimension, "fails", _always(Outcome.VIOLATED))),
    )
    row = next(item for item in verdict.dimensions if item.dimension is dimension)
    assert row.outcome is Outcome.VIOLATED
    assert verdict.outcome is Outcome.VIOLATED
    assert dimension in verdict.violated_dimensions


# ══════════════════════════════════════════════════════════════════════════════
# ⭐ الفرق بين مُتحقِّقٍ ومُصحِّح
# ══════════════════════════════════════════════════════════════════════════════
def test_final_outcome_alone_never_reports_holds():
    """⛔ فحصُ النتيجة النهائية وحدها لا يُنتج حكم سلامةٍ أبداً — بالبناء لا بالنيّة."""
    verdict = verify(
        _trajectory(),
        _set(Constraint("only-final", Dimension.FINAL_OUTCOME, "ok", _always(Outcome.HOLDS))),
    )
    assert verdict.outcome is Outcome.INCONCLUSIVE
    assert verdict.outcome is not Outcome.HOLDS


def test_all_five_covered_can_report_holds():
    verdict = verify(
        _trajectory(),
        ConstraintSet(
            constraints=tuple(
                Constraint(f"c::{dim.value}", dim, "holds", _always(Outcome.HOLDS))
                for dim in Dimension
            )
        ),
    )
    assert verdict.outcome is Outcome.HOLDS


def test_uncovered_dimension_without_reason_is_rejected():
    """⛔ بُعدٌ متروك بلا سبب — الفراغ يُقرأ نجاحاً (D-206 L11)."""
    with pytest.raises(ConstraintError, match="uncovered dimensions"):
        ConstraintSet(
            constraints=(
                Constraint("c", Dimension.FINAL_OUTCOME, "ok", _always(Outcome.HOLDS)),
            )
        )


def test_uncovered_dimension_with_empty_reason_is_rejected():
    with pytest.raises(ConstraintError, match="empty reason"):
        ConstraintSet(
            constraints=(
                Constraint("c", Dimension.FINAL_OUTCOME, "ok", _always(Outcome.HOLDS)),
            ),
            uncovered_reason={dim: "" for dim in Dimension if dim is not Dimension.FINAL_OUTCOME},
        )


# ══════════════════════════════════════════════════════════════════════════════
# «لا نعرف» تُعلَن ولا تُبتلَع (D-215)
# ══════════════════════════════════════════════════════════════════════════════
def test_raising_predicate_is_inconclusive_not_holds():
    """⛔ قيدٌ ينفجر لا يُقرأ سلامة — نمط D-208 (`except: return []`)."""

    def explode(_trajectory):
        raise RuntimeError("probe blew up")

    verdict = verify(
        _trajectory(),
        _set(Constraint("boom", Dimension.TOOL_USE, "explodes", explode)),
    )
    row = next(item for item in verdict.dimensions if item.dimension is Dimension.TOOL_USE)
    assert row.outcome is Outcome.INCONCLUSIVE
    assert "boom" in row.inconclusive
    assert verdict.outcome is not Outcome.HOLDS


def test_violation_outranks_inconclusive():
    verdict = verify(
        _trajectory(),
        _set(
            Constraint("bad", Dimension.TOOL_USE, "fails", _always(Outcome.VIOLATED)),
            Constraint("unknown", Dimension.STATE_TRANSITIONS, "?", _always(Outcome.INCONCLUSIVE)),
        ),
    )
    assert verdict.outcome is Outcome.VIOLATED


def test_every_dimension_is_recorded_even_after_a_violation():
    """لا «أوّل يفوز»: التقرير يحمل الأبعاد الخمسة كاملةً — المشتري يدفع ثمنها."""
    verdict = verify(
        _trajectory(),
        _set(Constraint("bad", Dimension.OBSERVABLE_OUTCOMES, "fails", _always(Outcome.VIOLATED))),
    )
    assert len(verdict.dimensions) == len(Dimension)


# ══════════════════════════════════════════════════════════════════════════════
# الأنواع ترفض المُدخَل المكسور عند الإنشاء
# ══════════════════════════════════════════════════════════════════════════════
def test_trajectory_without_language_is_rejected():
    with pytest.raises(TrajectoryError, match="language"):
        _trajectory(language="")


def test_out_of_order_steps_are_rejected():
    with pytest.raises(TrajectoryError, match="ordered"):
        _trajectory(
            steps=(
                Step(1, "second", "a", "b"),
                Step(0, "first", "b", "c"),
            )
        )


def test_evidence_without_reproduction_is_rejected():
    """⛔ ادّعاءٌ بلا إعادة إنتاجٍ انطباعٌ لا دليل."""
    with pytest.raises(EvidenceError, match="reproduction"):
        Evidence(
            evidence_id="e1",
            kind=EvidenceKind.EXPLOIT_REPRODUCTION,
            summary="something",
            reproduction="   ",
            source_reference="docs/architecture/NAAS_VERIFICATION_LAYER.md",
        )


def test_duplicate_constraint_ids_are_rejected():
    with pytest.raises(ConstraintError, match="duplicate"):
        _set(
            Constraint("same", Dimension.TOOL_USE, "a", _always(Outcome.HOLDS)),
            Constraint("same", Dimension.FINAL_OUTCOME, "b", _always(Outcome.HOLDS)),
        )
