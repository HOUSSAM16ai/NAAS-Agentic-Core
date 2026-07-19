"""R0.2 (D-172) — Dependency Contract gate.

The Codex "Existential Risks" audit named R0.2: `orchestrator-service` silently
loses its Postgres checkpointer because `from langgraph.checkpoint.postgres.aio
import AsyncPostgresSaver` fails, and the guard degrades to `MemorySaver` — a
hidden fallback that makes the stack look healthy while being downgraded.

Root cause found: the orchestrator container's own requirements.txt installed
bare `langgraph` and omitted `langgraph-checkpoint-postgres` + `psycopg`
entirely, so the import could never succeed in the built image.

These tests assert the checkpointer stack is installed and importable, so the
REAL `AsyncPostgresSaver` is used. They run in CI (requirements-test.txt pins
the package) and inside the orchestrator image build. The full runtime proof
(`GET /checkpointer/status -> backend=postgres`) lives in the live E2E,
scripts/verify_full_stack_docker.py.
"""

from __future__ import annotations

import importlib


def test_async_postgres_saver_is_importable() -> None:
    """The langgraph Postgres checkpointer must import (not ImportError→None)."""
    module = importlib.import_module("langgraph.checkpoint.postgres.aio")
    saver = getattr(module, "AsyncPostgresSaver", None)
    assert saver is not None, (
        "AsyncPostgresSaver missing — langgraph-checkpoint-postgres is not "
        "installed/compatible; the checkpointer would silently fall back to "
        "MemorySaver (R0.2)."
    )


def test_langgraph_checkpoint_base_present() -> None:
    """The base checkpointer contract langgraph validates isinstance against."""
    base = importlib.import_module("langgraph.checkpoint.base")
    assert hasattr(base, "BaseCheckpointSaver")
