# NAAS Lab: EL-NUKHBA (Agentic AI Safety for Education)

**Project:** Agentic Verification Layer for Code-Switching Contexts (Arabic/French/Darija).
**Region:** North Africa (Algeria).
**Status:** Grant Proposal / Pilot Phase.
**Governance Framework:** Aligned with NIST AI RMF (Map, Measure, Manage).

## 1. Overview
**The Problem:** Current Large Language Models (LLMs) often exhibit degraded safety performance when users switch between languages or use low-resource dialects (code-switching). This creates safety gaps—such as hallucinations or jailbreaks—in educational settings for North African youth.

**The Solution:** EL-NUKHBA builds a reusable **"verify-then-reply" agentic layer** designed for North African youth education. This layer intercepts student prompts, screens for context-specific risks (hallucinations, cultural toxicity, jailbreaks), and verifies responses before delivery.

## 2. What We Will Ship (Deliverables)
We are committed to producing reusable, open-source artifacts for the global AI safety community:
* **Agentic Safety Layer:** Open-source architecture for the verification pipeline.
* **Code-Switching Test Suite:** A curated dataset of red-teaming prompts in mixed Arabic/French/Darija.
* **Evaluation Protocol:** TEVV-aligned methodology for measuring safety in mixed-language contexts.
* **Safeguarding Playbooks:** Operational guides for educators and NGOs handling AI in youth contexts.
* **Evidence Report:** Aggregated analysis of failure modes and mitigation strategies.
* **Stakeholder Briefs:** Concise policy memos for regulators and product teams.

## 3. Repository Structure
```text
├── README.md                   # Project overview & reproduction steps
├── SAFEGUARDING.md             # Youth safety protocols, escalation matrix & RACI
├── DATA_PROTECTION.md          # Privacy-by-design, minimization & retention rules
└── docs/
    ├── GRANT_ALIGNMENT.md      # Logic mapping: Objectives -> Budget -> Deliverables
    ├── EVALUATION_PROTOCOL.md  # NIST-aligned metrics & test scenarios (TEVV)
    ├── IMPACT_MEASUREMENT.md   # Wellbeing indicators (SWEMWBS) & reach metrics
    ├── DELIVERABLES_ROADMAP.md # Timeline, milestones & acceptance criteria
    └── RISK_REGISTER.md        # Operational & technical risk management
```

## 4. Reproducibility (High-Level)
To reproduce our evaluation benchmarks (once published):
1. **Clone:** `git clone https://github.com/naas-lab/el-nukhba.git`
2. **Install:** `pip install -r requirements.txt` (Environment setup)
3. **Config:** Set API keys in `.env` (OpenAI/Anthropic).
4. **Run Test:** `python run_eval.py --dataset code_switch_v1 --mode strict`
5. **View Results:** Metrics generated in `data/telemetry/report_latest.json`.

## 5. Open-Source Policy
We adhere to a strict "Open Artifacts, Private Data" policy:
* **Public:** Codebase, Test Suites (sanitized), Aggregated Metrics, Playbooks.
* **Restricted:** Raw student chat logs, PII, Mentor notes (Never published).

## 6. Reviewer Confidence Checklist
* ✅ **Governance:** Aligned with NIST AI RMF functions.
* ✅ **Privacy:** Data minimization & pseudonymization by design.
* ✅ **Safety:** Non-clinical safeguarding with clear escalation paths.
* ✅ **Transparency:** Commitment to publish negative results (failure modes).
