HUMAN:

I reviewed the file `app/services/data_mesh/domain/ports.py` visually to verify that the example interface block was successfully removed, and the instructional comment remained intact. I also ran a grep search across the codebase and verified no other identical `# Example:` commented protocol blocks existed in other services.

AGENT:

No unit tests cover this file as it's just an interface definitions file. However, I ran basic validation commands:

```bash
cat app/services/data_mesh/domain/ports.py
```
Output:
```python
"""
Domain Ports (Interfaces) for DataMesh
"""

# Add your interfaces here
```

---

## Why
This removes unnecessary boilerplate/example code, reducing visual clutter and improving the readability and maintainability of the file.

## Summary
- Removed the commented-out `IYourRepository` example block from `app/services/data_mesh/domain/ports.py`.

## Issue Number
Fixes #2312

## How to Test
```bash
cat app/services/data_mesh/domain/ports.py
```
Expected output: the file should only contain the module docstring and the `# Add your interfaces here` comment.

## Change Type
- [ ] bug fix
- [ ] feature
- [ ] refactor
- [x] governance / documentation
- [ ] security hardening

## Affected Areas
- [ ] app core
- [ ] microservices
- [ ] contracts / guardrails
- [ ] CI/CD
- [ ] docs / governance

## Risk & Rollback
- **Risk level:** low
- **Rollback plan:** Revert this specific commit.

## Validation Evidence
```bash
cat app/services/data_mesh/domain/ports.py
```

## Video/Screenshots
N/A

## Governance Checklist (Required)
- [x] I updated docs when runtime/CI behavior changed.
- [x] I did not add duplicate CI truth layers.
- [x] I confirmed mergeability depends on `required-ci`.
- [x] I removed or justified any skipped tests.
- [x] I verified no PII or sensitive secrets were added.

## Safeguarding Impact
N/A

## Reviewer Guide
Look at `app/services/data_mesh/domain/ports.py`.
