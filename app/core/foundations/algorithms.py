"""Algorithms & data structures — teaching-grade search, graph traversal, complexity.

Deterministic, dependency-free implementations of the canonical algorithms a
first course covers, plus a small empirical big-O classifier. Graphs are plain
adjacency maps ``{node: [neighbours]}``.
"""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Hashable, Mapping, Sequence

from app.core.foundations.errors import FoundationsError

Graph = Mapping[Hashable, Sequence[Hashable]]


def binary_search(sorted_values: Sequence[float], target: float) -> int:
    """Return the index of ``target`` in an ascending sequence, or -1 if absent (O(log n))."""
    lo, hi = 0, len(sorted_values) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        value = sorted_values[mid]
        if value == target:
            return mid
        if value < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1


def bfs_order(graph: Graph, start: Hashable) -> list[Hashable]:
    """Breadth-first visitation order from ``start`` (O(V + E))."""
    _require_node(graph, start)
    seen = {start}
    queue: deque[Hashable] = deque([start])
    order: list[Hashable] = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for neighbour in graph.get(node, ()):
            if neighbour not in seen:
                seen.add(neighbour)
                queue.append(neighbour)
    return order


def dfs_order(graph: Graph, start: Hashable) -> list[Hashable]:
    """Depth-first visitation order from ``start`` (iterative, O(V + E))."""
    _require_node(graph, start)
    seen: set[Hashable] = set()
    order: list[Hashable] = []
    stack: list[Hashable] = [start]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        order.append(node)
        # Push neighbours reversed so the first neighbour is explored first.
        for neighbour in reversed(list(graph.get(node, ()))):
            if neighbour not in seen:
                stack.append(neighbour)
    return order


def shortest_path_length(graph: Graph, start: Hashable, goal: Hashable) -> int:
    """Fewest edges from ``start`` to ``goal`` in an unweighted graph, or -1 if unreachable."""
    _require_node(graph, start)
    if start == goal:
        return 0
    seen = {start}
    queue: deque[tuple[Hashable, int]] = deque([(start, 0)])
    while queue:
        node, dist = queue.popleft()
        for neighbour in graph.get(node, ()):
            if neighbour == goal:
                return dist + 1
            if neighbour not in seen:
                seen.add(neighbour)
                queue.append((neighbour, dist + 1))
    return -1


_GROWTH_ORDER = ("O(1)", "O(log n)", "O(n)", "O(n log n)", "O(n^2)", "O(n^3)", "O(2^n)")


def classify_growth(sizes: Sequence[int], costs: Sequence[float]) -> str:
    """Best-fit big-O label for measured ``(size, cost)`` samples.

    Compares the correlation of ``cost`` against each candidate growth model and
    returns the closest — a teaching aid for reasoning about complexity, not a proof.
    """
    if len(sizes) != len(costs):
        raise FoundationsError("classify_growth: sizes and costs must have equal length")
    if len(sizes) < 3:
        raise FoundationsError("classify_growth: need at least 3 samples")
    if any(n <= 0 for n in sizes):
        raise FoundationsError("classify_growth: sizes must be positive")

    best_label = "O(n)"
    best_score = -2.0
    for label in _GROWTH_ORDER:
        predicted = [_growth_value(label, n) for n in sizes]
        score = _pearson(predicted, list(costs))
        if score > best_score:
            best_score = score
            best_label = label
    return best_label


def _growth_value(label: str, n: int) -> float:
    """Predicted cost of growth model ``label`` at input size ``n``."""
    if label == "O(1)":
        return 1.0
    if label == "O(log n)":
        return math.log2(n + 1)
    if label == "O(n)":
        return float(n)
    if label == "O(n log n)":
        return n * math.log2(n + 1)
    if label == "O(n^2)":
        return float(n) ** 2
    if label == "O(n^3)":
        return float(n) ** 3
    return float(2**n)  # O(2^n)


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    mx = math.fsum(xs) / n
    my = math.fsum(ys) / n
    cov = math.fsum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    vx = math.fsum((x - mx) ** 2 for x in xs)
    vy = math.fsum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        return -1.0
    return cov / math.sqrt(vx * vy)


def _require_node(graph: Graph, node: Hashable) -> None:
    if node not in graph:
        raise FoundationsError(f"graph does not contain start node {node!r}")
