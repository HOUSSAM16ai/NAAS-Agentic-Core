# Branch Protection Guide (Authoritative)

This repository uses a **single mergeability truth**: `required-ci`.

## Required settings for `main`

- Require pull request before merging: **enabled**
- Require approvals: **1+** (increase to 2 when team grows)
- Dismiss stale approvals when new commits are pushed: **enabled**
- Require review from Code Owners: **enabled**
- Require status checks to pass before merging: **enabled**
- Require branches to be up to date before merging: **enabled**
- Restrict who can push directly to matching branches: **enabled**
- Do not allow bypassing the above settings: **enabled**
- Allow force pushes: **disabled**
- Allow deletions: **disabled**

## Required status checks

Exactly one required check:
- `required-ci`

`required-ci` aggregates **nine** jobs — the live `needs:` list in
`.github/workflows/ci.yml` is the truth, and this list mirrors it:

`lint` · `contracts` · `guardrails` · `test-monolith` · `test-microservices` ·
`frontend-tests` · `skills-structural` · `event-stack-live` · `images-plan` +
`images-build`.

Do **not** require both aggregate and underlying jobs in branch protection.

> **ISS-148 — why this paragraph is spelled out.** It used to say `required-ci`
> aggregates "`lint`, `contracts`, `guardrails`, and `test`" — four jobs, one of
> which (`test`) no longer exists; it was split into `test-monolith` and
> `test-microservices`. Meanwhile `.memory/ci-gates.md` listed a *third*,
> different set as merge-blocking. Three governance documents disagreed about
> the single thing they exist to state. A contributor reading any one of them
> would have been wrong.

### Workflows that are **not** aggregated by `required-ci`

These run on every PR and have no aggregator job, so whether they block a merge
depends on branch-protection settings in GitHub, not on anything in this repo:

`doc-integrity` · `runtime-truth` · `skills-doctrine-gate` ·
`skills-architecture-gate` · `structure-validation` · `frontend-theme-ci` ·
`observability-validation` · `docker-fullstack-gate`.

They are listed here so their status is a **known** unknown rather than an
assumption. Treat them as required in practice: they guard the constitution,
the truth table, and the pedagogical doctrine.

## Why this model

- Prevents duplicated failure surfaces (`build` + `verify` + `required-ci`).
- Keeps PR failure reason obvious in one workflow.
- Reduces configuration drift between docs and GitHub settings.

## Change control

Any change to required checks must update, in one PR:
1. `.github/workflows/ci.yml`
2. `.github/BRANCH_PROTECTION_GUIDE.md`
3. `CONTRIBUTING.md`
