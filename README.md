# NAAS-Agentic-Core
### Youth-facing GenAI safety evaluation in Arabic/French/Darija code-switching contexts.

![License](https://img.shields.io/badge/License-MIT-blue.svg) ![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![CI](https://img.shields.io/badge/CI-Passing-brightgreen) ![Docs](https://img.shields.io/badge/Docs-Latest-orange) ![Status](https://img.shields.io/badge/Status-Active_R%26D-yellow) ![Governance](https://img.shields.io/badge/Governance-Safeguarding_%2B_Data_Policy-red) ![Citation](https://img.shields.io/badge/Citation-CFF-lightgrey)

> **Governance & Safeguarding Context**
> This repository operates under strict ethical guidelines for youth-facing AI research. All contributors must review [SAFEGUARDING.md](./SAFEGUARDING.md) and [DATA_POLICY.md](./DATA_POLICY.md) before running evaluations or accessing datasets.

## Problem
Current Large Language Models (LLMs) often exhibit degraded safety performance when users switch between languages or use low-resource dialects (code-switching). This creates safety gaps—such as hallucinations or jailbreaks—in educational settings for North African youth.

## Approach
We implement a reusable **"verify-then-reply" agentic layer** designed for North African youth education. This layer intercepts student prompts, screens for context-specific risks (hallucinations, cultural toxicity, jailbreaks), and verifies responses before delivery.

## Outputs
We deliver open-source artifacts for the global AI safety community:
* **Agentic Safety Layer:** Open-source architecture for the verification pipeline.
* **Code-Switching Test Suite:** A curated dataset of red-teaming prompts in mixed Arabic/French/Darija.
* **Evaluation Protocol:** TEVV-aligned methodology for measuring safety in mixed-language contexts.

### Verify-then-Reply Pipeline
```mermaid
graph LR
    Input[Student Input] --> PreChecks[Pre-Checks (PII/Toxicity)]
    PreChecks -->|Safe| AgentLoop[Verification Agent Loop]
    PreChecks -->|Unsafe| Refusal[Immediate Refusal]
    AgentLoop -->|Verify| Policy[Policy Decision]
    Policy -->|Safe| Response[Safe Response]
    Policy -->|Unsafe| Refusal
    Policy -->|Escalate| Human[Human Review/Telemetry]
    Response --> Telemetry[Safety Telemetry]
    Refusal --> Telemetry
```

## What We Measure
We track four core metrics to ensure robust safety:
1. **Bypass Success Rate:** Percentage of adversarial prompts that bypass the safety filter.
2. **Interception Rate:** Percentage of unsafe prompts correctly blocked.
3. **PII-Risk Events per 100 Sessions:** Frequency of potential PII leakage.
4. **Reliability Errors:** Rate of false positives/negatives in safety judgments (via blinded audits).

## Repository Structure
```text
.
├── src/                        # Core agentic logic and middleware
├── evaluation/                 # Test suites and benchmarking tools
├── docs/                       # Documentation and governance files
├── CITATION.cff                # Citation metadata
├── DATA_POLICY.md              # Data protection rules
├── SAFEGUARDING.md             # Youth safety protocols
└── README.md                   # This file
```

## Quickstart
> **Note:** These commands are generic. Adjust paths to match your local environment.

```bash
# Clone the repository
git clone https://github.com/HOUSSAM16ai/NAAS-Agentic-Core.git
cd NAAS-Agentic-Core

# Install dependencies
pip install -r requirements.txt

# Run evaluation suite (example)
python evaluation/run_eval.py --suite code-switching-v1 --mode strict
```

## Reproducibility & Transparency
We are committed to open science while protecting participant privacy.
* **We Publish:** Evaluation methods, instruments, aggregated metrics, and anonymised incident patterns.
* **We Never Publish:** Raw youth chat logs, PII, or unredacted specific failure cases that could compromise safety.

## Value to Stakeholders
* **Product Teams:** robust evaluation methodologies for multilingual deployments.
* **NGOs/Educators:** safeguard protocols and deployment-ready safety layers.
* **Policymakers/Regulators:** empirical evidence on code-switching risks and mitigation strategies.

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## How to Cite
Please cite this work using the metadata in [CITATION.cff](CITATION.cff).

## Contact
For research inquiries, please contact: `research-leads@example.org` (Placeholder).

> **Disclaimer:** This repository provides research tools and methods. It does not constitute legal or safeguarding advice. Users are responsible for their own deployment compliance.
