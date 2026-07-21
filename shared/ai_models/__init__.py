"""shared.ai_models — cross-plane AI model contracts (single source of truth).

This package is import-safe from BOTH planes (the monolith `app/` and the
microservices under `microservices/`) and carries **zero** third-party deps, so it
never pulls FastAPI / pydantic / settings into a gate or a microservice that does
not need them.

Today it exposes the canonical OpenRouter model chain (`model_chain`). The two
brains (`app/core/ai_config.py` + `microservices/orchestrator_service/src/core/
ai_config.py`) keep their own gate-pinned `PRIMARY`/fallback declarations for
defense-in-depth (D-067/ISS-079), and a deterministic parity gate
(`scripts/fitness/check_model_chain_parity.py`) proves both brains agree with the
canonical chain declared here — turning the old D-013 "edit both copies by hand"
prose rule into a machine-enforced single source of truth.
"""

from __future__ import annotations

from shared.ai_models.model_chain import (
    FALLBACK_CHAIN,
    MODEL_CHAIN,
    PRIMARY_MODEL,
    resolve_primary_model,
)

__all__ = [
    "FALLBACK_CHAIN",
    "MODEL_CHAIN",
    "PRIMARY_MODEL",
    "resolve_primary_model",
]
