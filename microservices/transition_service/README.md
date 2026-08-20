# Transition Service — منظومة وكلاء تحول الذكاء الاصطناعي

**المنفذ:** 8012 | **العقد:** `docs/contracts/openapi/transition_service-openapi.json` (14 خدمة في بوابة API-first) | **D-240**

طبقة وكلاء متعددة تدير تحول الذكاء الاصطناعي في العمل والتعليم والحوكمة. تعمل بمنهجية **«الحتمية أولًا، والسرود ثانيًا»**: كل رقم يُحسب حتميًا من أطلس مهن/مهارات/وحدات تدريب موثّق (Eloundou β-weighting للتعرض، Acemoglu–Restrepo لمحاكاة السياسات، أطلس WEF 2025 للمهارات)، ولا يدخل LLM في أي حساب؛ دوره الوحيد السرد والتوضيح، مع وضع تهيؤ كامل `LLM_MOCK_MODE=1` (الافتراضي في CI وcompose).

## الوكلاء الثلاثة عشر

| المسار | الوكيل |
|--------|--------|
| `POST /early-warning` | الإنذار المبكر لسوق العمل |
| `POST /occupation-exposure` | التعرض المهني |
| `POST /skills-gap` | فجوة المهارات |
| `POST /career-transition` | الانتقال المهني |
| `POST /education` | التعليم والمناهج |
| `POST /job-creation` | خلق الوظائف |
| `POST /social-protection` | الحماية الاجتماعية |
| `POST /governance` | تصنيف قرار الحوكمة |
| `POST /equity` | العدالة والتمثيل |
| `POST /simulation` | محاكاة السياسات |
| `POST /dialogue` | الحوار الاجتماعي |
| `POST /evaluation` | التقييم والمساءلة (KPIs) |
| `POST /red-team` | الفريق الأحمر |

إضافة إلى: `GET /health`, `GET /agents`, `POST /dispatch` (موجّه عام)، `POST /decide` (بوابة الحوكمة بمستوياتها الأربعة)، `GET /decision-log` و`GET /metrics` (Prometheus).

## بوابة الحوكمة

لا يُنفَّذ أي قرار من المستوى الأول آليًا: `INFORMATIVE → REQUIRES_REVIEW → COMMITTEE_APPROVAL → HIGH_RISK_REJECT`. كل قرار يُسجَّل في سجل تدقيق (request id، الوكيل، المفتاح، المستوى، السبب، وصف الإجراء البشري) قابل للتصدير.

## التشغيل

```bash
docker compose up -d transition-service   # عبر compose (:8012)
# أو محليًا:
LLM_MOCK_MODE=1 uvicorn microservices.transition_service.src.main:app --port 8012
```

## الاختبار

```bash
LLM_MOCK_MODE=1 python -m pytest microservices/transition_service/tests -v
```

61 اختبارًا: وحدية على الأرقام الحتمية (حدود، خطية، عدالة، حتمية) + E2E عبر TestClient على كل المسارات.

## الميثاق

انظر `docs/charter/AI_TRANSITION_CHARTER.md`.
