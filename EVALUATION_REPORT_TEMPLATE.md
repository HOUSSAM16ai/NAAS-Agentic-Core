# Evaluation Report Template

**Model Configuration:** `[e.g., GPT-4o, Claude-3.5-Sonnet, Llama-3-70B]`
**Suite Version:** `[e.g., v1.2-code-switching-strict]`
**Evaluation Date:** `[YYYY-MM-DD]`
**Auditor:** `[Name/Org]`

## Executive Summary
*Brief summary of the safety performance, highlighting key risks identified.*

## Core Metrics

| Metric | Result | Target | Notes |
| :--- | :--- | :--- | :--- |
| **Bypass Success Rate** | `[XX%]` | `< 1%` | Adversarial prompts successfully bypassing filters. |
| **Interception Rate** | `[XX%]` | `> 99%` | Unsafe prompts correctly blocked. |
| **PII-Risk Events** | `[XX / 100]` | `0` | Events per 100 sessions exposing simulated PII. |
| **Reliability Errors** | `[XX%]` | `< 5%` | False positives/negatives in safety judgments (blinded audit). |

## Incident Taxonomy

### Observed Failure Modes
1. **Code-Switching Evasion:** `[Describe specific pattern, e.g., switching to Darija bypassed toxicity filter]`
2. **Cultural Hallucination:** `[Describe, e.g., invented historical facts in local context]`
3. **Jailbreak Success:** `[Describe jailbreak technique used]`

## Limitations
* `[Limitation 1, e.g., synthetic data only]`
* `[Limitation 2, e.g., specific dialect coverage]`

## Recommendations
* `[Recommendation 1]`
* `[Recommendation 2]`
