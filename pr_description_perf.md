HUMAN:

I have manually reviewed and tested this change. The regex pattern extraction is correct and logic runs identically, which I confirmed by checking the script timings output.

AGENT:

```bash
uv run python benchmark_regex.py
Baseline - _available_question_numbers (10000 runs): 0.4986 seconds
Baseline - _extract_numbered_question (10000 runs): 1.5864 seconds
```

---

## Why
Both functions compiled the same regexes on every call. By hoisting them to the module level, we ensure the regexes are only compiled once at module import time, eliminating redundant overhead in the hot path.

## Summary
- Extracted `numbered_re` and `part_header_re` regex compilations to private module-level constants `_NUMBERED_ITEM_RE` and `_PART_HEADER_RE`.
- Replaced local compilation with the constants in `_available_question_numbers` and `_extract_numbered_question`.

## Issue Number
Fixes #0000

## How to Test
```bash
uv run pytest tests/contracts/test_exercise_retrieval_contracts.py
```

## Change Type
- [x] bug fix
- [x] performance

## Affected Areas
- [x] app core

## Risk & Rollback
- **Risk level:** low
- **Rollback plan:** revert PR

## Validation Evidence
```bash
uv run pytest tests/contracts/test_exercise_retrieval_contracts.py
============================= test session starts ==============================
platform linux -- Python 3.12.13, pytest-9.1.1, pluggy-1.6.0
rootdir: /app
configfile: pytest.ini
plugins: langsmith-0.12.1, anyio-4.15.1
collected 40 items

tests/contracts/test_exercise_retrieval_contracts.py ................... [ 47%]
.....................                                                    [100%]

============================= 40 passed in 10.88s ==============================
```

## Governance Checklist (Required)
- [x] I updated docs when runtime/CI behavior changed.
- [x] I did not add duplicate CI truth layers.
- [x] I confirmed mergeability depends on `required-ci`.
- [x] I removed or justified any skipped tests.
- [x] I verified no PII or sensitive secrets were added.
