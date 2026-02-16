# Safeguarding & Youth Safety Protocol

**Purpose:** Defines the duty of care, safety boundaries, and incident response workflows.
**Scope:** All interactions involving minors (~15–20 core pilot, ~100 workshop participants).
**Owner:** Project Lead / Safeguarding Officer.

## 1. Duty of Care & Principles
* **Non-Clinical Role:** We act as technical educators, not mental health professionals. We measure *indicators* of confidence, not clinical diagnoses.
* **Human-in-the-Loop:** A human mentor is strictly required during all live beta-testing sessions with minors.
* **Zero Tolerance:** Immediate suspension of testing if high-severity harm is detected.
* **Consent:** Opt-in required for all participants; Guardian consent required for minors under 18 (per local regulations).

## 2. Prohibited Content
During Red-Teaming workshops, the following inputs are **strictly prohibited**:
* Sexual content or Nudity.
* Self-harm or Suicide instructions.
* Real-world violence planning or promotion of terrorism.
* Personally Identifiable Information (PII) of self or others.

## 3. Incident Taxonomy
| Category | Definition | Severity |
| :--- | :--- | :--- |
| **Hallucination Harm** | AI presents false facts as truth in an educational context (e.g., historical errors). | Low |
| **Code-Switch Jailbreak** | AI bypasses safety filters using mixed Arabic/French/Darija logic. | Med |
| **Toxicity/Bias** | AI generates culturally offensive, sexist, or regionally biased output. | Med |
| **Privacy Leak** | AI requests PII or reveals training data PII. | High |
| **Critical Harm** | AI encourages self-harm, violence, or illegal acts. | Critical |

## 4. Escalation Matrix
| Severity | Action Required | Notification | Timeline |
| :--- | :--- | :--- | :--- |
| **Low** | Log in telemetry; Flag for fine-tuning. Session continues. | Mentor | End of Day |
| **Med** | Pause session for user; Review log; Update system prompt. | Lead Engineer | < 2 Hours |
| **High** | **STOP SESSION.** Remove user. Root cause analysis. | Project Lead | Immediate |
| **Critical** | **STOP ALL TESTING.** Notify Platforms/Parents. Legal consultation. | PI / Ethics Lead | Immediate |

## 5. Safeguarding Evidence (Artifacts)
We maintain the following non-PII logs to prove compliance:
* **Attendance Logs:** Dates/times of sessions (Anonymized User IDs).
* **Session Briefing Checklist:** Signed confirmation that safety rules were read.
* **Incident Log:** Registry of all Med/High flags and resolution time.

## 6. Mentor Checklist
* ✅ **DO:** Intervene if a student seems distressed.
* ✅ **DO:** Remind students this is an AI, not a human.
* ❌ **DON'T:** Leave the room during a live session.
* ❌ **DON'T:** Attempt to diagnose or treat anxiety.
