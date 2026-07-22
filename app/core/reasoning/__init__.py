"""General reasoning layer — the platform's verified *thinking* substrate.

Where ``app.core.foundations`` verifies the platform's *numbers* (combinatorics,
probability, logic tables…), ``app.core.reasoning`` verifies its *reasoning
structure*: the deterministic core of logic, critical thinking, problem solving,
abstraction, causal understanding, and mental-model building. Six domains:

* ``arguments``      — propositional expression tree, entailment-checked validity,
  and formal-fallacy recognition (built on ``foundations.logic``).
* ``causal``         — directed cause→effect graphs, correlation-vs-causation,
  counterfactual interventions (built on ``foundations.algorithms``).
* ``decomposition``  — Polya problem decomposition + dependency-ordered sub-goals.
* ``abstraction``    — generalising instances into patterns, sequence rules, and
  structure-mapping analogies.
* ``mental_model``   — entity/relation/dynamics models with a coherence check.

Every primitive is deterministic and raises :class:`ReasoningError` on a
structural violation — never a misleading silent result. Like ``foundations`` it
lives under ``app/core/`` (a pure computational library, not a pedagogical Skill):
the reasoning Skills in ``app/services/skills/`` import verified structure from
here and add the guarded-LLM narration on top (CLAUDE.md §0 — symbolic truth
before language). Consumes ``app.core.foundations`` — no other app dependencies.
"""

from __future__ import annotations

from app.core.reasoning import (
    abstraction,
    arguments,
    causal,
    decomposition,
    mental_model,
)
from app.core.reasoning.errors import ReasoningError

__all__ = [
    "ReasoningError",
    "abstraction",
    "arguments",
    "causal",
    "decomposition",
    "mental_model",
]
