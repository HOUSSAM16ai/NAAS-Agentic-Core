# Code Acceptance Constitution — D-277

## Constitutional sentence

> **No agent may add, modify, or enable code from intuition alone: every change must enter through the unified context, name the governing standards and evidence, pass local gates, preserve existing assets, and prove why it belongs in a production product that can create durable customer value and foreign-currency revenue.**

## Scope

This constitution applies to every change packet that claims to add or modify code, workflows, configuration, schemas, service contracts, agent tools, model behavior, deployment assets, or production-facing documentation. It supplements existing CI gates; it does not replace them.

## Laws

### L1 — Context before code

The agent must load `docs/governance/AGENT_CONTEXT_REGISTRY.json`, follow its boot sequence, and identify the authority and truth source for the task before making a change.

### L2 — Standards are named, not implied

The change packet must name the applicable repository sources from `SOURCE_ADOPTION_MATRIX.json` and the applicable evidence sources from `EVIDENCE_CATALOG.json`. A source in `PENDING_CLASSIFICATION` cannot be used as authority until its purpose and local application are reviewed.

### L3 — Local application is mandatory

For every named standard, the packet must state the local path, test, gate, contract, or evidence that applies it. “Inspired by” is not an implementation claim.

### L4 — Production proof

A production-facing change must identify its owner, interfaces, failure behavior, observability, security boundary, test evidence, rollback or containment plan, and current truth status. Building an image or importing a module is not the same as proving a healthy capability.

### L5 — Agent and tool safety

Changes involving agents, models, browsers, external APIs, memory, execution, or sensitive data require identity, least privilege, explicit authorization, human approval where applicable, auditability, budget limits, isolation, and adversarial or negative testing.

### L6 — Commercial traceability

Every substantive change must either name the customer problem, offer, value hypothesis, and foreign-currency path it advances, or record a clear reason why it is a non-commercial foundation change and identify the future enablement it protects. Research activity is not revenue evidence.

### L7 — Academic and research integrity

When a change relies on an academic course, paper, standard, or research claim, the packet must cite the source URL and summarize the relevant principle. Claims beyond the source or local evidence are forbidden.

### L8 — Zero silent deletion

The default deletion count is zero. A change packet with a deletion is rejected by this layer. Historical records remain append-only, and any future migration that genuinely requires deletion must use a separate, explicit migration decision rather than bypassing this gate.

### L9 — Gates cannot self-authorize

An agent cannot weaken, remove, skip, or rewrite the gate that evaluates its own change. Changes to acceptance gates require a separate governance decision, an explanation of the risk, and independent review.

### L10 — Proof packet before merge

The packet must pass machine validation, JSON/schema checks, relevant project gates, `git diff --check`, and an explicit check that no unintended deletion occurred. A green individual test never overrides a failed required gate.

### L11 — Complete curriculum consideration

The agent must load `UNIVERSITY_CURRICULUM_CATALOG.json` and `CURRICULUM_APPLICATION_MATRIX.json`, account for every catalogued course in the packet, and identify the domains that apply to the change. A course may be recorded as not directly applicable only with a reason; it may not be hidden, deleted, or cited as implemented without local evidence.

## Required packet fields

| Field | Required meaning |
|---|---|
| `changed_paths` | Exact files or directories touched. |
| `standards` | Source IDs from the complete adoption matrix, never free-form names only. |
| `evidence` | IDs from the evidence catalog with URLs and relevant scope. |
| `local_application` | How each standard becomes local code, contract, test, gate, or evidence. |
| `production` | Owner, interface, failure behavior, observability, security, rollback, and status. |
| `commercial_trace` | Customer/problem/offer/value/foreign-currency path or a justified foundation exception. |
| `deletions` | Explicit count and list; this layer requires zero. |
| `verification` | Commands and results run before merge. |

## Enforcement

The primary enforcer is `scripts/fitness/check_code_acceptance.py`, executed in the required CI guardrail path. The gate validates the current packet, the source matrix, the evidence catalog, the non-destructive rule, and all referenced local paths. Existing tests and gates remain required; this constitution adds the cross-cutting traceability layer.
