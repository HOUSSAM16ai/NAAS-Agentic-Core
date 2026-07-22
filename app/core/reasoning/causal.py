"""Causal reasoning — directed cause→effect graphs, confounding, counterfactuals.

A :class:`CausalGraph` is a directed graph whose edges mean «cause → effect». On
top of the verified traversal primitives in ``app.core.foundations.algorithms``
it answers the questions a causal-reasoning lesson turns on:

* **Causation vs. correlation** — :meth:`classify_relationship` distinguishes a
  genuine directed cause from a *confounded* pair (two effects of a shared hidden
  cause) that a naïve learner reads as «A causes B».
* **Counterfactuals** — :meth:`counterfactual` performs an intervention (delete a
  node, «what if this had not happened?») and returns the effects that lose all
  their causal support.
* **Acyclicity** — a causal story that loops on itself is flagged, not silently
  accepted.

Deterministic and dependency-free beyond the standard library and
``app.core.foundations``. Structural violations raise :class:`ReasoningError`.
"""

from __future__ import annotations

from collections.abc import Hashable, Iterable

from app.core.foundations import algorithms
from app.core.reasoning.errors import ReasoningError

Node = Hashable


class CausalGraph:
    """A directed cause→effect graph with causal-reasoning queries."""

    def __init__(self) -> None:
        self._adj: dict[Node, list[Node]] = {}

    # ── construction ─────────────────────────────────────────────────────────
    def add_node(self, node: Node) -> None:
        self._adj.setdefault(node, [])

    def add_edge(self, cause: Node, effect: Node) -> None:
        """Record «``cause`` causes ``effect``»."""
        if cause == effect:
            raise ReasoningError(f"a node cannot cause itself: {cause!r}")
        self.add_node(cause)
        self.add_node(effect)
        if effect not in self._adj[cause]:
            self._adj[cause].append(effect)

    @classmethod
    def from_edges(cls, edges: Iterable[tuple[Node, Node]]) -> CausalGraph:
        graph = cls()
        for cause, effect in edges:
            graph.add_edge(cause, effect)
        return graph

    # ── inspection ───────────────────────────────────────────────────────────
    @property
    def nodes(self) -> frozenset[Node]:
        return frozenset(self._adj)

    def adjacency(self) -> dict[Node, list[Node]]:
        """A copy of the adjacency map (consumable by ``foundations.algorithms``)."""
        return {node: list(succ) for node, succ in self._adj.items()}

    def _require_node(self, node: Node) -> None:
        if node not in self._adj:
            raise ReasoningError(f"unknown node {node!r}")

    def is_cause_of(self, cause: Node, effect: Node) -> bool:
        """True iff a directed causal path ``cause → … → effect`` exists."""
        self._require_node(cause)
        self._require_node(effect)
        if cause == effect:
            return False
        return algorithms.shortest_path_length(self._adj, cause, effect) != -1

    def descendants(self, node: Node) -> frozenset[Node]:
        """All effects reachable (directly or transitively) from ``node``."""
        self._require_node(node)
        order = algorithms.bfs_order(self._adj, node)
        return frozenset(order) - {node}

    def ancestors(self, node: Node) -> frozenset[Node]:
        """All causes from which ``node`` is reachable."""
        self._require_node(node)
        return frozenset(other for other in self._adj if node in self.descendants(other))

    def has_cycle(self) -> bool:
        """True iff the graph contains a directed cycle (an ill-formed causal story)."""
        white, grey, black = 0, 1, 2
        colour: dict[Node, int] = dict.fromkeys(self._adj, white)

        def visit(node: Node) -> bool:
            colour[node] = grey
            for succ in self._adj[node]:
                if colour[succ] == grey:
                    return True
                if colour[succ] == white and visit(succ):
                    return True
            colour[node] = black
            return False

        return any(colour[node] == white and visit(node) for node in self._adj)

    def require_acyclic(self) -> None:
        if self.has_cycle():
            raise ReasoningError("causal graph contains a cycle (not a valid DAG)")

    # ── causal-reasoning queries ─────────────────────────────────────────────
    def common_causes(self, a: Node, b: Node) -> frozenset[Node]:
        """Shared ancestors of ``a`` and ``b`` — the confounders behind a correlation."""
        return self.ancestors(a) & self.ancestors(b)

    def classify_relationship(self, a: Node, b: Node) -> str:
        """Classify the relationship ``a`` — ``b``.

        Returns one of ``"causal"`` (a→…→b), ``"reverse_causal"`` (b→…→a),
        ``"confounded"`` (a shared cause makes them correlate without either
        causing the other), or ``"independent"``. This is the deterministic core
        of «correlation is not causation».
        """
        self._require_node(a)
        self._require_node(b)
        if a == b:
            raise ReasoningError("classify_relationship needs two distinct nodes")
        if self.is_cause_of(a, b):
            return "causal"
        if self.is_cause_of(b, a):
            return "reverse_causal"
        if self.common_causes(a, b):
            return "confounded"
        return "independent"

    def counterfactual(self, intervention: Node) -> frozenset[Node]:
        """«What if ``intervention`` had not occurred?»

        Deletes ``intervention`` and returns the set of nodes that were caused
        (directly or transitively) by it and now have **no** remaining causal
        support from any surviving root cause — i.e. the effects that would not
        have happened. A pure intervention (do-operator style), not a heuristic.
        """
        self._require_node(intervention)
        before = self.descendants(intervention)
        if not before:
            return frozenset()

        # Root causes are the nodes with no incoming edge in the ORIGINAL graph.
        # An effect orphaned by the ablation must not be mistaken for a root.
        has_incoming = {succ for succs in self._adj.values() for succ in succs}
        roots = [n for n in self._adj if n not in has_incoming and n != intervention]

        surviving = {n: [s for s in succ if s != intervention] for n, succ in self._adj.items()}
        del surviving[intervention]

        still_supported: set[Node] = set()
        for root in roots:
            still_supported.update(algorithms.bfs_order(surviving, root))
        return frozenset(effect for effect in before if effect not in still_supported)
