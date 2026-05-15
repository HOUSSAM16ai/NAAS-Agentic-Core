# Memory Update Templates

After any LLM model fix, update these 4 files in this exact format.

---

## 1. CLAUDE.md — append at end

```markdown
**Model fix applied YYYY-MM-DD (ISS-NNN — [short description] / D-NNN):** [one paragraph summary].
**التغييرات:** [list key files]. **قاعدة لا تُخرق:** [the permanent rule].
**نتائج حية:** [benchmark results with ✅/❌].
```

---

## 2. .memory/issues.md — prepend before previous ISS

```markdown
## ISS-NNN — [Title] (YYYY-MM-DD)

- **Symptom**: [what the user/agent observed]
- **Root cause**: [technical root cause, numbered if multiple]
- **Fix (D-NNN)**:
  - [fix item 1]
  - [fix item 2]
- **Files changed**: [list]
- **Benchmark results (live YYYY-MM-DD)**:
  - `model-id`: TTFT=Xs ✅/❌
- **Status**: FIXED YYYY-MM-DD — branch `fix/iss-NNN-description`.
```

---

## 3. .memory/runtime_truth.md — prepend new D-NNN section

```markdown
## D-NNN Live Verification Results (YYYY-MM-DD) — [description]

| Service | Port | Status | Key Fields |
|---------|------|--------|-----------|
| main-app | 8000 | ✅ ACTIVE | `database: ok` |
| user-service | 8001 | ✅ ACTIVE | `status: ok` |
| planning-agent | 8002 | ✅/❌ | `database: postgresql+asyncpg://...` |
| research-agent | 8007 | ✅/❌ | `tavily_available: true/false` |
| reasoning-agent | 8008 | ✅/❌ | `llm_backend: openrouter/mock` |

**Active LLM Model**: `model-id` (TTFT=Xs)
**Fallback Chain**: `model1` → `model2` → `model3`
**BROKEN MODEL**: `model-id` — reason

### Key Fixes Applied (ISS-NNN / D-NNN)
- [fix 1]
- [fix 2]
```

---

## 4. .memory/decisions.md — append at end

```markdown
## D-NNN — [Decision Title] (YYYY-MM-DD)

**Problem**: [what was broken]
**Decision**: [what was chosen]
**Rationale**:
- [reason 1]
- [reason 2]
**Invariants (قواعد دائمة)**:
1. [rule 1]
2. [rule 2]
**Status**: IMPLEMENTED YYYY-MM-DD — branch `fix/iss-NNN-description`.
```
