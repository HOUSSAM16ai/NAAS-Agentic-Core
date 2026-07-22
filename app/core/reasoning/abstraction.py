"""Abstraction & analogy — generalising instances and mapping structure.

Abstraction is «what do these cases share, and what varies?»; analogy is «this new
thing is like that known thing». Both are modelled deterministically:

* :func:`generalize` over a set of feature dicts → the **invariants** (features
  equal across every instance) and the **parameters** (features that vary) — the
  extracted pattern.
* :func:`generalize_sequence` recognises the constant / arithmetic / geometric
  rule behind a numeric sequence and predicts the next term (verified arithmetic,
  never a guess).
* :func:`analogy` structure-maps a source onto a target by aligning shared
  relations, returning the mapping and a confidence in ``[0, 1]``.

Deterministic and dependency-free (standard library only). Empty inputs raise
:class:`ReasoningError`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from itertools import pairwise
from typing import Any

from app.core.reasoning.errors import ReasoningError, require_non_empty


@dataclass(frozen=True)
class Pattern:
    """The result of generalising a set of instances."""

    invariants: dict[str, Any]
    parameters: tuple[str, ...]

    def matches(self, instance: Mapping[str, Any]) -> bool:
        """True iff ``instance`` agrees with every invariant of the pattern."""
        return all(instance.get(k) == v for k, v in self.invariants.items())


def generalize(instances: Sequence[Mapping[str, Any]]) -> Pattern:
    """Extract the shared pattern across ``instances``.

    A feature key is an **invariant** when it is present with the *same* value in
    every instance, and a **parameter** when it appears but varies. Keys missing
    from some instances are treated as parameters (they are not universal).
    """
    require_non_empty(instances, "instances")
    all_keys: set[str] = set()
    for inst in instances:
        all_keys.update(inst.keys())

    invariants: dict[str, Any] = {}
    parameters: list[str] = []
    for key in sorted(all_keys):
        present_everywhere = all(key in inst for inst in instances)
        values = [inst[key] for inst in instances if key in inst]
        if present_everywhere and all(v == values[0] for v in values):
            invariants[key] = values[0]
        else:
            parameters.append(key)
    return Pattern(invariants=invariants, parameters=tuple(parameters))


@dataclass(frozen=True)
class SequenceRule:
    """The recognised rule behind a numeric sequence + its next term."""

    kind: str  # "constant" | "arithmetic" | "geometric" | "unknown"
    step: Fraction | None
    next_term: Fraction | None


def generalize_sequence(values: Sequence[float | int | Fraction]) -> SequenceRule:
    """Recognise a constant / arithmetic / geometric sequence and predict the next term.

    Uses exact :class:`~fractions.Fraction` arithmetic so ``[1, 2, 4, 8]`` is a
    clean geometric ratio 2, not a float approximation. Returns ``kind="unknown"``
    (no ``next_term``) when no simple rule fits.
    """
    if len(values) < 2:
        raise ReasoningError("generalize_sequence needs at least 2 values")
    nums = [Fraction(v) for v in values]

    diffs = [b - a for a, b in pairwise(nums)]
    if all(d == diffs[0] for d in diffs):
        step = diffs[0]
        kind = "constant" if step == 0 else "arithmetic"
        return SequenceRule(kind=kind, step=step, next_term=nums[-1] + step)

    if all(n != 0 for n in nums[:-1]):
        ratios = [b / a for a, b in pairwise(nums)]
        if all(r == ratios[0] for r in ratios):
            ratio = ratios[0]
            return SequenceRule(kind="geometric", step=ratio, next_term=nums[-1] * ratio)

    return SequenceRule(kind="unknown", step=None, next_term=None)


@dataclass(frozen=True)
class Analogy:
    """A structure mapping from a source domain onto a target domain."""

    mapping: dict[str, tuple[Any, Any]]
    confidence: float
    unmapped_source: tuple[str, ...]
    unmapped_target: tuple[str, ...]


def analogy(source: Mapping[str, Any], target: Mapping[str, Any]) -> Analogy:
    """Structure-map ``source`` onto ``target`` over their shared relation keys.

    The mapping aligns every key present in both domains (``source[k] ↔ target[k]``)
    — the analogical correspondence. Confidence is the fraction of the *combined*
    relations that align (Jaccard over keys): a full structural match scores 1.0,
    a partial one less, disjoint domains 0.0.
    """
    if not source or not target:
        raise ReasoningError("analogy needs non-empty source and target")
    s_keys, t_keys = set(source), set(target)
    shared = s_keys & t_keys
    union = s_keys | t_keys
    mapping = {k: (source[k], target[k]) for k in sorted(shared)}
    confidence = len(shared) / len(union) if union else 0.0
    return Analogy(
        mapping=mapping,
        confidence=confidence,
        unmapped_source=tuple(sorted(s_keys - t_keys)),
        unmapped_target=tuple(sorted(t_keys - s_keys)),
    )
