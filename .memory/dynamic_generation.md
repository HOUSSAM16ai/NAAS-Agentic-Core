# Dynamic Generation

## Purpose
Defines the adaptive exercise generation engine. The platform must not rely on a static question bank. Exercises are generated dynamically to target specific cognitive weaknesses identified in the Digital Twin.

## Core Invariant
Generation targets cognitive weakness. Never target superficial similarity. The generated exercise must possess an equivalent cognitive weakness, a different context, a different representation, but the *same reasoning challenge*.

## Runtime Implications
- The system must be able to synthesize new problem parameters on the fly that structurally match a specific conceptual fragility (e.g., distinguishing between permutations and combinations).
- The LLM or symbolic engine must validate generated exercises for mathematical correctness and pedagogical intent before presenting them to the student.

## Service Mapping
- `PedagogicalPolicyEngine`: Orchestrates the generation trigger based on the Digital Twin's error memory.
- `ReasoningSkill` / LLM Generation layer: Synthesizes the new problem text and symbolic constraints.

## Student Interaction Contract
If a student struggles with "combinations," the system does not repeat the exact same type of question. It builds a "weakness profile" and presents the same underlying concept in fundamentally different forms until the correct mental model solidifies. No two students will see the exact same sequence of exercises.

## Acceptance Criteria
- Dynamic generation must explicitly map to a tracked conceptual fragility or error.
- Generated questions must vary context and representation while maintaining the core reasoning challenge.
- The system must verify the correctness of dynamically generated content.
