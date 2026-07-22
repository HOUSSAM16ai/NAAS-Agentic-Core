"""Mental models — structured entity/relation/dynamics graphs + consistency.

A mental model is how a learner represents a concept: the **entities** in play,
the static **relations** among them, and the **dynamics** (cause→effect rules) that
drive them. This module builds that representation and checks it for coherence:

* contradictory relations (``a is b`` **and** ``a is-not b``) are surfaced;
* the dynamics are compiled into a :class:`~app.core.reasoning.causal.CausalGraph`
  so a self-referential («circular») causal story is detected;
* isolated entities (in the model but connected to nothing) are reported.

Deterministic and dependency-free beyond the standard library and the sibling
``causal`` module. Structural violations raise :class:`ReasoningError`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.reasoning.causal import CausalGraph
from app.core.reasoning.errors import ReasoningError

#: Relation verbs that directly contradict one another when applied to the same pair.
_NEGATION_PAIRS: frozenset[frozenset[str]] = frozenset(
    {
        frozenset({"is", "is_not"}),
        frozenset({"has", "lacks"}),
        frozenset({"causes", "prevents"}),
        frozenset({"increases", "decreases"}),
        frozenset({"before", "after"}),
    }
)


@dataclass(frozen=True)
class Relation:
    """A static triple ``(subject, verb, object)`` in a mental model."""

    subject: str
    verb: str
    object: str


@dataclass(frozen=True)
class ConsistencyReport:
    """The outcome of checking a mental model for coherence."""

    consistent: bool
    contradictions: tuple[tuple[Relation, Relation], ...]
    has_causal_cycle: bool
    isolated_entities: tuple[str, ...]


@dataclass
class MentalModel:
    """A structured representation of a concept: entities, relations, dynamics."""

    name: str
    entities: set[str] = field(default_factory=set)
    relations: list[Relation] = field(default_factory=list)
    dynamics: list[tuple[str, str]] = field(default_factory=list)

    def add_entity(self, entity: str) -> None:
        if not entity or not entity.strip():
            raise ReasoningError("entity name must be non-empty")
        self.entities.add(entity)

    def add_relation(self, subject: str, verb: str, obj: str) -> None:
        """Record a static relation, registering its endpoints as entities."""
        if not verb or not verb.strip():
            raise ReasoningError("relation verb must be non-empty")
        self.add_entity(subject)
        self.add_entity(obj)
        self.relations.append(Relation(subject, verb, obj))

    def add_dynamic(self, cause: str, effect: str) -> None:
        """Record a cause→effect rule, registering its endpoints as entities."""
        self.add_entity(cause)
        self.add_entity(effect)
        self.dynamics.append((cause, effect))

    # ── coherence ────────────────────────────────────────────────────────────
    def _contradictions(self) -> tuple[tuple[Relation, Relation], ...]:
        found: list[tuple[Relation, Relation]] = []
        for i, a in enumerate(self.relations):
            for b in self.relations[i + 1 :]:
                if (
                    a.subject == b.subject
                    and a.object == b.object
                    and frozenset({a.verb, b.verb}) in _NEGATION_PAIRS
                ):
                    found.append((a, b))
        return tuple(found)

    def _causal_cycle(self) -> bool:
        if not self.dynamics:
            return False
        try:
            graph = CausalGraph.from_edges(self.dynamics)
        except ReasoningError:
            # A self-loop dynamic (cause == effect) is itself a degenerate cycle.
            return True
        return graph.has_cycle()

    def isolated_entities(self) -> tuple[str, ...]:
        """Entities that appear in no relation and no dynamic (orphan concepts)."""
        connected: set[str] = set()
        for rel in self.relations:
            connected.add(rel.subject)
            connected.add(rel.object)
        for cause, effect in self.dynamics:
            connected.add(cause)
            connected.add(effect)
        return tuple(sorted(self.entities - connected))

    def check_consistency(self) -> ConsistencyReport:
        """Full coherence report: contradictions, causal cycles, isolated entities."""
        contradictions = self._contradictions()
        has_cycle = self._causal_cycle()
        isolated = self.isolated_entities()
        return ConsistencyReport(
            consistent=not contradictions and not has_cycle,
            contradictions=contradictions,
            has_causal_cycle=has_cycle,
            isolated_entities=isolated,
        )

    def summary(self) -> dict[str, int]:
        """Cardinality summary of the model (for metrics / narration)."""
        return {
            "entities": len(self.entities),
            "relations": len(self.relations),
            "dynamics": len(self.dynamics),
        }
