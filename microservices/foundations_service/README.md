# foundations-service (:8010) — D-183

The API-first **"first roots"** compute Skill: a deterministic HTTP surface over
the verified pre-programming substrate (logic, mathematics, theory of
computation). No LLM, no DB, no external keys — every result comes from a
dependency-free engine (CLAUDE.md §0: *symbolic truth before language*).

## Endpoints
- `POST /compute` — `{domain, operation, args}` → deterministic result (fail-open)
- `GET /health` — status + supported domains
- `GET /metrics` — Prometheus (independent CollectorRegistry)

## Domains
`linear_algebra` · `calculus` · `statistics` · `optimization` · `graph_theory`
· `formal_languages` · `computability` · `complexity`

Functions (calculus/optimization) are passed as polynomial coefficient lists
(`[c0, c1, c2] → c0 + c1·x + c2·x²`) so the surface stays JSON-safe — no `eval`.

## Example
```json
POST /compute
{"domain": "linear_algebra", "operation": "solve",
 "args": {"matrix": [[2,1],[1,3]], "b": [3,4]}}
→ {"domain":"linear_algebra","operation":"solve","ok":true,"result":[1.0,1.0], ...}
```

Run: `uvicorn microservices.foundations_service.main:app --port 8010`
