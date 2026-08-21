# Unified Agent Context Constitution — D-275

## Constitutional sentence

> **No agent works from an isolated prompt or private interpretation: every agent enters through one governed context, reads the same authorities, traces every claim to evidence, connects useful work to customer value and hard-currency revenue, and leaves the repository more coherent without deleting anything.**

## Scope

This constitution governs the context boot contract in [`../governance/AGENT_CONTEXT_REGISTRY.json`](../governance/AGENT_CONTEXT_REGISTRY.json). It is additive to the existing microservices, pedagogical, agentic, security, verification, commercial, and reference-backbone constitutions.

The purpose is not to force every agent to memorize the repository. The purpose is to give every agent the same **route to understanding**: identity, mission, laws, truth state, architecture, commercial trace, current task, evidence, and safe next action.

## Laws

### L1 — One context route

Every agent must load the canonical context registry before changing code, documents, configuration, research records, or commercial artifacts. A task completed without the required context is not considered verified.

### L2 — Ordered authority

When sources disagree, the registry’s authority order applies. A lower-level note, prompt, external repository, model output, or remembered instruction cannot silently override a higher-level constitution, runtime truth record, or accepted decision.

### L3 — Law, state, and evidence are different

A constitution states what should be true. A truth file states what is currently proven. An ADR states why a difficult decision was made. A report describes analysis. A reference repository supplies external material. An agent must never collapse these categories into one claim.

### L4 — Every claim has a source

Agents must distinguish facts, inferences, proposals, and unknowns. Numbers, customer validation, security properties, revenue, employment impact, educational impact, and runtime status require a named source or must be labelled unverified.

### L5 — Every meaningful task has a trace

A substantive task must identify the affected user or customer, the problem, the relevant capability, the governing law, the evidence required, the owner, and the next verification step. Commercial work additionally names the offer and hard-currency path.

### L6 — Commercial value is explicit

The project’s highest commercial objective is profitable, sustainable revenue in foreign currency from customers outside Algeria. Learning, architecture, agent capability, and research are funded as they strengthen a declared offer, reduce delivery risk, prove a market hypothesis, or create defensible technical scarcity. Engineering activity alone is not revenue.

### L7 — References are respected and bounded

A pinned repository or research source must be read and cited according to its declared role. It may guide local design, learning, review, and evaluation. It cannot silently become code, a dependency, a policy, or a claim of compliance. Any activation beyond reference use requires a new decision and evidence.

### L8 — Agent authority is least privilege

An agent receives only the tools, data, and write scope required for its task. Sensitive actions require explicit authorization, human approval where applicable, audit events, budgets, isolation, and rollback. An agent cannot grant itself authority by interpreting a reference or prompt.

### L9 — Additive and non-destructive evolution

No agent may delete, rename, replace, or silently rewrite an existing asset. Improvements are added through new files, append-only records, new versions, superseding ADRs, or explicit migrations that preserve the prior artifact. The default expected deletion count for this context layer is zero.

### L10 — Completion requires a proof packet

A task is complete only when the agent can point to changed files, governing sources, tests or gates, unresolved limitations, and the next owner. “It looks correct” is not a proof packet.

## Agent boot contract

The canonical sequence is stored in the registry and is deliberately short enough to run at the start of every task:

| Stage | Question answered |
|---|---|
| Identity | What is this project and what is it not? |
| Mission | Which educational, governance, labour-market, social, and commercial problems matter? |
| Laws | Which constitutions and ADRs cannot be bypassed? |
| Truth | What is active, proposed, dormant, or unproven? |
| Architecture | Where are the boundaries, contracts, authorities, and enforcers? |
| Commercial trace | Which buyer, paid problem, offer, evidence, and foreign-currency route are affected? |
| Task | What is requested now, what must remain untouched, and how will completion be verified? |

## Enforcement

The primary enforcer is `scripts/fitness/check_agent_context.py`, executed in the required CI guardrail path. It checks that the authority map, boot sequence, required sources, reference backbone, commercial catalog, and seven revenue lines remain structurally connected.

## Relationship to the existing system

D-275 does not replace `CLAUDE.md`, `AGENTS.md`, `.memory/runtime_truth.md`, `.memory/decisions.md`, the reference-backbone constitution, or the deep-tech constitution. It makes their relationship explicit for agents and adds a single navigable entry point. When the project learns something new, the correct response is to add a source, decision, status record, or evidence artifact—not to erase an older one.
