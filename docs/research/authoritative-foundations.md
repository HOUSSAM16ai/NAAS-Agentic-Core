# Authoritative foundations — research notes

## NIST AI Risk Management Framework

Source: https://www.nist.gov/itl/ai-risk-management-framework

Key findings captured 2026-08-21:

- NIST AI RMF 1.0 is voluntary guidance intended to incorporate trustworthiness into the design, development, use, and evaluation of AI products, services, and systems.
- It treats risk management as a lifecycle activity, with continuous assessment, measurement, management, and mapping of AI risks and trustworthiness factors.
- The page emphasizes governance, transparency, accountability, stakeholder engagement, and oversight throughout the AI-system lifecycle.
- NIST provides a companion Playbook, Roadmap, Crosswalks, and a Generative AI Profile; the framework is being revised.

Implication for NAAS-Agentic-Core: treat AI governance, risk records, evaluation evidence, human accountability, and lifecycle traceability as first-class repository artifacts and merge gates rather than optional documentation.

## NIST Secure Software Development Framework (SSDF) 1.1

Source: https://csrc.nist.gov/projects/ssdf

Key findings captured 2026-08-21:

- SSDF is a set of fundamental, outcome-based secure development practices that should be integrated into the project’s chosen SDLC.
- The practices are grouped into Prepare the Organization (PO), Protect the Software (PS), Produce Well-Secured Software (PW), and Respond to Vulnerabilities (RV).
- SSDF defines practices, tasks, implementation examples, and references, and is intended to align security activity with mission requirements, risk tolerance, and resources.
- The current project page identifies SSDF Version 1.1 as NIST SP 800-218 and links to a Generative AI and Dual-Use Foundation Models Community Profile.

Implication for NAAS-Agentic-Core: encode organization readiness, source and dependency protection, secure build/release verification, and vulnerability response into repository policy, CI checks, release evidence, and ownership rules.

## Preliminary repository context

Linked repository: https://github.com/bakabala27-svg/NAAS-Agentic-Core

Initial clone was clean on branch `main` tracking `origin/main`. The repository already contains extensive governance and operational material, including `.github`, `.cicd`, `.memory`, `AGENTS.md`, `GOVERNANCE.md`, `SECURITY.md`, `DATA_POLICY.md`, `DATA_PROTECTION.md`, `Makefile`, Docker/devcontainer assets, route registries, runtime truth artifacts, and a sizable Python application. No files were deleted or modified during inspection.

## Research discipline

The attached note contains repository claims and popularity counts that must not be treated as verified facts without checking primary repository pages and current metadata. It also contains future-dated or potentially unverified claims; these must be excluded or clearly marked unless independently corroborated.

## DORA research program

Source: https://dora.dev/

Key findings captured 2026-08-21:

- DORA describes itself as a long-running research program studying capabilities that drive software delivery and operations performance.
- The current site presents DORA Core as its established body of findings and offers a generative-AI guide and an AI-assisted software-development ROI report.
- The practical implication is to measure delivery and operational improvement as a capability system, not to treat isolated activity counts as proof of quality.

Implication for NAAS-Agentic-Core: define a small, balanced engineering scorecard covering delivery flow, reliability, security, quality, user outcomes, and learning; avoid using any single metric as a target that can be gamed.

## OpenSSF Scorecard

Source: https://scorecard.dev/

Key findings captured 2026-08-21:

- Scorecard assesses open-source supply-chain risk through automated checks covering source code, build, dependencies, testing, and maintenance.
- It reports per-check scores and risk levels, with an aggregate posture score and remediation prompts.
- Listed checks include vulnerabilities, dependency update tooling, maintenance, security policy, CI tests, fuzzing, SAST, binary artifacts, branch protection, dangerous workflows, code review, pinned dependencies, token permissions, packaging, and signed releases.

Implication for NAAS-Agentic-Core: add supply-chain posture checks to CI and track exceptions explicitly. High-risk controls such as branch protection, code review, dangerous-workflow prevention, pinned dependencies, least-privilege workflow tokens, and signed releases should be treated as release prerequisites where feasible.

## NIST AI Agent Standards Initiative

Source: https://www.nist.gov/artificial-intelligence/ai-agent-standards-initiative

Key findings captured 2026-08-21:

- NIST frames autonomous agents as requiring a trusted, interoperable, and secure ecosystem.
- The initiative’s strategic pillars are industry-led standards, community-led protocols, and research into agent authentication, identity infrastructure, and security evaluations.
- The page was updated August 14, 2026 and links to work on software and AI-agent identity and authorization.

Implication for NAAS-Agentic-Core: model agent identity, authorization, protocol boundaries, and security evaluation as explicit architecture concerns. Agent actions must be attributable, scoped, reviewable, and testable.

## OWASP AI Agent Security Cheat Sheet

Source: https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html

Key findings captured 2026-08-21:

- Key risks include prompt injection, tool abuse and privilege escalation, data exfiltration, memory poisoning, goal hijacking, excessive autonomy, high-impact action abuse, decision/approval manipulation, cascading failures, malicious configuration, and denial-of-wallet.
- Recommended controls include minimum required tools, per-tool permission scoping, separate tool sets by trust level, and explicit authorization for sensitive operations.
- The page gives a concrete safe pattern: allowlisted operations and paths, blocked secret patterns, and confirmation middleware for sensitive tools such as code execution, database writes, and deletion.

Implication for NAAS-Agentic-Core: preserve and extend the existing executor/model separation with explicit capability manifests, allowlists, approval points, budgets, audit events, isolation, and adversarial evaluation. “Agent autonomy” must never mean unbounded authority.

## SLSA specification v1.2

Source: https://slsa.dev/spec/v1.2/

Key findings captured 2026-08-21:

- SLSA v1.2 is an approved, industry-consensus specification for incrementally improving software supply-chain security.
- It defines levels, Build and Source tracks, provenance and attestation formats, and verification guidance.
- Its build track is intended to provide confidence that artifacts were not tampered with and can be traced back to their source.

Implication for NAAS-Agentic-Core: phase supply-chain assurance. Start with source and dependency integrity, then add verifiable build provenance and release attestations as artifacts are published. Do not claim a SLSA level until its requirements and evidence are actually met.

## Microsoft Azure Well-Architected ADR guidance

Source: https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-decision-record

Key findings captured 2026-08-21:

- ADRs should capture decisions affecting system structure, key quality attributes, or difficult-to-reverse choices, including rejected alternatives, context, rationale, trade-offs, consequences, confidence, and status.
- ADRs should start at the beginning of a workload, remain append-only after acceptance, and be superseded by new records rather than edited in place.
- A shared documentation repository should serve as the single source of truth for decisions, audits, and incident response.

Implication for NAAS-Agentic-Core: create a dedicated backbone ADR and a reference adoption registry. Changes to the immutable foundation, imported references, agent authority, security gates, or runtime topology require a new ADR and cannot be silently edited around.

## Verified university-course evidence

### MIT 6.5840 / 6.824 Distributed Systems

Source: https://pdos.csail.mit.edu/6.824/

Verified 2026-08-21 from the official Spring 2026 course page. The course presents abstractions and implementation techniques for engineering distributed systems, with major topics including fault tolerance, replication, and consistency. It combines lectures, readings, programming labs, projects, and exams.

Local acceptance implication: changes to service boundaries, persistence, replication, events, concurrency, or failure handling must include an explicit distributed-systems rationale and failure-oriented tests where applicable.

### Stanford CS224N — Natural Language Processing with Deep Learning

Source: https://web.stanford.edu/class/cs224n/

Verified 2026-08-21 from the official Winter 2026 course page. The course covers deep-learning fundamentals for NLP and current research on large language models, using lectures, assignments, and a final project to teach students to design, implement, and understand neural-network models.

Local acceptance implication: language-model or Arabic/French NLP changes must identify the task, data, evaluation method, model limitations, and evidence against overclaiming generalization.

## Verified Harvard CS curriculum evidence

### Harvard Computer Science concentration requirements

Source: https://csadvising.seas.harvard.edu/concentration/requirements/

Verified 2026-08-21 from Harvard CS Undergraduate Advising. The basic concentration requires a core spanning programming, formal reasoning, systems, computation and the world, and advanced computer science, plus mathematics including linear algebra and probability. The page specifically enumerates programming, discrete mathematics, computational limitations, algorithms, systems, computation and the world, artificial intelligence, and advanced CS as requirement domains.

Local acceptance implication: the project does not claim that every Harvard course is loaded before every line. Instead, it maintains a Harvard CS curriculum catalog with a mandatory foundation for all code changes and a task-specific prerequisite map. A change touching algorithms, systems, distributed state, models, data, security, or product interfaces must cite the relevant domain and its evidence.

### Harvard CS50x

Source: https://cs50.harvard.edu/x/

Verified 2026-08-21 from the official course page. CS50x covers computational thinking, abstraction, algorithms, data structures, correctness, design, style, C, memory, Python, SQL, HTML, CSS, JavaScript, and a final project.

Local acceptance implication: every code packet must include correctness, design, and style evidence; changes involving memory, data, APIs, databases, or user interfaces must also identify the relevant engineering checks.
