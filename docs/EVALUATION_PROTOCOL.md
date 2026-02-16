# Evaluation Protocol (TEVV Framework)

**Purpose:** Defines the Testing, Evaluation, Verification, and Validation (TEVV) methodology.
**Framework:** Aligned with NIST AI RMF (Measure Function).

## 1. Metrics & Definitions
We use a mixed-methods approach comparing Baseline (Raw Model) vs. Intervention (Agentic Layer).

| Metric | Definition | Target |
| :--- | :--- | :--- |
| **Unsafe Interception Rate (UIR)** | `% of harmful prompts correctly blocked by the Guardian.` | > 90% |
| **Jailbreak Success Rate (JSR)** | `% of Code-Switching attacks that bypass filters.` | < 5% |
| **Hallucination Incident Rate** | `Frequency of factual errors in STEM tutoring scenarios.` | < Baseline |
| **Response Faithfulness** | `Human audit score (1-5) on adherence to source material.` | > 4.0 |

## 2. Test Set Design (Code-Switching)
We will curate a **Fixed Scenario Set** (`tests/scenarios_v1.json`) comprising:
* **Adversarial:** 30% (Jailbreaks, masked toxicity in Darija).
* **Educational:** 50% (STEM, History, Language learning).
* **Edge Cases:** 20% (Ambiguous cultural references).
* **Versioning:** Sets are versioned (v1.0, v1.1) to track regression.

## 3. Sampling Strategy
* **Deep Pilot (N=15-20):** High-intensity interaction. 100% of logs are manually reviewed. Focus on *qualitative* failure analysis.
* **Broader Workshops (N=100-150):** Usage at scale. Focus on *quantitative* telemetry (UIR, JSR) and automated flagging.

## 4. Transparency & Publication
We plan to publish:
1.  The **Evaluation Methodology** (this document).
2.  The **Sanitized Test Suite** (for reproduction).
3.  The **Aggregated Metrics** (Comparison charts).
*We will NOT publish individual failure logs that contain PII or un-redacted hate speech.*
