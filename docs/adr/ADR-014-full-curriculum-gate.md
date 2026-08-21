# ADR-014: Full Curriculum Consideration Gate

## Status

Accepted as an additive governance layer on 2026-08-21.

## Context

The project must not reduce rigorous education to a short list of popular courses. The owner requires every course in the authoritative academic catalogs used by the project to remain visible and considered, including foundational, elective, advanced, research, systems, AI, security, education, social, economic, and interdisciplinary courses.

A literal rule that forces every agent to read every course in every university before every line would be untestable and would create noise rather than understanding. The enforceable interpretation is stronger: every course is catalogued, each course has a domain and application card, the task packet considers the full catalog, and the agent loads the subset whose domains are relevant to the change. The baseline foundations and safety evidence remain mandatory for every code change.

## Decision

We adopt the following additive contract:

1. `docs/research/UNIVERSITY_CURRICULUM_CATALOG.json` is the complete extracted snapshot for the official Harvard SEAS Computer Science course listing used by this layer.
2. `docs/research/CURRICULUM_APPLICATION_MATRIX.json` contains one application record for every course in that catalog; no course may remain invisible or silently discarded.
3. Every code-acceptance packet must state that the full catalog was loaded and considered, name the catalog count and course IDs, and record the policy for courses that are not directly applicable.
4. Every code change must use the baseline evidence for CS50 foundations, Harvard CS concentration domains, NIST SSDF, and OWASP agent security. Task-specific changes add the relevant mapped course domains and evidence.
5. A course is not claimed as implemented merely because it appears in the catalog. Implementation requires a local path, test or gate, owner, and evidence in the packet.
6. New universities, departments, courses, papers, or curricula are added; they never replace or delete an existing catalog entry.

## Consequences

The project obtains complete visibility without pretending that educational exposure is production proof. The acceptance gate becomes auditable, task-specific, and scalable. The cost is that a change packet must carry explicit curriculum consideration and must refuse unsupported claims.

## Enforcement

The code gate is `scripts/fitness/check_code_acceptance.py`, and the catalog builders are `scripts/research/extract_harvard_course_catalog.py` and `scripts/research/build_curriculum_application_matrix.py`. The current packet is `docs/changes/CURRENT_CODE_ACCEPTANCE_PACKET.json`.
