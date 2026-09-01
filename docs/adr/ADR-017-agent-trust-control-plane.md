# ADR-017: Stage NAAS from action assurance toward an agent trust control plane

- **Status:** Proposed
- **Date:** 2026-09-01
- **Deciders:** project leadership and architecture governance
- **Technical story:** additive product direction; no runtime capability is activated by this decision

## Context

The existing NAAS Verification Layer evaluates supplied agent trajectories across five dimensions and emits evidence-bound verdicts. The live truth file states that it has not yet judged a real third-party agent trajectory. It does not implement inline interception, identity, authorization, human approval, runtime blocking, or recovery.

The emerging agent ecosystem nevertheless creates a durable problem beyond final-output evaluation: software agents increasingly invoke tools and alter external state on behalf of people and organisations. A long-term product direction is needed without presenting planned controls as implemented capabilities.

## Decision drivers

- Preserve the existing trajectory verifier and its evidence model.
- Distinguish current truth from product roadmap.
- Enter through a narrow, testable, multilingual paid problem.
- Avoid a generic observability or prompt-filter product.
- Align with identity, authorization, least privilege, human oversight, audit, and lifecycle-risk standards.
- Make runtime enforcement conditional on measured safety and reliability.
- Preserve the additive-only repository policy.

## Considered options

### 1. Remain an offline verifier only

**Benefit:** smallest scope and lowest operational risk.
**Cost:** may remain a feature or consultancy without a durable control point.

### 2. Build a complete runtime control plane immediately

**Benefit:** ambitious platform narrative.
**Cost:** no customer proof, no external adapter, no decision-quality evidence, and unacceptable critical-path risk. Rejected.

### 3. Use an evidence-gated expansion

Start with external pre-production Agent Action Assurance, then shadow runtime observation, then bounded inline enforcement, and finally multi-agent identity/delegation only after explicit promotion evidence.

## Decision

Adopt option 3 as a **proposed target architecture**.

The product names are:

- **Current wedge:** `NAAS Agent Action Assurance`.
- **Target platform:** `NAAS Agent Trust & Control Plane`.
- **Long-horizon category thesis:** `Autonomous Systems Trust Infrastructure`.

No name changes the current runtime state. [`.memory/naas_verification_truth.md`](../../.memory/naas_verification_truth.md) remains the authority for implementation claims.

The architectural sequence is:

1. authorized external trajectory adapter and evidence bundle;
2. paid, repeatable pre-production assurance;
3. non-blocking shadow runtime with measured decision quality and latency;
4. inline enforcement for one bounded action class with explicit failure policy;
5. identity, delegation, and multi-agent controls after separate architecture and security review.

## Consequences

### Positive

- Preserves the verified core while defining a larger product path.
- Creates explicit promotion gates instead of roadmap-by-prose.
- Separates action assurance from generic output grading without denying competitive overlap.
- Makes runtime safety, availability, privacy, and evidence integrity first-class requirements.

### Negative

- The company may discover that assurance has no independent budget.
- Large security, identity, cloud, and observability platforms can bundle similar controls.
- Inline enforcement introduces latency, availability, and liability risk.
- Multilingual specialization is an entry wedge, not a sufficient global moat.
- Success requires customer-authorized traces and integrations that are not yet present.

## Non-claims

This ADR does not prove market demand, create a customer, authorize testing against third parties, select a policy engine, certify compliance, guarantee safety, or declare any runtime-control module active.

## Validation and revisit triggers

The decision should be revisited when any of the following occurs:

- three unrelated customers pay for substantially the same assurance outcome;
- an external trace adapter and held-out comparison exist;
- shadow-mode evidence supports or rejects inline enforcement;
- platform-native alternatives match the proposed value at lower cost;
- privacy, data-residency, or reliability constraints make the architecture infeasible.

Detailed architecture and gates: [`AGENT_TRUST_CONTROL_PLANE.md`](../architecture/AGENT_TRUST_CONTROL_PLANE.md).
