"""Vendored dependency-free foundation engines for foundations-service (D-183).

An independent copy of ``app/core/foundations`` (pure stdlib, no ``app`` imports)
so the microservice honours the isolation rule (CLAUDE.md §0.5 rule 3: a Skill
never imports another service or the monolith). The monolith keeps the canonical
copy; this vendored set is what the API-first service serves.
"""
