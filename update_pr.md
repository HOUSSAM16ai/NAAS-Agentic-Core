## Summary
Replaced broad, silenced exceptions (`except Exception: pass`) with safe, structured logging within the MCPToolSkill telemetry paths.

## Why
Silenced exceptions represent poor code health and hide underlying operational issues. This refactor makes failures visible in debug contexts for hot paths and emits a clear operations warning if the whole Prometheus subsystem fails to import. Fixes #2354.

## How to Test
Run the isolated unit test:
```bash
python -m pytest tests/services/test_mcp_tool_skill.py
```

## Validation Evidence
```text
============================= test session starts ==============================
platform linux -- Python 3.12.13, pytest-9.1.1, pluggy-1.6.0
rootdir: /app
configfile: pytest.ini
plugins: cov-7.1.0, asyncio-1.4.0, anyio-4.15.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 1 item

tests/services/test_mcp_tool_skill.py .                                  [100%]

============================== 1 passed in 0.78s ===============================
```

## Risk & Rollback
Low risk. Telemetry exceptions are still caught, meaning standard operations aren't impacted. If logging introduces unforeseen latency, rollback is simply reverting to the previous `pass` behavior.

HUMAN:
I have successfully verified this change locally. The smoke test proves the correct warning is emitted when Prometheus imports fail, without leaking modified module state into other tests. I manually ran the test suite, and everything passes as expected.
AGENT:
Completed template.
