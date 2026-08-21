# Reference Backbone — Runtime Truth

**Decision:** ADR-013
**Constitution:** D-274
**Status date:** 2026-08-21
**Enforcer:** `scripts/fitness/check_reference_backbone.py`
**CI path:** `.github/workflows/ci.yml` → `guardrails` → required-ci

## Current status

| Property | Truth |
|---|---|
| Mandatory references | 15 |
| Pinning | Every reference has a 40-character commit SHA and snapshot URL |
| Runtime imports | 0 by design |
| Git submodules | 0 introduced by this change |
| Existing files deleted | 0 |
| External source verification | GitHub CLI metadata and GitHub API commit lookup on 2026-08-21 |
| Gate result at implementation time | PASS |
| Research evidence record | `docs/research/authoritative-foundations.md` |

## Active use

The backbone is **ACTIVE as a governed reference layer**. Its active use means that architecture and learning decisions may cite the pinned sources and must declare what was adopted and rejected. It does not mean that the external repositories are imported, executed, or treated as runtime authorities.

## Not active

No external reference repository is an active production dependency. No browser automation, public API, agent skill, model implementation, or learning platform was activated by this change. Such activation requires its own contract, owner, security review, evaluation, runtime evidence, and ADR.

## Upgrade conditions

A reference may become a runtime dependency only after a superseding ADR records exact code or package boundaries, license and provenance review, threat model, least-privilege permissions, dependency pinning, tests, observability, rollback, and an explicit decision that the dependency is necessary. Agent-related activation additionally requires identity, authorization, human approval for high-impact actions, isolation, budget limits, audit events, and adversarial evaluation.

## Honesty rule

This file records the state of the local integration. It does not claim that the project has implemented every principle described by the reference repositories. A principle is implemented only when local code, tests, gates, and runtime evidence prove it.
