"""Single source of truth for the orchestrator API's source-file composition (D-168).

Mirror of the monolith's ``tutor_sources.py`` (D-164) for the microservice side:
``routes.py`` is being decomposed into cohesive sibling modules (verbatim moves),
and the source-inspection CI gates / tests that used to ``read_text(routes.py)``
now read the concatenation through this one manifest — so extracting a new module
is a **one-line append** to ``API_SOURCE_FILES`` instead of a multi-file gate change.

Stdlib-only (no fastapi / no pydantic) so degraded-sandbox gates can import it —
the same design constraint as ``tutor_sources.py`` and ``db_bridge.py``.
"""

from __future__ import annotations

from pathlib import Path

# api/ -> src -> orchestrator_service -> microservices -> <repo root>
_ROOT = Path(__file__).resolve().parents[4]

# Canonical, fixed order: routes.py first (router + all @router handlers stay there —
# the AST backbone gate parses it alone), then the extracted helper modules (D-168 —
# append each new extraction below, in dependency-layer order).
API_SOURCE_FILES: tuple[str, ...] = (
    "microservices/orchestrator_service/src/api/routes.py",
    "microservices/orchestrator_service/src/api/chat_types.py",  # D-168 Slice A1
    "microservices/orchestrator_service/src/api/chat_context.py",  # D-168 Slice A1
    "microservices/orchestrator_service/src/api/identity_access.py",  # D-168 Slice A2
    "microservices/orchestrator_service/src/api/stream_serialization.py",  # D-168 Slice A2
    "microservices/orchestrator_service/src/api/conversation_store.py",  # D-168 Slice A3
)


def read_api_source() -> str:
    """Return the orchestrator API "source" = all `API_SOURCE_FILES` concatenated.

    Fixed order, ``\\n``-joined — byte-identical to the pre-D-168 ``routes.py`` read
    while the manifest holds a single file, so every existing substring / count
    assertion keeps holding as modules are extracted verbatim.
    """
    return "\n".join((_ROOT / rel).read_text(encoding="utf-8") for rel in API_SOURCE_FILES)
