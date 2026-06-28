# Cognitive Lab Philosophy

## Purpose
Establishes the foundational doctrine that CogniForge is not a conversational chatbot, but an interactive "Cognitive Lab" or "Thinking Engine." The chat interface is merely a delivery mechanism; the true core consists of observing, modeling, testing, and improving student reasoning.

## Core Invariant
The system must act as a dynamic laboratory where students build their understanding through interaction, simulation, and discovery, rather than receiving textual explanations.
Any future feature that improves chat while weakening the core pillars (Interactive Object UI, Cognitive Modeling, Error Memory, Adaptive Generation, Simulation) is architecturally incorrect.

## Runtime Implications
- Generative UI rendering must prioritize interactive manipulable objects over static markdown text.
- Intent classification and diagnosis must map to cognitive models rather than just determining a chat response.
- Progression logic must rely on the student's cognitive twin (mastery, errors, latency) rather than stateless chat history.

## Service Mapping
- **UI Layer:** `GenerativeUIRenderer` -> Evolves into an Interactive Canvas/Object Engine.
- **Diagnostic Layer:** `ConceptDiagnosisSkill`, `SocraticEvaluatorSkill` -> Responsible for "Building the Mind" (explaining cognitive flaws, not calculation errors).
- **Modeling Layer:** `TutorStateService`, `BKTEngine` -> Combine to form the "Digital Twin of the Mind."
- **Execution Layer:** `PedagogicalPolicyEngine` -> Drives Adaptive Generation based on identified cognitive weaknesses.
- **Simulation Layer:** Future `SimulationEngine` -> Runs million-trial empirical validations.

## Student Interaction Contract
The platform does not ask "What is the answer?". It asks "What is the structure?"
Students interact by building mental models (e.g., selecting if order matters, choosing combinations vs. permutations, dragging objects) before performing mathematical calculations.

## Acceptance Criteria
- No new features can be introduced that bypass the Cognitive Lab principles to deliver direct textual answers where an interactive or modeling approach is required.
- Architectural design must always reference the 7 Cognitive Lab phases.
