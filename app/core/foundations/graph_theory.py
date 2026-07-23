"""Graph theory — connectivity, cycles, ordering, spanning trees, colouring.

Structural graph algorithms beyond the traversal primitives in ``algorithms.py``:
connected components, cycle detection (directed & undirected), Kahn topological
sort, minimum spanning tree (Kruskal), bipartite 2-colouring, and a tree check.
Unweighted graphs are adjacency maps ``{node: [neighbours]}``; weighted edges are
``(u, v, weight)`` triples.

Every primitive raises :class:`FoundationsError` on a domain violation (missing
node, negative weight where disallowed, topological sort of a cyclic graph).
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Hashable, Iterable, Mapping, Sequence

from app.core.foundations.errors import FoundationsError

Graph = Mapping[Hashable, Sequence[Hashable]]
WeightedEdge = tuple[Hashable, Hashable, float]


def _nodes(graph: Graph) -> set[Hashable]:
    nodes: set[Hashable] = set(graph)
    for neighbours in graph.values():
        nodes.update(neighbours)
    return nodes


def connected_components(graph: Graph) -> list[list[Hashable]]:
    """Connected components of an **undirected** graph (edges treated both ways)."""
    adj: dict[Hashable, set[Hashable]] = defaultdict(set)
    for node in _nodes(graph):
        adj.setdefault(node, set())
    for node, neighbours in graph.items():
        for nb in neighbours:
            adj[node].add(nb)
            adj[nb].add(node)
    seen: set[Hashable] = set()
    components: list[list[Hashable]] = []
    for start in adj:
        if start in seen:
            continue
        stack = [start]
        component: list[Hashable] = []
        seen.add(start)
        while stack:
            node = stack.pop()
            component.append(node)
            for nb in adj[node]:
                if nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        components.append(sorted(component, key=repr))
    return sorted(components, key=lambda c: repr(c[0]) if c else "")


def is_connected(graph: Graph) -> bool:
    """True when an undirected graph has exactly one connected component."""
    if not _nodes(graph):
        raise FoundationsError("is_connected: graph has no nodes")
    return len(connected_components(graph)) == 1


def has_cycle(graph: Graph, *, directed: bool = False) -> bool:
    """Detect a cycle. ``directed`` uses DFS colours; undirected uses union-find."""
    if directed:
        color: dict[Hashable, int] = {}

        def _visit(node: Hashable) -> bool:
            color[node] = 1  # grey
            for nb in graph.get(node, ()):
                c = color.get(nb, 0)
                if c == 1 or (c == 0 and _visit(nb)):
                    return True
            color[node] = 2  # black
            return False

        return any(color.get(node, 0) == 0 and _visit(node) for node in _nodes(graph))

    parent: dict[Hashable, Hashable] = {}

    def _find(x: Hashable) -> Hashable:
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    for node in _nodes(graph):
        parent.setdefault(node, node)
    seen_edges: set[frozenset[Hashable]] = set()
    for node, neighbours in graph.items():
        for nb in neighbours:
            edge = frozenset((node, nb))
            if len(edge) == 1 or edge in seen_edges:  # self-loop or already counted
                if len(edge) == 1:
                    return True
                continue
            seen_edges.add(edge)
            ra, rb = _find(node), _find(nb)
            if ra == rb:
                return True
            parent[ra] = rb
    return False


def topological_sort(graph: Graph) -> list[Hashable]:
    """Kahn topological order of a DAG; raises :class:`FoundationsError` if cyclic."""
    indegree: dict[Hashable, int] = dict.fromkeys(_nodes(graph), 0)
    for neighbours in graph.values():
        for nb in neighbours:
            indegree[nb] += 1
    queue: deque[Hashable] = deque(sorted((n for n, d in indegree.items() if d == 0), key=repr))
    order: list[Hashable] = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for nb in sorted(graph.get(node, ()), key=repr):
            indegree[nb] -= 1
            if indegree[nb] == 0:
                queue.append(nb)
    if len(order) != len(indegree):
        raise FoundationsError("topological_sort: graph has a cycle — no linear order exists")
    return order


def degree_sequence(graph: Graph) -> list[int]:
    """Descending degree sequence of an undirected graph."""
    adj: dict[Hashable, set[Hashable]] = defaultdict(set)
    for node in _nodes(graph):
        adj.setdefault(node, set())
    for node, neighbours in graph.items():
        for nb in neighbours:
            adj[node].add(nb)
            adj[nb].add(node)
    return sorted((len(v) for v in adj.values()), reverse=True)


def minimum_spanning_tree(edges: Iterable[WeightedEdge]) -> list[WeightedEdge]:
    """Kruskal MST of a weighted undirected graph; raises if it is disconnected."""
    edge_list = [(float(w), u, v) for u, v, w in edges]
    if not edge_list:
        raise FoundationsError("minimum_spanning_tree: no edges provided")
    for w, _u, _v in edge_list:
        if w < 0:
            raise FoundationsError("minimum_spanning_tree: negative weights are not allowed")
    nodes: set[Hashable] = set()
    for _w, u, v in edge_list:
        nodes.update((u, v))
    parent: dict[Hashable, Hashable] = {n: n for n in nodes}

    def _find(x: Hashable) -> Hashable:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    mst: list[WeightedEdge] = []
    for w, u, v in sorted(edge_list, key=lambda e: (e[0], repr(e[1]), repr(e[2]))):
        ru, rv = _find(u), _find(v)
        if ru != rv:
            parent[ru] = rv
            mst.append((u, v, w))
    if len(mst) != len(nodes) - 1:
        raise FoundationsError("minimum_spanning_tree: graph is disconnected — no spanning tree")
    return mst


def is_bipartite(graph: Graph) -> bool:
    """True when the undirected graph admits a proper 2-colouring (no odd cycle)."""
    adj: dict[Hashable, set[Hashable]] = defaultdict(set)
    for node in _nodes(graph):
        adj.setdefault(node, set())
    for node, neighbours in graph.items():
        for nb in neighbours:
            adj[node].add(nb)
            adj[nb].add(node)
    color: dict[Hashable, int] = {}
    for start in adj:
        if start in color:
            continue
        color[start] = 0
        queue: deque[Hashable] = deque([start])
        while queue:
            node = queue.popleft()
            for nb in adj[node]:
                if nb not in color:
                    color[nb] = 1 - color[node]
                    queue.append(nb)
                elif color[nb] == color[node]:
                    return False
    return True


def is_tree(graph: Graph) -> bool:
    """True when an undirected graph is connected and acyclic (``|E| = |V| − 1``)."""
    nodes = _nodes(graph)
    if not nodes:
        raise FoundationsError("is_tree: graph has no nodes")
    edges: set[frozenset[Hashable]] = set()
    for node, neighbours in graph.items():
        for nb in neighbours:
            if node == nb:
                return False  # self-loop
            edges.add(frozenset((node, nb)))
    return len(edges) == len(nodes) - 1 and is_connected(graph)
