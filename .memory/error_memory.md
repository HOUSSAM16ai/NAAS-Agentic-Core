# Error Memory

## Purpose
Defines the taxonomy and tracking of student errors. The system studies the student's mistakes as closely as it studies their correct answers, using this data to drive diagnostic feedback and dynamic generation.

## Core Invariant
Errors must be differentiated and classified. A computational error is not the same as a conceptual fragility. Each error class must map to a different pedagogical intervention.

## Runtime Implications
- The `SocraticEvaluatorSkill` and `ConceptDiagnosisSkill` must classify errors into specific categories.
- Error taxonomy must include (but is not limited to):
  - Computational error
  - Counting error
  - Representation error
  - Model-selection error
  - Conceptual fragility
- The `TutorStateService` must persist these classified errors to form the student's "weakness profile".

## Service Mapping
- `ConceptDiagnosisSkill`: Identifies the misconception (`target_misconception`).
- `SocraticEvaluatorSkill`: Evaluates student answers against expected cognitive models.
- `TutorStateService`: Persists the Error Memory within the Digital Twin.
- `PedagogicalPolicyEngine`: Consumes Error Memory to determine the next intervention or dynamically generate new challenges.

## Student Interaction Contract
Instead of saying "Wrong answer," the system explains the root cause of the mental error (e.g., "You think order matters here, but..."). The system attacks the weakness by presenting the concept in different ways until the correct mental model is formed.

## Acceptance Criteria
- Every logged error must be classified according to the taxonomy.
- Interventions must be demonstrably linked to the specific class of error detected.
- The Digital Twin must accurately reflect the history and frequency of different error types.
