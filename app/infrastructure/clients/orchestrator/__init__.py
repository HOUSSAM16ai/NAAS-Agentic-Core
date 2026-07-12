"""Cohesive mixins decomposed out of the `orchestrator_client.py` God-file (D-164).

Each module here owns one responsibility (SRP) and is mixed into `OrchestratorClient`
via inheritance — a verbatim, behaviour-preserving continuation of the D-163
`ProbabilityTutorBrain` extraction. The `tutor_sources` manifest is the single source
of truth for which files compose the monolith tutor "source", so the ~25 source-inspection
CI gates + tests read one canonical concatenation and a future extraction is a one-line
append here, not a ~25-file change.

Stdlib-only, no heavy imports — degraded-sandbox gates (no pydantic) can import the manifest.
"""
