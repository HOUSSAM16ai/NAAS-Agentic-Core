# NAAS Agent Action Assurance — Evidence-Led Investment Case

> **Audience:** founders, investors, design partners, security leaders, and product reviewers.
> **Status:** investment thesis and falsifiable commercial plan; not proof of revenue, product-market fit, compliance, or investor return.
> **Current technical truth:** [`.memory/naas_verification_truth.md`](../../.memory/naas_verification_truth.md).
> **Target architecture:** [`AGENT_TRUST_CONTROL_PLANE.md`](../architecture/AGENT_TRUST_CONTROL_PLANE.md).

## 1. Thesis in one sentence

As AI moves from generating content to taking consequential actions, enterprises need an independent layer that can prove **who acted, under whose authority, through which tools and policy, what state changed, and whether the result actually satisfied the intended constraints**.

NAAS begins with a narrow paid wedge—pre-production assurance for Arabic customer-service agents performing actions—and earns the right to expand toward a cross-model Agent Trust & Control Plane.

## 2. The pain is observable, not hypothetical

The evidence supports a bounded claim: tool-using agents create a material assurance problem that output-only review cannot fully measure.

| Evidence | What it establishes | What it does not establish |
|---|---|---|
| [AgentDojo, NeurIPS 2024](https://proceedings.neurips.cc/paper_files/paper/2024/hash/97091a5177d8dc64b1da8bf3e1f6fb54-Abstract-Datasets_and_Benchmarks_Track.html) | A stateful benchmark with 97 realistic tasks and 629 security cases found leading agents failed many benign tasks; tool-returned untrusted data enabled harmful actions. | It does not measure NAAS or a specific customer's loss. |
| [InjecAgent, Findings of ACL 2024](https://aclanthology.org/2024.findings-acl.624/) | Across 1,054 cases, 17 user tools, 62 attacker tools, and 30 agents, indirect prompt injection caused direct-harm and private-data-exfiltration behavior; the paper reports 24% vulnerability for ReAct-prompted GPT-4 in its setup. | One benchmark rate must not be generalized to every model, defense, language, or production environment. |
| [METR task-horizon research](https://metr.org/blog/2025-03-19-measuring-ai-ability-to-complete-long-tasks/) | Agent capability on longer, multi-step tasks has improved rapidly, while reliability declines as task length grows. More useful autonomy expands both value and the surface requiring assurance. | The trend is not a revenue forecast and its authors publish methodology and external-validity caveats. |
| [NIST AI Agent Standards Initiative](https://www.nist.gov/artificial-intelligence/ai-agent-standards-initiative) | NIST explicitly prioritizes secure agent protocols, identity/authentication infrastructure, interoperability, and security evaluation. | An initiative is not a certification, mandate, or endorsement of NAAS. |
| [EU AI Act, Regulation (EU) 2024/1689](https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng) | Applicable high-risk systems face requirements around risk management, logging, human oversight, robustness, and post-market monitoring. | Applicability is fact-specific; NAAS is neither legal advice nor automatic compliance. |

The commercial pain appears when an agent can mutate a system of record: refund the wrong order, change an account, disclose protected information, skip an approval, or claim success without the required state transition. The buyer pays to reduce **expected loss, manual review cost, release delay, and evidence-production cost**—not for another generic AI score.

## 3. Why now, and why this can endure

Three structural forces reinforce the need:

1. **Capability expands authority.** Longer autonomous task horizons create more intermediate decisions and side effects to verify.
2. **Identity is moving toward non-human actors.** NIST's initiative and [Microsoft Entra Agent ID](https://www.microsoft.com/en-us/security/blog/2025/05/19/microsoft-extends-zero-trust-to-secure-the-agentic-workforce/) show that agent identity and authorization are becoming explicit infrastructure categories.
3. **Security platforms are buying AI-security capability.** Palo Alto Networks completed its acquisition of Protect AI in July 2025 and described demand spanning model scanning, red teaming, runtime protection, and agent security. This is evidence of strategic demand and competition—not proof of NAAS revenue or valuation.

The enduring unit is not today's model or protocol. It is **accountable delegation**. Models, clouds, and agent frameworks can change while organizations still need attributable authority, policy enforcement, observed state, and durable evidence.

## 4. Initial buyer, job, and offer

**Initial segment:** Arabic-first voice/text agent vendors serving GCC organizations.

**Consequential workflows:** bookings, refunds, ticket transitions, account changes, and access to sensitive customer data.

**Likely buyer:** CTO, Head of AI, product-security owner, or deployment owner carrying release and incident risk.

**Job to be done:**

> Before release or renewal, demonstrate that the agent used the correct tool, within delegated authority and customer policy, reached the required system state, and left reproducible evidence.

**First paid deliverable:** a bounded assurance engagement containing an authorized trace adapter, customer-policy test suite, adversarial cases, replayable evidence bundle, severity-ranked findings, retest, and executive remediation report. It excludes penetration of unapproved production systems, legal certification, and universal safety claims.

## 5. Customer ROI contract

The repository includes a deterministic model in `shared/agent_assurance_roi.py`. Every input must come from a customer-approved baseline or be labelled as a scenario assumption.

```text
review_savings = annual_review_hours × loaded_hourly_cost × measured_review_reduction
incident_loss_avoided = annual_incidents × mean_incident_cost × measured_incident_reduction
total_benefit = review_savings + incident_loss_avoided + evidenced_launch_delay_value
net_benefit = total_benefit − annual_NAAS_cost
ROI = net_benefit ÷ annual_NAAS_cost
payback_months = annual_NAAS_cost ÷ total_benefit × 12
```

### Evidence hierarchy for each input

1. reconciled customer finance/incident/time records;
2. prospectively measured pilot telemetry;
3. customer-approved estimate with owner and date;
4. scenario assumption, visibly labelled and excluded from any “measured ROI” claim.

No avoided regulatory fine, reputational value, future sale, or catastrophic incident may be inserted as a certain benefit. Zero cost or zero benefit produces an undefined ratio/payback, not an artificial infinity or zero.

### Pilot scorecard

| Metric | Baseline | Pilot | Claim gate |
|---|---:|---:|---|
| severe policy violations found | customer process on the same held-out traces | NAAS on the same traces | independent adjudication and denominator required |
| false-negative and false-positive rate | measured | measured | confidence interval and severity weighting required |
| review hours per release | time record | time record | same scope and reviewer population |
| mean evidence preparation time | time record | time record | same audit/release artifact |
| incident or near-miss rate | historical window | prospective window | no causal claim without adequate design |
| delivery cost and gross margin | actual | actual | include human review, support, compute, and rework |

## 6. Venture return logic—without promising returns

An investor can only recover capital if NAAS converts a real budget into recurring, high-margin revenue and creates an outcome large enough relative to invested capital. The repository therefore treats return as a gated model, not a guarantee.

### Bottom-up model

```text
ARR = Σ(customers in segment × evidenced annual contract value)
gross_profit = ARR − direct delivery, compute, support, and third-party costs
net_revenue_retention = retained recurring revenue after churn and expansion ÷ opening recurring revenue
capital_efficiency = net new ARR ÷ net cash burn
```

Valuation multiples, acquisition outcomes, and future financing are sensitivities—not operating facts. Funding announcements or acquisitions validate strategic interest but never substitute for NAAS contracts, retention, or margins.

### Financing gates

| Gate | Evidence required | Capital decision |
|---|---|---|
| Problem | 15 buyer interviews; at least 5 quantify current cost/risk and name a budget owner | fund only a bounded demonstrator |
| Paid proof | 3 unrelated paid pilots for the same job; at least one customer-confirmed severe finding missed by the current process | fund repeatability, not a broad platform |
| Repeatability | ≥70% reusable delivery assets; one renewal; measured positive contribution margin | fund integrations and sales learning |
| Product pull | 10 recurring customers; retention and expansion cohort; no single customer dominates evidence | fund product and regional expansion |
| Scale | repeatable acquisition, acceptable payback, strong gross margin, referenceable outcomes | consider institutional growth capital |

These are internal decision gates, not forecasts. Thresholds may be revised only with recorded evidence and an explicit decision—not to rescue a weak result.

## 7. Defensibility

Code alone is not the moat. Defensibility must accumulate in five assets:

1. permissioned Arabic/dialect/code-switching failure trajectories with adjudicated outcomes;
2. reusable policy graphs for consequential customer-service actions;
3. cross-model and cross-runtime adapters plus normalized action evidence;
4. customer workflow integration and longitudinal proof of reduced review or loss;
5. trust earned through independent, reproducible, scoped evidence.

The independence matters: a model or cloud vendor evaluates its own stack, while NAAS is positioned to produce evidence across providers. That independence is valuable only if buyers recognize and pay for it.

## 8. Competition and the anti-bundling test

The market includes AI-security platforms, observability/evaluation suites, identity vendors, policy engines, MCP gateways, model/cloud-native controls, and internal security teams. The primary strategic threat is bundling by incumbents.

NAAS must beat a customer's current stack on a held-out workflow by producing at least one of:

- a severe path/action failure the current stack misses;
- materially lower evidence-preparation or review cost;
- a cross-provider proof the incumbent cannot independently produce;
- Arabic policy/trajectory coverage with measured lift;
- faster approval of a release or enterprise procurement decision.

If none is demonstrated repeatedly, the standalone product thesis is falsified and the capability should become a service component or be stopped.

## 9. Risk register and falsification

| Risk | Early signal | Decision response |
|---|---|---|
| no standalone budget | praise but no paid pilot or named budget owner | sell through an existing security/compliance budget or stop |
| incumbent bundling | native control matches held-out outcomes and cost | narrow to independent evidence/Arabic specialization; stop generic platform work |
| custom-services trap | reuse below 70% across three pilots | constrain supported workflows or remain a priced service |
| data-access barrier | prospects cannot legally export traces | customer-hosted adapter, minimization, or reject the engagement |
| false positives block operations | shadow precision/recall misses approved threshold | do not enter inline enforcement |
| long enterprise sales cycle | no paid learning inside the runway | target vendors/design partners with shorter deployment authority |
| concentration | one customer supplies most revenue or evidence | delay scale claims and diversify before expansion |

## 10. Ninety-day evidence plan

**Days 1–30 — problem evidence**

- interview 15 qualified buyers and record problem, current process, annual cost/risk, authority, and budget;
- implement one authorized external trace adapter in a sandbox;
- define the held-out comparison against the customer's existing QA/security process.

**Days 31–60 — paid proof**

- close the first bounded paid pilot in foreign currency;
- run baseline and NAAS on the same traces;
- publish only customer-approved, anonymized results with denominators and limitations;
- calculate ROI from recorded inputs using the repository model.

**Days 61–90 — repeatability**

- repeat with two unrelated customers;
- measure reusable test/policy/adapter percentage, direct cost, gross margin, false positives, and delivery time;
- seek one renewal or recurring monitoring agreement;
- decide build, narrow, service-only, or stop from the gates—not from narrative momentum.

## 11. Claim discipline

Allowed now:

- “NAAS implements bounded offline trajectory verification on repository fixtures and reference targets.”
- “The target market and ROI are hypotheses governed by paid-evidence gates.”
- “Peer-reviewed benchmarks and official initiatives establish a broader agent assurance problem.”

Forbidden now:

- “NAAS prevents agent failures,” “is compliant,” “has product-market fit,” “guarantees ROI,” or “will return investor capital.”
- presenting acquisition, funding, total cybersecurity spend, or regulation as NAAS revenue;
- converting a scenario spreadsheet into measured customer savings;
- claiming an Arabic moat before held-out comparative evidence exists.

## 12. Investor diligence checklist

An investor should be able to inspect:

1. the live technical truth and executable tests;
2. source-level support for each market/problem claim;
3. customer-authorized baseline and pilot evidence;
4. signed commercial evidence for status advancement;
5. the reproducible ROI inputs and output;
6. cohort retention, margins, concentration, and cash use when they exist;
7. failed hypotheses and stop decisions, not only successes.

The investable promise is therefore not certainty. It is a disciplined way to turn expanding machine autonomy into **measurable, independent trust infrastructure**, while spending capital only after each layer earns its evidence.
