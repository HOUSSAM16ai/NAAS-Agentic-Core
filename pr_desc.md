HUMAN:
I reviewed the logs and tested the fallback locally using the fake credentials script. The debug logger triggers precisely.

AGENT:

---

## Why
Telemetry runs on the hot path. Raising exceptions here could break the core flow and cause unexpected drops in execution. However, silently swallowing them makes Prometheus issues untraceable. This change logs them safely.

## Summary
- Replaced `pass` with `logger.debug` in `RetrievalRerankSkill._rec` telemetry exception handler.
- Created `test_retrieval_telemetry_silenced_exception` to verify the error is swallowed and logged.

## Issue Number
Fixes #2358

## How to Test
Run the test suite specifically targeting this skill:
```bash
pytest tests/services/test_retrieval_rerank_skill.py -q
```

## Change Type
- [x] refactor

## Affected Areas
- [x] app core

## Risk & Rollback
- **Risk level:** low
- **Rollback plan:** revert the commit; it restores the `pass` inside the try/except block.

## Validation Evidence
```bash
$ ruff check app/services/skills/retrieval_rerank_skill.py
All checks passed!

$ pytest tests/services/test_retrieval_rerank_skill.py -q
1 passed in 0.93s
```
- [x] `ruff check .`
- [x] `ruff format --check .`
- [x] `pytest ...`

## Video/Screenshots
N/A

## Governance Checklist (Required)
- [x] I updated docs when runtime/CI behavior changed.
- [x] I did not add duplicate CI truth layers.
- [x] I confirmed mergeability depends on `required-ci`.
- [x] I removed or justified any skipped tests.
- [x] I verified no PII or sensitive secrets were added.

## Safeguarding Impact
N/A

## Reviewer Guide
Look at `app/services/skills/retrieval_rerank_skill.py` line 52 to see the new debug statement.
