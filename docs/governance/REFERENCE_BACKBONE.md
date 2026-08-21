# Reference Backbone

## Purpose

This document is the human-readable companion to [`REFERENCE_BACKBONE.json`](REFERENCE_BACKBONE.json). The manifest is the machine-checked source of truth; this page explains how the references shape the project without turning external repositories into unreviewed runtime dependencies.

> **Backbone law:** these references are mandatory engineering context, not optional decoration. They may guide design, learning, review, evaluation, and research. They may not bypass local contracts, tests, security controls, runtime evidence, or human accountability.

The integration is intentionally **additive**. Existing source code, services, contracts, constitutions, and operational rules remain in place. The new layer adds a pinned reference set, explicit adoption boundaries, an append-only ADR, research provenance, and a hard CI gate.

## The twelve-month engineering compass

The project should move through the references as a reinforcing system rather than as disconnected reading. Orientation defines the path; algorithmic and systems foundations make trade-offs intelligible; architecture references turn local code into a scalable system; clean-code references keep change legible; integration and agent references expand capability only under security controls.

| Layer | Pinned references | How the project uses the layer |
|---|---|---|
| **Orientation** | [developer-roadmap](https://github.com/kamranahmedse/developer-roadmap/tree/9a38345ec29629224e40131ecfaba7a82abdf979), [freeCodeCamp](https://github.com/freeCodeCamp/freeCodeCamp/tree/4289125977fa5bc4c90d7e2860bc04062a30abee), [free-programming-books](https://github.com/EbookFoundation/free-programming-books/tree/5b277d20f623ce5b2889b16fc9dd5e266536f521), [awesome](https://github.com/sindresorhus/awesome/tree/d35bcd9c5c83f2652b0d2b5f91a320009c8f29a3) | Contributor onboarding, prerequisite mapping, research discovery, and durable self-learning paths. |
| **Foundations** | [coding-interview-university](https://github.com/jwasham/coding-interview-university/tree/717298bf219a30d7fb0671285c5f057b1bb74b27), [TheAlgorithms/Python](https://github.com/TheAlgorithms/Python/tree/f5988cc09713315817df6a7e327e258013a94440), [build-your-own-x](https://github.com/codecrafters-io/build-your-own-x/tree/aa17439b62f384511a5561ce308e9598b94d8989), [LLMs-from-scratch](https://github.com/rasbt/LLMs-from-scratch/tree/ec0bac5e1d854306a8ea6c308da49aae22479bd1) | Algorithmic reasoning, implementation literacy, systems understanding, and model literacy. |
| **Architecture** | [system-design-primer](https://github.com/donnemartin/system-design-primer/tree/ae9bbd7b02d90b9866215de185217d33f39ab733), [system-design-101](https://github.com/ByteByteGoHq/system-design-101/tree/b28380a4710c5ec9638ec037d4168e288f334cba) | Architecture reviews, failure analysis, protocol explanation, distributed-systems trade-offs, and capacity reasoning. |
| **Craft** | [clean-code-javascript](https://github.com/ryanmcdermott/clean-code-javascript/tree/5311f64b03fc0c2450ab17a45ee9818669c8b9b5), [clean-code-book](https://github.com/Gatjuat-Wicteat-Riek/clean-code-book/tree/4e5ffdaeb166cd2248ddd16d2c5e8d27812cd10c) | Readability, cohesion, meaningful names, small responsibilities, and maintainable change. These remain guidance, not a license to violate local contracts. |
| **Integrations and agents** | [public-apis](https://github.com/public-apis/public-apis/tree/c045a2eb505f0f8b7992bb4af53cc020f25003fd), [browser-use](https://github.com/browser-use/browser-use/tree/85ddbfedf609166b2d2c76c3d80506649fee82a9), [awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills/tree/be2a406907dbc61b73e6827ded415c96139d13a2) | Discover possible integrations and agent/skill patterns. No external API, browser action, skill, or tool becomes active merely because it appears in a reference. |

## Non-bypassable rules

A reference is not an implementation. Every capability derived from the backbone must still have a local owner, a typed contract, tests, observability, a threat model where relevant, and runtime evidence before it is labelled active. A source that supplies examples does not create a project standard by itself.

The repository must not vendor or bulk-copy the reference repositories. It must not add them as Git submodules or package dependencies unless a new ADR documents the exact material, license, provenance, security review, maintenance owner, and rollback plan. The default is to implement principles locally and link to the pinned source.

Agent-related references receive the strictest boundary. The project preserves explicit identity, authorization, least privilege, human approval for sensitive operations, auditability, budget limits, isolation, and failure containment. This follows NIST’s direction on agent standards and identity [1] and OWASP’s controls for scoped tools and sensitive-action authorization [2].

## Review protocol

Any architectural change materially influenced by a backbone reference must name the relevant reference ID in its ADR or design document. The review must state what was adopted, what was rejected, and what evidence proves the local implementation. If the reference revision changes, update the pinned SHA and write a new ADR or a superseding record; do not rewrite the accepted history.

## Evidence and research boundary

The full research record is [`../research/authoritative-foundations.md`](../research/authoritative-foundations.md). NIST AI RMF provides the lifecycle governance frame [3]. NIST SSDF provides secure-development outcomes across preparation, protection, production, and vulnerability response [4]. OpenSSF Scorecard and SLSA inform supply-chain checks and provenance [5] [6]. DORA informs balanced delivery and operational measurement rather than vanity metrics [7].

## References

[1]: https://www.nist.gov/artificial-intelligence/ai-agent-standards-initiative "NIST AI Agent Standards Initiative"
[2]: https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html "OWASP AI Agent Security Cheat Sheet"
[3]: https://www.nist.gov/itl/ai-risk-management-framework "NIST AI Risk Management Framework"
[4]: https://csrc.nist.gov/projects/ssdf "NIST Secure Software Development Framework"
[5]: https://scorecard.dev/ "OpenSSF Scorecard"
[6]: https://slsa.dev/spec/v1.2/ "SLSA Specification v1.2"
[7]: https://dora.dev/ "DORA"
