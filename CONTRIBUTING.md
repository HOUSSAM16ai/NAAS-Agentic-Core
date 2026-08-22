# Contributing to NAAS-Agentic-Core

This repository enforces **deterministic CI, architectural guardrails, and safeguarding-first governance**.
If your PR passes locally with the commands below, it should be merge-ready for `required-ci`.

## 1) Local setup (source of truth)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
pip install -r requirements-test.txt
```

## 2) Required local checks before opening a PR

Use the canonical entrypoints from the repository root. Do not replace a failing gate with a warning, `|| true`, a skipped job, or a hand-written claim in the PR description.

```bash
git diff --check
python scripts/fitness/check_documentation_contract.py
make gates
make test
```

For a documentation-only change, the documentation contract gate is still mandatory. `make guardrails` is a subset and is not a replacement for `make gates`.

## 3) CI mergeability model

Branch protection should require only one status check:
- `required-ci`

`required-ci` aggregates and blocks on:
- `lint`
- `contracts`
- `guardrails`
- `test`

Do not add extra merge-blocking checks without updating:
1. `.github/workflows/ci.yml`
2. `.github/BRANCH_PROTECTION_GUIDE.md`
3. this `CONTRIBUTING.md`

## 4) Architectural contribution rules

- No direct imports from `app/` inside `microservices/` modules.
- Keep route registries and runtime routes in parity.
- Keep tracing gate checks passing.
- Keep docs/runtime/contracts in sync when behavior changes.
- For live documentation changes, update the single source of truth and `docs/DOCUMENTATION_INDEX.md` in the same PR.
- Read and comply with `docs/DOCUMENTATION_CONTRACT.md`; its gate must pass without weakening the gate itself.

## 5) Dependency policy

- Runtime dependencies: `requirements-prod.txt`.
- Test dependencies: `requirements-test.txt` (extends prod).
- Dev tooling: `requirements-dev.txt` (extends prod).
- Do not add duplicated packages across files with conflicting pins.

## 6) PR quality bar

Every PR must include:

- scope + risk statement
- rollback plan
- exact validation commands executed and their results
- linked issue or rationale for untracked work
- the source of truth changed, if documentation or runtime behavior changed
- explicit disclosure of anything not proven by local or CI checks

Documentation changes must also state whether the file is live, supporting, generated, or archived. Do not duplicate operational facts across multiple live files when a link to the canonical source is sufficient.

Use `.github/PULL_REQUEST_TEMPLATE.md` exactly; do not remove governance sections.

## 7) Security and safeguarding

- Never commit real user data, PII, or secrets.
- For vulnerabilities, use `SECURITY.md` private disclosure channel.
- Youth-safeguarding changes must reference `SAFEGUARDING.md` and `DATA_POLICY.md`.
