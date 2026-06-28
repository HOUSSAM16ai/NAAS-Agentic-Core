# Simulation Engine

## Purpose
Defines the Simulation Engine capability, enabling students to interact empirically with abstract concepts. Simulation is a core reasoning tool, not a visual decoration.

## Core Invariant
The simulation engine must allow the student to run empirical trials to observe theoretical concepts converging with reality, answering "What if?" scenarios dynamically.

## Runtime Implications
- The frontend must support high-performance visual rendering for running trials (e.g., millions of coin flips, ball draws).
- The backend must be capable of providing parameters or running heavy Monte Carlo simulations and streaming the results back to the canvas.
- State management must seamlessly handle transitioning between theoretical calculation mode and empirical simulation mode.

## Service Mapping
- `MicroSimulationSkill`: Existing baseline for small-scale simulations.
- Future `SimulationEngine` Microservice/Component: Dedicated to handling large-scale trials, convergence comparisons, and constraint modifications.

## Student Interaction Contract
After every step, the student can explore "What if?" scenarios:
- "What if there were 3 white balls instead of 2?"
- "What if the draw was with replacement?"
- "What if we asked for 'at least' instead of 'exactly'?"
The student can press "Run a million trials" to see results converge with the theoretical probability, understanding *why* the law works.

## Acceptance Criteria
- UI must allow constraint modification and real-time behavioral observation.
- The system must provide visual convergence comparisons.
- Simulations must be integrated as pedagogical steps within the interactive canvas.
