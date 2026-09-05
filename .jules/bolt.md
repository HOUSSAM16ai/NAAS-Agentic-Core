## 2024-05-23 - [UUID Generation Strategy]
**Learning:** Replaced `uuid4()` with `uuid7()` from `uuid-utils` for performance, but it's a bad idea.
**Action:** Do not optimize UUID generation this way because: 1) It requires a new dependency (needs permission). 2) Changing the ID generation strategy across ~30 call sites is an architectural change, not a <50-line micro-optimization. 3) `uuid4()` generation is already in microseconds and not a bottleneck at call sites; `uuid7()`'s real value is B-tree index locality for primary keys (a schema decision, not a hot-path performance fix).
