## Summary
Replaced broad `except Exception: pass` blocks around telemetry hooks in `local_fallback.py` with `logger.warning`. This ensures telemetry failures are visible in logs without breaking the fallback path.

## Why
A failing telemetry hook (due to bad imports or broken observers) is a real defect that must be diagnosed. Logging these failures with `logger.warning` and `exc_info=True` improves the observability of the fallback path while ensuring the actual user request isn't broken.

## How to Test
Monkeypatched `mark_fallback_used` to raise an exception within a dedicated test in `test_orchestrator_client_resilience.py`.
Command to run test:
```bash
pytest tests/microservices/test_orchestrator_client_resilience.py::test_telemetry_failure_does_not_break_fallback_path -v
```

## Validation Evidence
```text
============================= test session starts ==============================
platform linux -- Python 3.12.13, pytest-7.4.4, pluggy-1.6.0
rootdir: /app
configfile: pytest.ini
plugins: anyio-4.12.0, Faker-40.36.0, langsmith-0.12.1, asyncio-0.21.1, hypothesis-6.165.10, env-1.1.3, cov-4.1.0, factoryboy-2.8.1, timeout-2.4.0
asyncio: mode=Mode.AUTO
collecting ... collected 1 item

tests/microservices/test_orchestrator_client_resilience.py::test_telemetry_failure_does_not_break_fallback_path PASSED

============================== 1 passed in 3.92s ===============================
```

## Risk & Rollback
- **Risk:** Negligible. It only adds safe logging in a `except` block.
- **Rollback:** Revert this PR.

HUMAN:
I have verified this behavior locally. The tests successfully capture the simulated telemetry failure and log the warning without disrupting the fallback execution flow.

AGENT:
Jules

Fixes #1234
