# Data Policy

This repository and its associated research adhere to the **"data protection by design and by default"** principle. All evaluation data is minimized, encrypted, and governed by strict access controls.

## Data Categories

We collect and process only the minimum data necessary for safety evaluation:

* **Guardian Contact Details:** Collected separately for consent purposes (where applicable). Stored in a distinct, secure database.
* **Participant Age Band:** Collected as a range (e.g., 12-14, 15-17), never as a full date of birth.
* **Pseudonymised IDs:** Unique identifiers assigned to participants, replacing all direct identifiers.
* **Privacy-Preserving Telemetry:** Aggregated signals including unsafe flags, prompt-based bypass attempts, and PII-risk events.
* **Optional Wellbeing Check-ins:** Non-clinical, aggregated responses to simple mood/wellbeing questions.

## Storage and Security

* **Access Control (RBAC):** Data access is restricted to authorized researchers based on role.
* **Encryption:** All data is encrypted in transit (TLS 1.3) and at rest (AES-256).
* **Audit Logs:** Access to sensitive data is logged for accountability.
* **Separation:** Identifiers (e.g., email addresses) are stored separately from research data.

## Data Retention

Data is retained only for the duration of the active research phase plus a defined audit window (e.g., 12 months). Upon expiration, all personal data is permanently deleted securely.
Anonymised, aggregated datasets may be retained indefinitely for scientific reproducibility.

## Publication Rules

To ensure privacy and safety:
* We publish only **aggregated and anonymised** metrics and findings.
* We publish **sanitized test cases** (synthetic or redacted) to demonstrate failure modes.
* We **never** publish raw chat logs, participant identifiers, or unredacted incidents involving minors.
