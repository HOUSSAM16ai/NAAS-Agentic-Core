# Architecture Risks
> Last updated: 2026-05-05

1. Documentation drift between `.memory`, `CLAUDE.md`, and executable code.
2. Hidden coupling via shared implicit models across services.
3. Router-level business logic creep in `app/api/routers/*`.
4. Inconsistent resilience policies for remote calls across services.
