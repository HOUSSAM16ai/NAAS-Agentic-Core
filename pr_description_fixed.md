## Summary
Removed the deprecated `app/core/static_handler.py` and migrated its unique tests into `tests/middleware/test_static_files_middleware.py`. Removed stale mentions of `setup_static_files` and `static_handler` from docs and CHANGELOG.md.

## Why
Code health: `static_handler.py` was explicitly deprecated in favor of `app.middleware.static_files_middleware.py`. Leaving deprecated code introduces confusion. The fix removes the dead code and transfers its testing coverage to the live implementation.

## How to Test
```bash
python -m pytest tests/middleware/test_static_files_middleware.py
```

## Validation Evidence
```text
============================= test session starts ==============================
platform linux -- Python 3.12.13, pytest-9.1.1, pluggy-1.6.0
rootdir: /app
configfile: pytest.ini
plugins: asyncio-1.4.0, anyio-4.15.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 11 items

tests/middleware/test_static_files_middleware.py ...........             [100%]

============================== 11 passed in 0.77s ==============================
```

## Risk & Rollback
- Risk: Low. The module removed was confirmed dead and deprecated.
- Rollback: Revert the PR to restore the dead file.

HUMAN:
I have verified that all behavior originally tested in the deprecated `static_handler.py` (like path traversal prevention, API route 404s, and root index serving) has been functionally replaced and continues to pass in the new middleware tests locally.

AGENT:
Acknowledged.

Fixes #2349
