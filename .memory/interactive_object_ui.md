# Interactive Object UI (Interactive Canvas)

## Purpose
Establishes the Interactive Canvas as the mandatory user interface paradigm for the Cognitive Lab. Problems are translated into manipulable objects rather than long walls of text.

## Core Invariant
Interactive Canvas is mandatory. Interactive problems must become manipulable objects. Text-only rendering for interactive-eligible problems is considered an architectural defect.

## Runtime Implications
- The UI must parse problem scenarios into structural components. For example, a probability problem requires rendering a bag, balls, colors, numbers, draw mode, replacement rules, and ordering constraints.
- The student must be able to drag, drop, rotate, group, and modify these elements.
- Interaction data (e.g., what was clicked, moved, or ignored) must be streamed back to the Cognitive Modeling layer.

## Service Mapping
- `GenerativeUIRenderer` (Frontend): Must support rich, interactive puzzle-like components.
- `OrchestratorClient` / Content Skills: Must output structured JSON data describing the objects and constraints, not just markdown text.

## Student Interaction Contract
The student does not read a long question first. They enter the "world" of the exercise. They see the bag, the balls, the colors. They build the solution themselves within this thinking engine, recreating the scenario like a puzzle.

## Acceptance Criteria
- Problems eligible for object representation must be rendered as interactive components.
- The UI must support manipulation (dragging, counting, grouping).
- Textual Q&A must only serve as an assistive channel alongside the primary Interactive Canvas.
