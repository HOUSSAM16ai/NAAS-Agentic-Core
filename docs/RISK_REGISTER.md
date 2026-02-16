# Risk Register

**Purpose:** To identify, assess, and mitigate risks proactively.
**Review Cycle:** Monthly.

## 1. Risk Matrix
| Risk ID | Risk Description | Likelihood | Impact | Mitigation Strategy | Owner |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **R01** | **Recruitment Failure** (Cannot find 15 core users) | Low | High | Partner with university clubs; Offer transport stipends. | PI |
| **R02** | **API Cost Overrun** (Agents use too many tokens) | Med | Med | Strict rate-limiting; Caching responses; Contingency budget. | Lead Eng |
| **R03** | **Data Privacy Incident** (PII leak in logs) | Low | Critical | Privacy-by-design (redaction before storage); No raw log publishing. | Lead Eng |
| **R04** | **Model Drift** (Base model changes behavior) | Med | Med | Continuous evaluation; Versioned prompts; Model pinning. | Lead Eng |
| **R05** | **Cultural Misalignment** (AI bias in Darija) | High | Med | Red-teaming specifically for cultural nuances; Localized prompts. | PI |
| **R06** | **Transfer Delays** (Bank/FX issues) | Med | Med | Buffer in Admin budget; Early documentation submission. | Admin |
| **R07** | **Prompt Misuse** (Students try to generate harm) | High | High | Strict Safeguarding Protocol; Real-time blocking; Mentor intervention. | Mentor |

## 2. Go/No-Go Gates
* **Gate 1 (Month 2):** Safeguarding protocols approved? If NO → Stop Pilot.
* **Gate 2 (Month 5):** Prototype passes <5% Jailbreak Rate? If NO → Extend R&D, Delay Workshops.
* **Escalation:** Any "Critical" risk triggers immediate PI & Ethics Lead review.

## 3. Residual Risk
After mitigation, the primary residual risk remains **Model Drift**, which we accept as an inherent property of using LLMs, managed via continuous monitoring.
