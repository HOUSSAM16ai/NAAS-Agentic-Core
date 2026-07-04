# RFC 001: Unified State & Failure Management (USFM) Architecture

## 1. Introduction

This Request for Comments (RFC) proposes a new architectural standard for the Multi-Agent System (MAS) to resolve systemic failures related to state inconsistency, failure masking, and "error-as-data" anti-patterns.

This architecture is based on recent research in MAS reliability (ICML 2025) and Formal Methods (Lamport's TLA+), aiming to transform the system from a fragile, optimistic orchestrator into a robust, evidence-based, mathematically verified distributed system.

## 2. Problem Statement

The current system suffers from:
1.  **State Mismatch:** The Engine, UI, and Logs have different definitions of "state", leading to UI "jumping" and user confusion.
2.  **Error-as-Data:** Tools return `{type: "error"}` inside results instead of raising exceptions, bypassing failure handling mechanisms (Silent Failure).
3.  **Success Masking:** The system marks missions as `SUCCESS` even when critical components fail, provided the loop completes (False Success).
4.  **Lack of Attribution:** Failures are difficult to trace back to the specific agent or tool that caused them.

## 3. The 8 Pillars of USFM (System Invariants)

### 3.1. Unified State Contract

A single, canonical State Machine (FSM) must define the lifecycle of a mission across all layers (Engine, UI, Logs).

**Phases:** `MISSION_STARTED` -> `CONTEXT_ENRICHMENT` -> `PLANNING` -> `RESEARCH` -> `DESIGN` -> `EXECUTION` -> `REVIEW` -> `MISSION_COMPLETED` (or `FAILED`).

**Transition Rules:** Every transition must have (Reason, Impact, Evidence).

### 3.2. Strict Tool Contracts

Tools must never hide errors. Schema: `{ ok: boolean, data: object|null, error: ErrorSchema|null }`.
**Invariant:** `ok = TRUE => data != NULL /\ error = NULL`.
**Invariant:** `ok = FALSE => error != NULL`.

### 3.3. Success-by-Evidence (Termination Condition)

Final status is **derived**, not assigned.
- `SUCCESS`: All required steps completed AND valid evidence exists for each.
- `PARTIAL_SUCCESS`: Objective met, but non-critical steps failed.
- `FAILED`: Critical step failed or evidence missing.

**Equation:** `FinalStatus = f(TaskResults, Artifacts, Objective)`

### 3.4. Interruptible Orchestration

Support "Pause & Resume" (Checkpointing) for high-risk operations. No blind continuation after failure.

### 3.5. Distributed Correctness (Saga Pattern)

Use Event Sourcing (append-only logs) and Sagas for multi-step operations to ensure atomicity and consistency.

### 3.6. Failure Attribution

Automated diagnosis identifying "Who, When, and Why" for every failure.

### 3.7. Governance (NIST AI RMF)

Adopt a risk management framework (Map, Measure, Manage) for continuous reliability.

### 3.8. Formal Verification & Correctness Proofs (TLA+)

We model the critical logic (State Machine, Termination) using **TLA+** to mathematically prove safety and liveness properties.

**Safety Property (What must never happen):**
- `NoSuccessWithoutEvidence`: A mission cannot reach `SUCCESS` unless all critical tasks have `evidence != NULL`.
- `NoSilentFailure`: A tool failure must always transition the task state to `FAILED` or `RETRY`, never `SUCCESS`.

**Liveness Property (What must eventually happen):**
- `MonotonicProgress`: The system must eventually reach a terminal state (`SUCCESS`, `PARTIAL_SUCCESS`, `FAILED`) and not loop indefinitely.

## 4. Implementation Plan

1.  **Phase 1 (Immediate - Done):**
    - Refactor `search_content` to raise exceptions (Stop Error-as-Data).
    - Add `PARTIAL_SUCCESS` to `MissionStatus`.
    - Update `OvermindOrchestrator` to detect partial failures.

2.  **Phase 2 (Formal Modeling):**
    - Define `docs/architecture/mission_lifecycle.tla` specification.
    - Verify the model using TLC model checker (offline).

3.  **Phase 3 (Long Term):**
    - Implement `ToolResult` schema across all tools.
    - Implement Event Sourcing and Saga checkpoints.

## 5. Acceptance Criteria

- A mission with a failed search query *must* report `PARTIAL_SUCCESS` or `FAILED`, never `SUCCESS`.
- UI *must* show the specific tool error, not a generic "Technical Error".
- The TLA+ model check must pass for all defined invariants.
