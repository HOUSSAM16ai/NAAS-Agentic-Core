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

Every primitive raises :class:`FoundationsError` on a domain violation, so a
caller never sees a misleading ``0`` or a bare ``ZeroDivisionError``. Placed under
``app/core/`` (not ``app/services/skills/``) because it is a pure computational
library, not a pedagogical Skill — Skills that need verified numbers import from
here instead of re-implementing ``math.comb`` inline.
"""

from __future__ import annotations

from app.core.foundations import (
    algorithms,
    combinatorics,
    information_theory,
    logic,
    number_theory,
    probability,
)
from app.core.foundations.errors import FoundationsError

__all__ = [
    "FoundationsError",
    "algorithms",
    "combinatorics",
    "information_theory",
    "logic",
    "number_theory",
    "probability",
]
