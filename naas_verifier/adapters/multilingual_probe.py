"""مُحوِّل المسابر متعدّدة اللغات — المجال يدخل من هنا وحده (D-267 §3).

يقرأ الذخيرة **بياناتٍ لا استيراداً**، ويبني لكلّ صنفٍ مجموعة قيودٍ تغطّي الأبعاد
الخمسة، ثمّ يُشغِّل الهدف المرجعي ويُصدر حكماً.

⛔ لا يستورد `app/**` ولا `microservices/**`.
"""

from __future__ import annotations

import itertools
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from naas_verifier.core.constraint import Constraint, ConstraintSet, Dimension, Outcome
from naas_verifier.core.evidence import Evidence, EvidenceKind
from naas_verifier.core.trajectory import Trajectory
from naas_verifier.core.verdict import Verdict, verify
from naas_verifier.targets.reference import LEGAL_STATES, run_target

__all__ = ["CorpusError", "build_constraints", "load_corpus", "probe_class"]

CORPUS_PATH = Path(__file__).resolve().parents[1] / "corpus" / "ar_fr_exploit_classes.json"


class CorpusError(RuntimeError):
    """الذخيرة مفقودة أو مكسورة — ⛔ يُرفَع صراحةً ولا يُسقَط صامتاً."""


def load_corpus(path: Path | None = None) -> list[dict[str, Any]]:
    """يقرأ الذخيرة كبيانات. غيابُ الملفّ **خطأٌ منطوق** لا قائمةٌ فارغة."""
    source = path or CORPUS_PATH
    if not source.is_file():
        raise CorpusError(
            f"corpus not found at {source} — run scripts/research/extract_incident_corpus.py"
        )
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CorpusError(f"corpus is not valid JSON: {exc}") from exc
    classes = payload.get("classes")
    if not isinstance(classes, list) or not classes:
        raise CorpusError("corpus contains no classes")
    return classes


# ══════════════════════════════════════════════════════════════════════════════
# القيود — الأبعاد الخمسة، لا واحدٌ منها متروكٌ بلا سبب
# ══════════════════════════════════════════════════════════════════════════════
def _observable_non_empty(trajectory: Trajectory) -> Outcome:
    """مخرَجٌ مرصود فارغ من خطوةٍ أُعطيت مُدخَلاً غير فارغ = محوٌ صامت."""
    for step in trajectory.steps:
        if step.index == 0 and not step.output.strip():
            return Outcome.INCONCLUSIVE
    return Outcome.HOLDS


def _normalization_preserved_content(trajectory: Trajectory) -> Outcome:
    """⭐ البُعد الذي يكشف النمط `lucky`: التطبيع أفرغ النصّ فعبر الضابط بمسارٍ آخر."""
    raw = trajectory.steps[0].output
    normalized = trajectory.steps[1].output
    if not raw.strip():
        return Outcome.INCONCLUSIVE
    if not normalized.strip():
        return Outcome.VIOLATED
    return Outcome.HOLDS


def _marker_removed(marker: str):
    """الثابت الوسطي **المعاكس**: نصٌّ كان يجب أن يُزال فبقي.

    ثابتٌ واحد لكلّ الأصناف كان يفوّت `SYS-ROLE-INJECT` في نمط `lucky`: الضابط
    يُبلِّغ كشفاً والعلامة ما زالت في النصّ المُخزَّن. جذرٌ معاكس يحتاج ثابتاً معاكساً.
    """

    def predicate(trajectory: Trajectory) -> Outcome:
        normalized = trajectory.steps[1].output
        if not normalized.strip():
            return Outcome.VIOLATED
        return Outcome.VIOLATED if marker in normalized else Outcome.HOLDS

    return predicate


def _intermediate_predicate(entry: Mapping[str, Any]):
    """يختار الثابت الوسطي **المُصرَّح** للصنف — لا افتراضَ ضمنيّاً."""
    probe = entry["probe"]
    invariant = str(probe.get("intermediate_invariant", ""))
    if invariant == "marker_removed":
        return _marker_removed(str(probe[str(probe["marker_field"])]))
    if invariant == "content_preserved":
        return _normalization_preserved_content
    raise CorpusError(
        f"{entry['class_id']}: undeclared `intermediate_invariant` — "
        "an unstated invariant would silently read as a pass (D-206 L11)"
    )


def _legal_transitions(trajectory: Trajectory) -> Outcome:
    expected = tuple(itertools.pairwise(LEGAL_STATES))
    return Outcome.HOLDS if trajectory.transitions == expected else Outcome.VIOLATED


def _control_tool_invoked(trajectory: Trajectory) -> Outcome:
    return Outcome.HOLDS if "control" in trajectory.tools_used else Outcome.VIOLATED


def _expected_control_decision(expected_fires: bool):
    def predicate(trajectory: Trajectory) -> Outcome:
        fired = bool(trajectory.metadata.get("control_fired"))
        return Outcome.HOLDS if fired is expected_fires else Outcome.VIOLATED

    return predicate


def build_constraints(entry: Mapping[str, Any]) -> ConstraintSet:
    """مجموعةٌ تغطّي الأبعاد الخمسة لصنفٍ واحد."""
    class_id = str(entry["class_id"])
    expected = bool(entry["probe"]["expect_control_fires"])
    return ConstraintSet(
        constraints=(
            Constraint(
                f"{class_id}::observable",
                Dimension.OBSERVABLE_OUTCOMES,
                "the first observed step must carry the input it was given",
                _observable_non_empty,
            ),
            Constraint(
                f"{class_id}::intermediate",
                Dimension.INTERMEDIATE_CONSTRAINTS,
                "the class-declared intermediate invariant must hold — this is the "
                "dimension a final-outcome grader cannot see",
                _intermediate_predicate(entry),
            ),
            Constraint(
                f"{class_id}::transitions",
                Dimension.STATE_TRANSITIONS,
                f"states must follow {' -> '.join(LEGAL_STATES)} with no skipped state",
                _legal_transitions,
            ),
            Constraint(
                f"{class_id}::tool_use",
                Dimension.TOOL_USE,
                "the control tool must actually be invoked, not assumed",
                _control_tool_invoked,
            ),
            Constraint(
                f"{class_id}::final",
                Dimension.FINAL_OUTCOME,
                f"the control must {'fire' if expected else 'stay clear'} on this input",
                _expected_control_decision(expected),
            ),
        )
    )


def probe_class(entry: Mapping[str, Any], variant: str, language: str) -> Verdict:
    """يُشغِّل صنفاً واحداً على هدفٍ مرجعيّ بلغةٍ واحدة ويُصدر حكماً بدليل."""
    trajectory = run_target(entry["probe"], variant, language)
    evidence = Evidence(
        evidence_id=f"{entry['class_id']}::{variant}::{language}::reproduction",
        kind=EvidenceKind.EXPLOIT_REPRODUCTION,
        summary=str(entry["title_en"]),
        reproduction=str(entry["reproduction"]),
        source_reference=str(entry["spec_reference"]),
        payload={
            "root_cause": str(entry["root_cause"]),
            "language_conditioned": bool(entry["language_conditioned"]),
            "variant": variant,
        },
    )
    return verify(trajectory, build_constraints(entry), evidence=(evidence,))


def probe_all(
    classes: Sequence[Mapping[str, Any]], variant: str, language: str
) -> list[Verdict]:
    return [probe_class(entry, variant, language) for entry in classes]
