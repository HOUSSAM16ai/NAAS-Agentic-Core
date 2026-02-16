# Data Protection & Privacy-by-Design

**Purpose:** To ensure compliance with GDPR Art. 25 (Data Protection by Design) and ethical research standards.
**Scope:** Collection, processing, and storage of pilot data.

## 1. Data Flow Diagram (Textual)
1.  **Collection:** User inputs (prompts) and AI outputs via the Pilot App.
2.  **Processing:** PII redaction layer runs *before* storage (Pseudonymization).
3.  **Storage:** Encrypted database (Supabase/Postgres) with strict access control.
4.  **Analysis:** Aggregation of anonymized patterns (e.g., "15% failure rate").
5.  **Publication:** Release of aggregated statistics and sanitized artifacts.

## 2. Data Minimization & Retention
| Data Type | Necessity | Retention Period | Action after Retention |
| :--- | :--- | :--- | :--- |
| **Raw Chat Logs** | Validation of safety failures | 12 Months | Permanently Deleted |
| **User PII (Names)** | Consent verification | 24 Months | Permanently Deleted |
| **Anonymized Patterns** | Research evidence | Indefinite | Open-Source Archive |
| **System Telemetry** | Performance monitoring | 6 Months | Aggregated & Deleted |

## 3. Access Control (RACI)
* **Responsible (Access):** Lead Engineer (DB Admin).
* **Accountable (Policy):** Project Lead (PI).
* **Consulted:** External Ethics Advisor (if applicable).
* **Informed:** Participants (via Consent Form).
* **Controls:** Role-Based Access Control (RBAC), Encryption at rest (AES-256) & in transit (TLS 1.2+).

## 4. Publish vs. Not Publish
| Data Type | Status | Example |
| :--- | :--- | :--- |
| **Raw Student Chat** | ❌ NEVER | "My name is Amina and I live in..." |
| **Student PII** | ❌ NEVER | "Student ID: 2024-XA-99" |
| **Aggregated Patterns** | ✅ PUBLISHED | "Darija prompts triggered toxicity filters 12% more often." |
| **Sanitized Test Cases** | ✅ PUBLISHED | "Translate [toxic phrase] to French." (Context removed) |

## 5. Privacy-by-Design Principle
We anchor our architecture to **GDPR Article 25**:
* **By Design:** Privacy is not an addon; the system *defaults* to not storing PII unless explicitly required for consent.
* **By Default:** Users do not need to toggle privacy settings; the most secure setting is the default.
