"""Problem decomposition — Polya's four phases + dependency-ordered sub-goals.

A problem-solving lesson is not «here is the answer» but «here is how to break the
problem down». This module models that structurally:

* :data:`POLYA_PHASES` — the canonical four phases (understand → plan → execute →
  review) every solved problem passes through.
* :class:`SubGoal` — one step, tagged with its phase and the sub-goals it depends
  on.
* :class:`Decomposition` — a set of sub-goals whose :meth:`execution_order` is a
  deterministic topological sort (Kahn's algorithm); a cyclic dependency is a
  :class:`ReasoningError`, never a silent wrong order.

Deterministic and dependency-free (standard library only). The LLM narrates a
decomposition; it never decides the ordering — that is computed here.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.core.reasoning.errors import ReasoningError, require_non_empty

#: Polya's four phases of problem solving (How to Solve It, 1945).
POLYA_PHASES: tuple[str, ...] = ("understand", "plan", "execute", "review")
_PHASE_RANK = {phase: i for i, phase in enumerate(POLYA_PHASES)}


@dataclass(frozen=True)
class SubGoal:
    """A single problem-solving step."""

    id: str
    description: str
    phase: str = "execute"
    depends_on: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise ReasoningError("SubGoal.id must be non-empty")
        if self.phase not in _PHASE_RANK:
            raise ReasoningError(f"unknown phase {self.phase!r}; expected one of {POLYA_PHASES}")
        if not isinstance(self.depends_on, tuple):
            object.__setattr__(self, "depends_on", tuple(self.depends_on))


@dataclass(frozen=True)
class Decomposition:
    """A set of sub-goals forming a dependency DAG over one problem."""

    problem: str
    subgoals: tuple[SubGoal, ...]

    def __post_init__(self) -> None:
        require_non_empty(self.subgoals, "subgoals")
        ids = [s.id for s in self.subgoals]
        if len(ids) != len(set(ids)):
            raise ReasoningError("duplicate SubGoal ids in a decomposition")
        known = set(ids)
        for sub in self.subgoals:
            for dep in sub.depends_on:
                if dep not in known:
                    raise ReasoningError(f"SubGoal {sub.id!r} depends on unknown {dep!r}")

    def _by_id(self) -> dict[str, SubGoal]:
        return {s.id: s for s in self.subgoals}

    def execution_order(self) -> list[str]:
        """Topologically ordered sub-goal ids (Kahn's algorithm, deterministic).

        Ties are broken by Polya phase then by id so the order is stable, and a
        dependency cycle raises :class:`ReasoningError`.
        """
        by_id = self._by_id()
        indegree = dict.fromkeys(by_id, 0)
        for sub in self.subgoals:
            for _dep in sub.depends_on:
                indegree[sub.id] += 1

        def _key(sid: str) -> tuple[int, str]:
            return (_PHASE_RANK[by_id[sid].phase], sid)

        ready = sorted((sid for sid, d in indegree.items() if d == 0), key=_key)
        order: list[str] = []
        while ready:
            current = ready.pop(0)
            order.append(current)
            for sub in self.subgoals:
                if current in sub.depends_on:
                    indegree[sub.id] -= 1
                    if indegree[sub.id] == 0:
                        ready.append(sub.id)
            ready.sort(key=_key)

        if len(order) != len(by_id):
            raise ReasoningError("dependency cycle detected — problem cannot be ordered")
        return order

    def by_phase(self) -> dict[str, list[SubGoal]]:
        """Sub-goals grouped by Polya phase (phases with none are omitted)."""
        grouped: dict[str, list[SubGoal]] = {}
        for sub in self.subgoals:
            grouped.setdefault(sub.phase, []).append(sub)
        return grouped


def polya_scaffold(problem: str) -> Decomposition:
    """Return the canonical four-phase scaffold for any problem.

    A deterministic starting decomposition — one sub-goal per Polya phase, each
    depending on the previous — that a caller can specialise. This is the
    «always have a plan» floor: even an unknown problem gets a structured path.
    """
    if not problem or not problem.strip():
        raise ReasoningError("problem text must be non-empty")
    steps = [
        SubGoal("understand", "افهم المعطيات والمطلوب بدقة.", "understand"),
        SubGoal("plan", "اختر استراتيجية ورتّب الخطوات.", "plan", ("understand",)),
        SubGoal("execute", "نفّذ الخطة خطوة بخطوة.", "execute", ("plan",)),
        SubGoal("review", "تحقّق من النتيجة وراجع المنطق.", "review", ("execute",)),
    ]
    return Decomposition(problem=problem, subgoals=tuple(steps))


def decompose(problem: str, subgoals: Sequence[SubGoal] | Iterable[SubGoal]) -> Decomposition:
    """Build a :class:`Decomposition` from explicit sub-goals (validated)."""
    return Decomposition(problem=problem, subgoals=tuple(subgoals))
