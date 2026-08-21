# Repo Label Map — NAAS-Agentic-Core

This file adapts the canonical triage roles (SKILL.md) to the label vocabulary
actually used in this repository, per `docs/governance/REPOSITORY_GOVERNANCE_MODEL.md`.
Use this mapping wherever SKILL.md says "the mapping should have been provided to you".

## Category roles (canonical → repo label)

| Canonical role | Repo label |
| --- | --- |
| `bug` | `type:bug` (existing vocabulary) |
| `enhancement` | `type:feature` (existing vocabulary) |

Refactor/documentation/security requests reuse the repo's own `type:refactor`,
`type:docs`, `type:security` labels and do not need a canonical category role.

## State roles (canonical → repo status label)

| Canonical role | Repo label | Notes |
| --- | --- | --- |
| `needs-triage` | `status:needs-triage` | entry state for unlabeled issues |
| `needs-info` | `status:blocked` | repo has no `needs-info`; reuse `status:blocked` with a triage note listing missing info |
| `ready-for-agent` | `status:ready` + triage comment with agent brief | `status:ready` = an AFK agent may pick it up |
| `ready-for-human` | `status:ready` + `type:` + comment noting human-only | state distinction lives in the comment, not the label |
| `wontfix` | close the issue | repo has no wontfix label |

## Priority

Use the repo's own `priority:P0/P1/P2` vocabulary when the triage recommendation
includes a priority; the canonical triage skill does not prescribe one.

## Area

Assign the repo's `area:` label (`area:app-core`, `area:microservices`,
`area:ci-cd`, `area:contracts`, `area:governance`) based on the issue's subject,
matching the domain glossary in `docs/governance/` and `CONTEXT.md`.

## Out-of-scope knowledge base

The canonical skill writes rejected enhancements to `.out-of-scope/*.md`. This
repo keeps rejections as governance docs (per governance model —
"no new duplicated governance controls"). New rejections land in
`docs/governance/rejected/<slug>.md` (create lazily) and are linked from the
closing comment, instead of touching `.out-of-scope/` unless that directory
already exists.
