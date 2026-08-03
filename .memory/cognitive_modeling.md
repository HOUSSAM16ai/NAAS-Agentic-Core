# Cognitive Modeling (Digital Twin of the Mind)

## Purpose
Defines the "Digital Twin" as a dynamic, continuous model of the student's cognitive state, moving beyond static scoring to track the nuanced "how" and "why" of their learning process.

## Core Invariant
**A present-turn signal outranks any historical trace (D-208 · ISS-149).** A student
who declares confusion is never recorded as having mastered anything, whatever the
last six messages contained — and naming a concept *inside a question about it* is
not evidence of understanding it. Whoever asks about a thing necessarily names it,
so the concept's own name is the worst possible evidence marker. Violating this does
not merely produce a wrong reply: it writes `understood` / `verified` into the
persistent model, **manufacturing** the illusion gap the platform exists to shrink.

Static scores are forbidden as the sole measure of understanding. The Digital Twin must capture a multi-dimensional map of the student's reasoning, including mastered concepts, fragile concepts, error history, decision latency, assistance patterns, and model-selection risk.

## Runtime Implications
- Every interaction must be logged not just as correct/incorrect, but with rich metadata:
  - Latency (time to decision)
  - Selected elements vs. ignored elements
  - Scaffolding required (`support_level`)
- Bayesian Knowledge Tracing (BKT) updates must incorporate cognitive vulnerability flags.

## Service Mapping
- `TutorStateService`: The primary store for the Digital Twin's session and historical state.
- `BKTEngine`: Evolves from simple probability tracking to tracking specific cognitive vulnerabilities and fragility.
- `ConceptDiagnosisSkill`: Identifies the conceptual mapping to feed into the twin.

## Student Interaction Contract
The AI does not start by knowing the answer; it starts by asking: "How are you thinking right now?"
It analyzes where the student looked, what they selected, and how long they took, building a model of their thought process.

## Acceptance Criteria
- **A declared confusion must never produce an `understood` state (D-208).** Enforced by
  `check_confusion_never_an_answer` across all four deciding brains, and by the
  transcript contract's `final_kc_state_not` field — text-only assertions would go
  green even while the model records mastery that never happened.
- The system must differentiate between assisted performance and durable mastery (the Illusion Gap).
- The state must track error history, conceptual fragility, and assistance patterns.
- New features touching user progress must read from and write to the comprehensive Digital Twin, not isolated tables.
