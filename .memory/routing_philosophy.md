# Routing Philosophy Doctrine

## 1. Purpose
To define the strict architectural boundaries for Intent Classification and Query Routing across the platform, preventing Semantic Hijacking (where broad terms capture unrelated analytical requests).

## 2. Core Invariant
Intent Routing MUST NOT rely on unbounded greedy regular expressions (`(.*)`) or keyword dictatorships (e.g., broad matches for the word "تمرين"). Analytical, deep reasoning, and complex mission intents hold strict priority over simple content retrieval.

## 3. Runtime Implications
- Intent regexes MUST use exact bounds (`^`, `$`) and length constraints (e.g., `.{0,60}`) to limit their capture radius.
- Standard Arabic keywords (e.g., "الاحتمالات") are prefixed with definite articles. Therefore, Python word boundaries (`\b`) MUST be avoided around standard Arabic keywords if they break prefixed matches, unless specifically handled.
- The default behavior for unmatched, long, or complex inputs must fall through to an analytical engine (`DEFAULT`, `DEEP_ANALYSIS`, or `MISSION_COMPLEX`).

## 4. Service Mapping
- `app/services/chat/intent_registry.py` (Central Registry)
- `app/services/chat/intent_detector.py` (Monolith Fallback Router)
- `microservices/orchestrator_service/src/services/overmind/utils/intent_detector.py` (Microservice Router)

## 5. Student Interaction Contract
When a student pastes a long problem description or an analytical question containing words like "تمرين", the system MUST NOT blindly serve a retrieved document. Instead, it must trigger the tutor to read, analyze, and assist the student pedagogically.

## 6. Acceptance Criteria
- A purely conversational or long analytical query containing the word "تمرين" does not trigger `CONTENT_RETRIEVAL`.
- A direct, short query like "اريد تمرين الاحتمالات" successfully triggers `CONTENT_RETRIEVAL`.
- The regex logic remains consistent across both Monolith and Microservice intent detectors.
