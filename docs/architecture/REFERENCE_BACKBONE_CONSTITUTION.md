# Reference Backbone Constitution — D-274

## Constitutional sentence

> **The project may learn from many ecosystems, but it may not lose its compass: the pinned reference backbone is mandatory context, additive by default, non-runtime by default, and impossible to remove or bypass silently.**

## Scope

This constitution governs the external repositories listed in [`../governance/REFERENCE_BACKBONE.json`](../governance/REFERENCE_BACKBONE.json). Those repositories provide structured reference material for learning paths, algorithms, systems architecture, software craft, integrations, and agent research.

This constitution does not replace the project’s existing architecture, product doctrine, service contracts, security policies, or runtime truth. It adds a durable reference layer that those authorities can use when making decisions.

## Laws

### L1 — Exact membership

The backbone is an explicit set, not a moving search result. Removing a declared reference or adding an unreviewed reference is a CI failure. Changes require a superseding ADR and a corresponding update to the enforcer’s expected set.

### L2 — Immutable snapshots

Every reference is anchored to an exact commit SHA and a snapshot URL. A branch URL may be useful for discovery, but it is not an auditable foundation.

### L3 — No silent adoption

Every source must state its role, what the project adopts, and what the project does not adopt. “Popular” or “recommended” is not an implementation requirement.

### L4 — No uncontrolled coupling

The references are not production imports, package dependencies, Git submodules, agent tools, API credentials, browser sessions, or data sources by default. Activating any such coupling requires a new ADR, a named owner, provenance and license review, a threat model, tests, observability, rollback, and an explicit security decision.

### L5 — Additive integration

The backbone is added without deleting existing project assets. It must not be used as a pretext to remove current constitutions, contracts, gates, services, or evidence. Conflicts are resolved by an explicit decision, never by silent deletion.

### L6 — Evidence before status

A reference can inform a design, but local implementation status still requires local proof: import and call-chain evidence where code is involved, contract tests, security checks, runtime evidence, and human review.

### L7 — Agent safety boundary

Agent and browser references remain research-only until the project proves identity, authorization, least privilege, approval for sensitive actions, isolation, budgets, auditability, adversarial evaluation, and failure containment. Autonomy is not permission.

### L8 — Reproducible knowledge

The project records verification date, method, pinned revision, adoption boundary, rejected boundary, and research provenance. Unverified popularity claims do not become architectural evidence.

### L9 — Append-only decisions

A changed interpretation is recorded as a new ADR that supersedes the old one. Accepted history is not rewritten to hide a change of direction.

## Enforcement

The primary enforcer is `scripts/fitness/check_reference_backbone.py`, which runs in the required `guardrails` path of `.github/workflows/ci.yml`. The manifest and enforcer are also linked from the documentation index and ADR-013.

## Relationship to other constitutions

D-274 is additive to the existing constitutions, including the delivery, agent standards, agentic design, deep-tech, security, pedagogical, and microservices doctrines. It does not create a second runtime truth system. The manifest is the reference-set source of truth; `.memory/reference_backbone_truth.md` records current verification state; ADR-013 records the decision history.
