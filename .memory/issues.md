# Open Issues / Risks
> Last updated: 2026-05-05

## High Priority
1. **Memory docs drift risk**
   - Risk: `.memory` files become stale after architecture changes.
   - Mitigation: update `.memory` in same PR when topology docs change.

2. **Hybrid boundary confusion**
   - Risk: contributors assume pure monolith or pure microservices and introduce coupling.
   - Mitigation: enforce client-boundary guidance in context/architecture docs.

## Medium Priority
3. **Evidence traceability gaps**
   - Risk: narrative claims without file anchors.
   - Mitigation: include direct file references in memory notes and PR descriptions.

4. **Endpoint documentation divergence (memory agent)**
   - Risk: service README and runtime routes drift apart.
   - Mitigation: refresh endpoint lists when route files change.
