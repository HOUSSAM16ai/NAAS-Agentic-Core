"""Foundational reasoning layer — the project's verified theoretical substrate.

A dependency-free (stdlib-only) toolkit of the foundational sciences the platform
reasons *from* rather than guesses at (CLAUDE.md §0: "symbolic truth before
language" — numbers come from deterministic engines, never the LLM). Six domains:

* ``combinatorics``       — exact counting (nPr, nCr, multinomial, Catalan, Stirling)
* ``number_theory``       — gcd/lcm, deterministic primality, factorization, modular arithmetic
* ``logic``               — propositional truth tables, tautology, satisfiability, entailment
* ``probability``         — discrete distributions (binomial, hypergeometric), expectation, Bayes, stats
* ``information_theory``  — Shannon entropy, KL divergence, mutual information
* ``algorithms``          — search, graph traversal (BFS/DFS/shortest path), empirical big-O

The "first roots" completion (D-183) adds the remaining pre-programming substrate:

* ``linear_algebra``      — vectors, matmul, determinant, rank, solve ``Ax=b`` (Gaussian elimination)
* ``calculus``            — numeric derivative, definite integral (Simpson), limit, Newton root, Taylor
* ``statistics``          — inferential layer: covariance, correlation, OLS regression, CI, t-stat, percentile
* ``optimization``        — gradient descent, golden-section search, bisection root, 2-var linear program
* ``graph_theory``        — components, cycles, topological sort, MST (Kruskal), bipartite, tree
* ``data_structures``     — Stack, Queue, MinHeap, LinkedList, BinarySearchTree (teaching-grade)
* ``formal_languages``    — DFA, small regex engine, Dyck balance, CFG derivation
* ``computability``       — Ackermann, finite-domain decidability, reductions, Halting/Busy-Beaver limits
* ``complexity``          — growth-rate ordering + P/NP/NP-complete/PSPACE catalogue (P vs NP named honestly)

Every primitive raises :class:`FoundationsError` on a domain violation, so a
caller never sees a misleading ``0`` or a bare ``ZeroDivisionError``. Placed under
``app/core/`` (not ``app/services/skills/``) because it is a pure computational
library, not a pedagogical Skill — Skills that need verified numbers import from
here instead of re-implementing ``math.comb`` inline.
"""

from __future__ import annotations

from app.core.foundations import (
    algorithms,
    calculus,
    combinatorics,
    complexity,
    computability,
    data_structures,
    formal_languages,
    graph_theory,
    information_theory,
    linear_algebra,
    logic,
    number_theory,
    optimization,
    probability,
    statistics,
)
from app.core.foundations.errors import FoundationsError

__all__ = [
    "FoundationsError",
    "algorithms",
    "calculus",
    "combinatorics",
    "complexity",
    "computability",
    "data_structures",
    "formal_languages",
    "graph_theory",
    "information_theory",
    "linear_algebra",
    "logic",
    "number_theory",
    "optimization",
    "probability",
    "statistics",
]
