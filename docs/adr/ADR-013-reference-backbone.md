# ADR-013 — Immutable reference backbone

## Status

Accepted.

## Date

2026-08-21.

## Decision

The repositories listed in [`REFERENCE_BACKBONE.json`](../governance/REFERENCE_BACKBONE.json) are the project’s **mandatory reference backbone**. They are not decorative links and they are not optional reading when a contribution changes architecture, algorithms, agent behavior, security, learning pathways, or engineering quality.

The backbone is enforced by `scripts/fitness/check_reference_backbone.py` and executed in the existing required CI guardrail path. A pull request cannot pass the repository’s aggregate checks if a mandatory source is removed, silently replaced, left unpinned, assigned no adoption boundary, or converted into an unreviewed runtime dependency.

The backbone is **additive**. This decision does not delete or replace existing project files, architectures, services, contracts, or governance. It adds a controlled reference layer above them. Any future change to the reference set, its role, its pinned revision, or its runtime boundary requires a new ADR or a superseding ADR; accepted records are not rewritten in place.

## Context

The project is a large, agentic, educational and research-oriented system. It already contains substantial constitutions, services, contracts, runtime truth records, fitness gates, and operational documentation. The new request is therefore not a request to copy popular repositories into the product. It is a request to make a curated body of foundational knowledge the project’s durable engineering compass without allowing external material to become an uncontrolled supply-chain or architectural dependency.

The adopted structure follows current authoritative guidance. NIST’s AI RMF treats trustworthy AI as a lifecycle concern involving governance, measurement, management, and mapping [1]. NIST’s AI Agent Standards Initiative highlights standards, open protocols, agent identity, authorization, and security evaluation [2]. NIST SSDF organizes secure development around preparing the organization, protecting software, producing well-secured software, and responding to vulnerabilities [3]. OpenSSF Scorecard identifies source, build, dependency, testing, and maintenance risks that can be checked automatically [4]. SLSA v1.2 provides incremental supply-chain guarantees and provenance concepts [5]. Current ADR guidance recommends an append-only record of context, alternatives, decisions, trade-offs, consequences, confidence, and status [6].

## Principles

| Principle | Repository rule | Enforcer or evidence |
|---|---|---|
| **Pinned truth** | Every reference is anchored to an exact commit SHA and snapshot URL. Moving branch links are not sufficient evidence. | `REFERENCE_BACKBONE.json`; `check_reference_backbone.py` |
| **Reference, not dependency** | The backbone informs design, education, evaluation, and review. It does not enter the production import graph or package manifests by default. | `runtime_import: false`; CI gate |
| **Adopt selectively** | Each source declares what the project adopts and what it explicitly does not adopt. | Required `adopted_ar` and `not_adopted_ar` fields |
| **Add, do not delete** | The integration adds records, policy, and enforcement. It does not remove existing project assets. | ADR-013 and review diff |
| **One governed set** | The exact reference set is checked against an explicit expected identifier set so removal cannot redefine the contract. | `EXPECTED_IDS` in the gate |
| **Security before autonomy** | Browser, API, agent, and model references remain research-only until identity, authorization, isolation, auditability, evaluation, and human approval are proven. | Manifest boundaries; existing security gates; future ADRs |
| **Evidence before claims** | Popularity counts and unverified prose are not treated as governance evidence. | Verification fields; research notes |

## Reference roles

The backbone is deliberately layered rather than flattened into a single reading list.

| Layer | References | Required use |
|---|---|---|
| **Orientation** | `developer-roadmap`, `freecodecamp`, `free-programming-books`, `awesome` | Frame learning paths, identify prerequisites, and support contributor onboarding. |
| **Foundations** | `coding-interview-university`, `the-algorithms-python`, `build-your-own-x`, `llms-from-scratch` | Strengthen algorithmic reasoning, implementation literacy, systems understanding, and model literacy. |
| **Architecture** | `system-design-primer`, `system-design-101` | Review scale, failure modes, protocol flows, data trade-offs, and operational consequences. |
| **Craft** | `clean-code-javascript`, `clean-code-book` | Improve clarity, cohesion, naming, responsibility boundaries, and maintainability without overriding project contracts. |
| **Integration and agents** | `public-apis`, `browser-use`, `awesome-claude-skills` | Explore integrations, agent interaction patterns, and skill design under explicit security boundaries. |

## Alternatives considered

| Alternative | Decision | Reason |
|---|---|---|
| Copy the external repositories into this repository | Rejected | It would create license, provenance, maintenance, and content-drift obligations while obscuring which material is actually used. |
| Add all repositories as Git submodules | Rejected | Submodules create an unnecessary build and supply-chain surface and can make local development depend on moving external infrastructure. |
| Add all repositories as production dependencies | Rejected | Educational and reference repositories are not validated runtime components; importing them would violate the project’s boundary and security posture. |
| Keep only prose links in a README | Rejected | Prose cannot enforce pinning, completeness, explicit adoption boundaries, or non-runtime policy. |
| Allow each team to choose its own reference set | Rejected | It would recreate the fragmentation and drift the request is intended to eliminate. New references remain possible, but only through a superseding decision and gate update. |

## Consequences

The positive consequence is a single, inspectable and reviewable foundation that connects learning, algorithms, architecture, code quality, integrations, and agent research to the project’s existing truth discipline. Contributors can see not only what is admired, but what is actually adopted, what remains a research seam, and what is explicitly forbidden.

The negative consequence is governance cost. Updating a pinned reference requires deliberate review, and a new external source cannot be introduced casually. This is intentional: the cost of a visible decision is lower than the cost of an undocumented dependency or an agent capability that enters production without an owner, threat model, or proof.

The backbone is not a substitute for domain-specific engineering evidence. A reference can guide a design review, but the project still requires local contracts, tests, runtime evidence, security checks, observability, and human review before a capability becomes active.

## Supersession rule

If the project needs to remove, rename, replace, or materially reinterpret a backbone reference, create a new ADR that links to ADR-013, preserves the historical record, names the affected capabilities, and updates the manifest and gate in the same reviewed change. Do not edit the accepted decision to make history disappear.

## References

[1]: https://www.nist.gov/itl/ai-risk-management-framework "NIST AI Risk Management Framework"
[2]: https://www.nist.gov/artificial-intelligence/ai-agent-standards-initiative "NIST AI Agent Standards Initiative"
[3]: https://csrc.nist.gov/projects/ssdf "NIST Secure Software Development Framework"
[4]: https://scorecard.dev/ "OpenSSF Scorecard"
[5]: https://slsa.dev/spec/v1.2/ "SLSA Specification v1.2"
[6]: https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-decision-record "Maintain an architecture decision record — Microsoft Azure Well-Architected Framework"
