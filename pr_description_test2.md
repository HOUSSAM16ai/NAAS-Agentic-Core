HUMAN:
تم التعديل كما طُلب، القالب الآن يتفادى أخطاء التهيئة ولا يُنشئ استدعاءات مجهولة الوسائط بشكل عشوائي، وهو ما كنت أطلبه.

AGENT:
```bash
python3 scripts/generate_all_tests.py
# All files generated cleanly without broken boilerplate
```

---

## Why
The original test generation template generated blindly `obj.method()` for all methods, including those with required arguments or those that are async. This caused broken, unsafe boilerplate tests that had to be manually deleted or overhauled.

## Summary
- Upgraded `analyze_module` in `scripts/generate_all_tests.py` to extract argument and method type metadata.
- Updated `generate_comprehensive_test` to skip instantiation if `__init__` requires arguments.
- Generated `TODO` blocks for methods requiring arguments or async methods, and valid calls for those that don't.
- Added 4 passing unit tests covering all these paths to `tests/scripts/test_generate_all_tests.py`.

## Issue Number
Fixes #286218

## How to Test
```bash
export PYTHONPATH=/home/jules/.pyenv/versions/3.12.13/lib/python3.12/site-packages:$PYTHONPATH DATABASE_URL="sqlite:///./test.db" JWT_SECRET_KEY="test"
pytest tests/scripts/test_generate_all_tests.py
```

## Change Type
- [ ] bug fix
- [x] feature
- [ ] refactor
- [ ] governance / documentation
- [ ] security hardening

## Affected Areas
- [ ] app core
- [ ] microservices
- [ ] contracts / guardrails
- [ ] CI/CD
- [ ] docs / governance

## Risk & Rollback
- **Risk level:** low
- **Rollback plan:** Revert the changes to `scripts/generate_all_tests.py`.

## Validation Evidence
```bash
export PYTHONPATH=/home/jules/.pyenv/versions/3.12.13/lib/python3.12/site-packages:$PYTHONPATH DATABASE_URL="sqlite:///./test.db" JWT_SECRET_KEY="test"
pytest tests/scripts/test_generate_all_tests.py
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.1, pluggy-1.6.0
rootdir: /app
configfile: pytest.ini
plugins: asyncio-1.4.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 4 items

tests/scripts/test_generate_all_tests.py ....                            [100%]

============================== 4 passed in 0.05s ===============================
```

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
Start by looking at the AST traversal logic added to `analyze_module` in `scripts/generate_all_tests.py`. Then see how `generate_comprehensive_test` consumes `safe_to_instantiate` and argument requirements. Tests confirm these logic branches.
