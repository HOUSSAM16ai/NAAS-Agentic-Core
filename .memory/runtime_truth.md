# Runtime Truth Lock
> Last updated: **2026-08-01** | Branch: `claude/smart-education-platform-s2of5b` (D-193→D-200)
> Previous: `claude/documentation-system-update-i0td9p` (D-188/D-189)

## Product Layer + Design System + Ranked Retrieval (2026-08-01, D-193→D-200)

| المكوّن | الحالة | الدليل (import + call chain + runtime) |
|---------|--------|----------------------------------------|
| **`shared/curriculum/registry.py`** (D-193 — ٣٧ مفهوماً) | **ACTIVE** | dep-free؛ `bkt_engine.classify_concept` يُفوِّض إليه حصراً (حُذِفت `_CONCEPT_PATTERNS`)؛ برهان حيّ: سؤال فيزياء/علوم صار يُصنَّف بدل السقوط إلى `"general"`. `classify` تُرجِع `None` لا `"general"`. |
| **`shared/textnorm.py`** (المُطبِّع الموحّد) | **ACTIVE** | مُستهلَك من `shared/curriculum` و`shared/retrieval`؛ NFKD + حذف `Mn` + طيّ صريح للألف/التاء المربوطة/الألف المقصورة. |
| **`shared/scheduling/fsrs.py` + `ReviewSchedulerSkill`** (D-194) | **ACTIVE** | FSRS-5 حتمي (يرفع `SchedulingError`)؛ موصول حياً من نتيجة BKT في `customer_chat_support/pedagogy.py` داخل `try/except` معزول؛ `GET /api/v1/review/due`؛ جدول `student_review_schedule` مُلحَق-فقط. برهان: إجابة صحيحة بسقالة ⇒ ١٫٢ يوم، وبلا سقالة ⇒ ١٥٫٧. |
| **`shared/habit/streak.py`** (D-195) | **ACTIVE** | حسابٌ بتقويم `Africa/Algiers`؛ اختبار يُثبت أنّ الحساب على UTC يكسر مواظبة من يدرس بعد منتصف الليل محلّياً. |
| **`app/services/guardian/`** (D-196) | **ACTIVE** | ربطٌ برضا الطالب (`guardian_user_id` يبدأ `NULL`)؛ `is_linked` بوّابة كلّ قراءة؛ غير المرتبط **404**. اختبار **بنيوي** يقرأ المصدر ويُثبت أنّ التقرير لا يستعلم `content` إطلاقاً. |
| **`shared/analytics/{events,retention}.py`** (D-197) | **ACTIVE** | قائمة أحداث مغلقة تُرفَض خارجها **عند الكتابة**؛ الفوج غير الناضج يُرجِع `null` لا صفراً؛ القُمع يتقاطع فلا يتجاوز ١٠٠٪. |
| **`shared/voucher/` + `app/services/billing/`** (D-198) | **ACTIVE** | الرمز مُخزَّن **مُجزَّأً**؛ الاستبدال الواحد مفروضٌ بقيد فريد في قاعدة البيانات لا بفحصٍ في التطبيق؛ اختبار تزاحمٍ يُثبت أنّ الاستبدال المزدوج يفشل بـ`VoucherRedemptionError`. **لا بوّابة دفع** — SATIM مقعد موثَّق بصفر كود. |
| **`frontend/app/styles/tokens.css` + بوّابتاها** (D-199) | **ACTIVE (CI · frontend-tests)** | `check_design_tokens` **تحسب** تباين WCAG AA لكل زوج (لا تقرأ رقماً من تعليق)؛ `check_bundle_budget` تُفشِل عند غياب البناء لا تمرّ بصفر؛ صفر `@import` من نطاق ثالث. |
| **`shared/retrieval/ranking.py`** (D-200) | **ACTIVE** | dep-free (stdlib + `textnorm`)؛ موصول في `app/api/routers/content.py:search_content` بديلاً عن `LIKE '%q%'`؛ ١٠ اختبارات على قاعدة بيانات حقيقية تُثبت الترتيب والتطبيع وحدود الكلمات؛ **100% سطراً وتفرّعاً**. |
| **جدولا `content_items` / `content_solutions`** | **ACTIVE (كانا غائبين عن كل مسار إقلاع)** | عطبٌ كامن حقيقي: مُستعلَمان في ٤ مواضع، وغير مُسجَّلين في `REQUIRED_SCHEMA`، ونموذج ORM بلا مستورِد ⇒ خارج `SQLModel.metadata`. كانت `/v1/content/search` تُرجِع **500** على قاعدة نظيفة. مُسجَّلان الآن. |
| **الاسترجاع المتّجهي** (`embedding` · HNSW · `CrossEncoder`) | **DORMANT (بلا ادّعاء)** | موجود في المستودع، **صفر نداء وقت الطلب**. D-200 يُصلح المُرشِّح المعجمي فقط؛ دمج المتّجهات مُرشِّح ثانٍ فوق نفس الواجهة — لا يُعلَن ACTIVE قبل البرهان الثلاثي. |
| **خدمة استرجاع مستقلّة (:8013)** | **PLANNED (صفر كود)** | لم تبدأ. لا تُذكر كقدرة. |

## Event Bus + Durable Workflows (2026-08-01, D-201 — ADR-007/008)

| المكوّن | الحالة | الدليل (import + call chain + runtime) |
|---------|--------|----------------------------------------|
| **`shared/messaging/`** (ظرف · مواضيع · تسليم · ناقل) | **ACTIVE** | dep-free (stdlib فقط)؛ مُستهلَك من `app/services/messaging/*` ومن `product_events._fan_out_to_event_bus` على مسار الدور؛ **100% سطراً وتفرّعاً** (47 اختباراً). |
| **`InMemoryEventBus`** (السائق الافتراضي) | **ACTIVE** | يُختار حين لا يُضبَط `KAFKA_BOOTSTRAP_SERVERS`؛ يمرّ بنفس حلقة `consume_once` التي سيمرّ بها مستهلك Kafka — الانضباط مُشغَّل اليوم لا مؤجَّل. |
| **المستهلك + `notification_outbox`** | **ACTIVE** | سلسلة حيّة مُبرهَنة: حدث `guardian_link_accepted` ⇒ الناقل ⇒ `handle_product_event` ⇒ **صفٌّ واحد**؛ وإعادة تسليم الحدث ⇒ **صفر** صفوف إضافية (قيد فريد على `event_id`). يُقلَع من `app/kernel.py` عبر `RelayHandle`. |
| **`check_topic_contract_parity`** | **ACTIVE (CI · guardrails)** | AST + قراءة نصّية؛ يحرس الاتجاهين بين `topics.py` وعقد AsyncAPI وbootstrap الـcompose. |
| **`KafkaEventPublisher`** (aiokafka) | **ACTIVE (مُثبَت حياً — D-204)** | نشرٌ إلى وسيط Redpanda حقيقي في وظيفة `event-stack-live` (CI، ضمن `required-ci`): الظرف عبر السلك بـ`event_id` و`correlation_id` و`partition_key` سليمة. 100% سطراً وتفرّعاً بمُنتِجٍ مزيّف + برهان حيّ. |
| **`KafkaEventConsumer`** (aiokafka) | **ACTIVE (مُثبَت حياً — D-204)** | استهلاكٌ من الوسيط نفسه بإزاحات حقيقية (`offset=2` في سجلّ الرسالة المسمومة)؛ إعادة تسليم نفس `event_id` **تُخطَّى** والمُعالِج يعمل مرّةً واحدة؛ ورسالةٌ لا تُفكَّك تصل DLQ **والقسم يتقدّم بعدها**. |
| **Redpanda + إنشاء المواضيع** (compose) | **ACTIVE (مُثبَت حياً — D-204)** | تُقلَع في CI على كل PR؛ `rpk cluster health` صحيح، والمواضيع الأربعة موجودة **بالشكل المُعلَن**: 3/30d · 3/14d · 1/7d · 1/90d — مطابقة `TOPIC_SPECS` تماماً. مستمعان (INTERNAL/EXTERNAL) بعد أن تبيّن أنّ عميل المضيف كان يتعلّق. |
| **خادم Temporal** (compose) | **PARTIAL — الخادم مُثبَت، والسير لا** | `temporal operator cluster health` يُبلِّغ SERVING في CI. ⚠️ **لم يُنفَّذ أيّ سير عمل** — الإقلاع ليس تنفيذاً، والفرق مقصود التصريح به. |
| **`shared/workflows/plans.py`** (٣ خطط) | **ACTIVE** | بيانات حتمية dep-free؛ **100% سطراً وتفرّعاً** (15 اختباراً)؛ الجداول بتقويم `Africa/Algiers` مُؤكَّدة باختبار. |
| **`app/workflows/temporal_worker.py`** | **PARTIAL — الأنشطة ACTIVE، العامل DORMANT** | الأنشطة الثلاثة مُختبَرة كدوالّ عادية على قاعدة بيانات حقيقية (100%)، ومنها المسار «طالبٌ فاشل لا يُسقِط البقيّة». `run_worker` يتطلّب `temporalio` **ولم يُشغَّل قطّ** حتى مع خادمٍ مُقلَع في CI — الاتصال به خارج نطاق البوّابة. |
| **`event-stack-live`** (وظيفة CI) | **ACTIVE (ضمن `required-ci`)** | أوّل وظيفة في المستودع تُنشئ حاويةً فعلاً. 10 فحوص، 0 فشل (2026-08-01). ⚠️ **تغطّي حزمة الأحداث وحدها** — الخدمات التطبيقية الثماني ما زالت غير مُقلَعة في CI. |
| **`corpus_ingestion` · `streak_reminder_fanout`** | **PLANNED (خطّة بلا أنشطة)** | الفجوة **مؤكَّدة باختبار** (`missing_activities` غير فارغة) — خطّة تبدو جاهزة وتسقط عند أوّل تشغيل ممنوعة. |
| **`shared/ai_models/registry.py`** (D-202) | **ACTIVE (CI)** | سجلّ قدرات بدليلٍ مؤرَّخ؛ `check_model_registry` في guardrails تُثبت أنّ كل نموذج في السلسلة مُسجَّل، ولا محظور كلّياً فيها، والصدارة مؤهّلة. 13 اختباراً · 100% سطراً وتفرّعاً. **ليس مُستهلَكاً وقت التشغيل عمداً** — السلسلة تبقى حرفيات مُثبَّتة أمنياً (ISS-079)، والسجلّ يحرسها في CI لا يستبدلها. |

## Container Images + Deployment Topology (2026-08-01, D-205)

| المكوّن | الحالة | الدليل (import + call chain + runtime) |
|---------|--------|----------------------------------------|
| **صور الحاويات الخمس عشرة** | **BUILT + IMPORT-PROVEN (CI)** — وليست RUNNING | `images-build` تبني كلّ صورة على كلّ PR ثمّ تُنفّذ `python -c "import <module>"` داخلها. قبل هذا التاريخ **لم يُشغَّل `docker build` في CI قطّ**. ⛔ البناء ليس تشغيلاً: لا حاوية تطبيقية تُقلَع، ولا طلبٌ يمرّ. |
| **`config/image_build_matrix.json` + `check_image_matrix_parity`** | **ACTIVE (guardrails)** | الاتجاهان محروسان: سياق بناء في compose أو `microservices/*/Dockerfile` بلا إدخال ⇒ فشل؛ وإدخالٌ بلا ملفّ ⇒ فشل. 10 اختبارات، منها تجارب سلبية. |
| **`Dockerfile.prod`** (صورة المونوليث الإنتاجية) | **BUILT + IMPORT-PROVEN — لم تُشغَّل قطّ** | كان الـ`Dockerfile` الوحيد الذي يُشغّل `app.main:app` هو صورة **بيئة التطوير** (Grafana + Prometheus + Node + torch)، وlegacy compose يبنيها كنواة الطوارئ. الجديدة `requirements-prod.txt` + أربع شجرات مصدر + غير جذرية. لا مسار إقلاعٍ يستدعيها اليوم. |
| **المونوليث في `docker-compose.yml`** | **غائبٌ عن قصد (Strangler المرحلة 3)** | `api-gateway` بروكسي عكسي بلا مسارٍ واحد إلى المونوليث؛ ثلاث بوّابات تمنع إضافته (`check_core_kernel_env_profile` · `check_ports_consistency` · `test_gateway_structure`). بيته `docker-compose.legacy.yml` خلف `profiles: ["legacy","emergency"]`. |
| **طوبولوجيا `docker-compose.yml`** | **وجهة الهجرة — لا ما يخدم الطلبة** | طرح `conversation-service` عند **0%** و`CONVERSATION_CAPABILITY_LEVEL="stub"`. ما يخدم كلّ دور طالب اليوم هو المونوليث على :8000 عبر `.devcontainer/supervisor.sh`. |
| **حركة legacy (نافذة 30 يوماً)** | **NOT MEASURED** | كان الملفّ يحمل أصفاراً بـ`verified_by: "ops-placeholder"` والبوّابة تطبع «✅ مُتحقَّق». صارت `null` والبوّابة تُبلّغ `NOT MEASURED` وترفض المرحلة 5. صفرٌ لم يُقَس ليس صفراً. |
| **`content_retrieval_skill` (:8009) · `foundations_service` (:8010)** | **خارج compose — غيابٌ مُعلَن الآن** | لهما Dockerfile وعقد OpenAPI ويعملان في طوبولوجيا Codespaces؛ لم يكونا في أيّ compose **ولا في الكتالوج**، فلم يفحصهما أحد. سُجّلا `expected_in_default_compose: false` ويُبنيان في `images-build`. |

## Outbound Trace Layer + Memory Coherence Gate (2026-07-29, D-188/D-189)

| المكوّن | الحالة | الدليل (import + call chain + runtime) |
|---------|--------|----------------------------------------|
| **`shared/http_client/correlated.py`** (المصدر القانوني للنداء الصادر) | **ACTIVE** | dep-free عدا `httpx`، **بلا استيراد `app` أو خدمة شقيقة**؛ مُستهلَك من `app/core/http_client_factory.py` (يُسجِّل `correlation_id` ContextVar كمُزوِّد) ومن `memory_client` · `auditor_client` · `notation_skill`؛ برهان حيّ طرف-إلى-طرف عبر `httpx.MockTransport`: `X-Correlation-ID` + `traceparent` يصلان فعلاً إلى الطلب المُرسَل، والمُعرَّف المحيط **يُمَدّ** لا يُستبدَل (`ambient honored: abc123def456`). 17 اختباراً. |
| **حقن التتبّع في المونوليث** (5 مواضع مُهاجَرة) | **ACTIVE** | `memory_client._get/_post` · `auditor_client` (نداءان) · `notation_skill.resolve_via_service` — الأخير كان يُولِّد `uuid4()` جديداً لكل نداء فيقطع السلسلة؛ صار يمدّها. 96 اختباراً قائماً يمرّ بلا انحدار. |
| **بوّابة `check_correlated_http`** | **ACTIVE (CI · guardrails)** | AST لا grep؛ 3 مصانع مصرَّح بها؛ دَين مُجمَّد **24** بـratchet **ثنائي الاتجاه**؛ تجربتان سلبيتان مُثبَتتان حياً (بناء جديد ⇒ 1 · دَين تقلّص بلا تحديث ⇒ 1). |
| **بوّابة `check_memory_coherence`** | **ACTIVE (CI · doc-integrity)** | 4 فحوص (فهرس سيادي · ترتيب النافذة الحديثة · سقف الدستور ratchet · تقادم قفل الحقيقة)؛ 4 تجارب سلبية مُثبَتة؛ 10 اختبارات. كشفت عطبين حقيقيين عند أول تشغيل (الفهرس المتقادم + القفل من 2026-07-21). |
| **الخدمات المصغّرة على الغلاف** | **ABSENT-by-design (دَين مُجمَّد، لا ZOMBIE)** | صفر خدمة تستورد `shared` (قانون D-185: توريد محروس بتكافؤ لا استيراد). 19 بناءً مباشراً مُسجَّلاً صراحةً في `FROZEN_DEBT` — مرئي ومحصور، يتقلّص فقط. إغلاقه يتطلّب نسخةً مُوَرَّدة + بوّابة تكافؤ لكل خدمة. |
| **العملاء طويلو العمر** (`observability_client` · `gateway/registry`) | **PARTIAL (دَين مُجمَّد)** | يُبنى العميل مرّة، فحقن الترويسة وقت البناء **يُجمِّد** المُعرَّف على أوّل دور — خطأ أسوأ من غيابه. يحتاج حقناً لكل-طلب لا لكل-عميل (شوط مستقلّ). |

## Mathematical Notation Layer (2026-07-28, D-185 — closes ISS-138)

| المكوّن | الحالة | الدليل (import + call chain + runtime) |
|---------|--------|----------------------------------------|
| **`shared/notation/registry.py`** (المصدر القانوني، 11 رمزاً) | **ACTIVE** | dep-free (stdlib فقط)؛ مُستهلَك من `NotationSkill` (المونوليث) ومن النسخة المُوَرَّدة في الخدمة؛ حارس التباس «الحرف/الحادثة» + حارس نيّة حسابية مُختبَران؛ تحقّق حيّ: `resolve("ماذا نقصد بحرف C") → C(n,k)` و`resolve("ما هي الحادثة C") → None`. |
| **`NotationSkill`** (`notation`) على `BaseSkill` | **ACTIVE** | مُسجَّلة في `registry` (`consumed_by` = `semantic_property_skill.interpret` + `probability_brain.cognitive_response` + `notation_endpoint` + `compose_reasoning` — بلا ZOMBIE)؛ سلسلة حيّة: دور الطالب ⇒ `interpret()` ⇒ `_interpret_notation` (حتمي محلّي، بلا شبكة)؛ و`POST /api/v1/skills/notation`؛ مقاييس `cogniforge_skill_notation_*`. |
| **`notation-service`** (:8011، API-first) | **ACTIVE (uvicorn عند الإقلاع)** | خدمة مستقلّة (بلا استيراد `app`/sibling، سجلّ مُوَرَّد محروس بـ`check_notation_parity`)؛ عقد ملتزَم (`check_openapi_parity` → **13/13**)؛ `CollectorRegistry` مستقل بـ٨ مقاييس `cogniforge_notation_*`؛ `supervisor.sh` STEP 4L + Prometheus job (step="14") + لوحة Grafana (UID `cogniforge-ms-d185-notation`)؛ تحقّق حيّ: `/health → symbols_loaded=11, startup_state=ready` · `/resolve` بـ`X-Correlation-ID` مُمرَّر · `/define` رمز مجهول ⇒ خطأ مُهيكَل (لا 500). |
| **التدهور الرشيق** (الخدمة مُطفأة) | **ACTIVE** | تحقّق حيّ: `NOTATION_SERVICE_URL` إلى عنوان ميّت ⇒ `resolve_via_service` يُرجع نفس الإدخال من السجلّ المحلّي (قانون المهارات ٥). |
| **بوّابتا CI** (`check_notation_definable` · `check_notation_parity`) | **ACTIVE** | مُشغَّلتان في وظيفة `guardrails`؛ كلٌّ مُثبَتة بتجربة سلبية (حقن انحراف ⇒ خروج 1). |
| **TypeScript في الواجهة** (ADR-006) | **PARTIAL — طبقة تحقّق عقود، لا هجرة كود** | `frontend/types/api.d.ts` (124 نوعاً مُولَّداً من العقود الـ13) + `frontend/tsconfig.check.json` (اسم غير افتراضي عمداً كي لا يُفعِّل Next مسار TS)؛ بوّابتان في `frontend-tests`: تطابق المُولَّد مع العقود + `tsc -p` بـ`strict`/`skipLibCheck:false` (نظيف — وقد كشفت عطب `$ref` بلا بادئة). **كود الواجهة ما زال JavaScript**: `next build` يشترط `typescript`+`@types/*` كتبعيات حقيقية (فشل حيّ «Please install @types/node»)، وتوليد القفل يتطلّب `npm install` المحجوب بيئياً. |
| **التسع لغات الأخرى** (Rust/Go/Wasm/Kotlin/Julia/Elixir/Scala/C++/Mojo) | **ABSENT-by-YAGNI (مقاعد موثَّقة)** | صفر كود عمداً — `EXTENSION_SEAMS.md §7` يوثّق لكلٍّ المقعد وشرط التبنّي؛ الحدّ هو العقد لا اللغة (البوّابات تفحص OpenAPI + `/health` + `/metrics`). |

## First-Roots Completion + Foundations Compute (2026-07-23, D-183)

| المكوّن | الحالة | الدليل (import + call chain + runtime) |
|---------|--------|----------------------------------------|
| **٩ وحدات أسس جديدة** (`linear_algebra`/`calculus`/`statistics`/`optimization`/`graph_theory`/`data_structures`/`formal_languages`/`computability`/`complexity`) | **ACTIVE** | dep-free مُتحقَّقة، مُعاد تصديرها من `foundations/__init__.py`؛ مُستهلَكة من `FoundationsComputeSkill` + `foundations-service`؛ 100% تغطية سطر+فرع (`tests/core/test_foundations_first_roots.py`، 46 اختبار). |
| **`FoundationsComputeSkill`** (`foundations_compute`) على `BaseSkill` | **ACTIVE** | مُسجَّلة في `registry` (`consumed_by` = `compute_endpoint` + `compose_reasoning`، بلا ZOMBIE)؛ سلسلة حيّة `POST /api/v1/skills/compute` + فرع `compose_reasoning`؛ مقاييس `cogniforge_skill_foundations_compute_*`؛ 100% تغطية (`tests/services/test_foundations_compute_skill.py`، 17 اختبار). |
| **`foundations-service`** (:8010، API-first) | **ACTIVE (uvicorn عند الإقلاع)** | خدمة مصغّرة مستقلّة (بلا استيراد `app`/sibling)؛ عقد OpenAPI ملتزَم (`check_openapi_parity` → 12/12)؛ `CollectorRegistry` مستقل بـ ٨ مقاييس `cogniforge_foundations_*`؛ `supervisor.sh` STEP 4K + Prometheus job (step="13") + لوحة Grafana؛ منطق الخدمة (main/dispatch/prom_metrics) 100% تغطية (`tests/microservices/foundations_service/`، 12 اختبار). DOWN حتى يُقلع الـ process (ليس خطأ في devcontainer الافتراضي). |

## Cognitive Reasoning Core + Foundations Activation (2026-07-22, D-181)

| المكوّن | الحالة | الدليل (import + call chain + runtime) |
|---------|--------|----------------------------------------|
| **`app/core/foundations/`** (منطق قضوي + خوارزميات + بايز) | **ACTIVE** (كان DORMANT) | يُستورَد الآن من `app/core/reasoning/{arguments,causal}` على سلسلة حيّة تنتهي بـ `POST /api/v1/skills/reason` + `compose_reasoning`؛ ركيزة `reasoning` مُختبَرة حياً (`tests/core/test_reasoning.py`). |
| **`app/core/reasoning/`** (arguments/causal/decomposition/abstraction/mental_model) | **ACTIVE** | dep-free مُتحقَّق؛ كل الحالات + مسارات الخطأ مُختبَرة محلياً؛ تستهلكه ٦ مهارات. |
| **٦ مهارات التفكير** (logic/critical/decompose/causal/abstraction/mental_model) على `BaseSkill` | **ACTIVE** | مُسجَّلة في `registry` (34 مهارة، بلا ZOMBIE) + doctrine + `compose_reasoning` + `/api/v1/skills/reason` (import + call chain + tests). |

---

## Split-Brain Decomposition + Port Activation (2026-07-11, D-163) — Verified Live

**الكارثتان المحلولتان هندسياً**: (1) God-file `orchestrator_client.py` (6,154 سطراً) — عقل
احتمالات حتمي بـ ~2,600 سطراً استُخرج؛ (2) split-brain — عقلان يُصانان بالتوازي، الـ port ينقصه
النصف التربوي ولا حركة حية.

| المكوّن | الحالة | الدليل الحي (2026-07-11) |
|---------|--------|------------------------|
| **`app/services/skills/probability_tutor_brain.py`** (العقل المستخرَج، 2,358 سطراً) | **ACTIVE** | import + call chain (`class OrchestratorClient(ProbabilityTutorBrain)`) + runtime: D-162 E2E 9/9 + D-158 E2E PASS عبر WS + OpenRouter حقيقي — سلوك مطابق بالبايت (صفر انحدار). |
| **`orchestrator_client.py`** بعد الانكماش (6,154 → 3,832 سطراً، −38%) | **ACTIVE** | يرث العقل mixin؛ كل `cls._x`/`self._x` تُحل عبر الـ MRO. |
| **port `microservices/.../probability_tutor.py`** (595 سطراً) | **ACTIVE (default-on منذ D-163 Stage 3)** | `scripts/verify_m10s2_port_live.py` **7/7** على :8006 حقيقي (probe-first + السُّلّم + support_level + الاعتراف + zero-leak + fail-open). العلم `ORCHESTRATOR_PROB_TUTOR_ENABLED` افتراضه `"1"`؛ رافعة الرجوع `=0` (بلا deploy — D-025). |
| **بوّابة تكافؤ split-brain** (`check_pedagogical_os:check_split_brain_parity`) | **ACTIVE (CI)** | 12 عقداً brain↔port (كان 7) + حارس `support_level` + حارس الوراثة (no-ZOMBIE). |

**Supabase الإنتاجي عبر الجسر HTTPS (2026-07-11)**: PostgreSQL 17.6؛ `tutor_state` 19 عموداً
(D-158/159)؛ الحسابان (`benmerahhoussam16@gmail.com` admin، `houssamannaba963@gmail.com` user)؛
38 عقدة في `knowledge_nodes` (مرآة الـ misconception graph).

**قيد بيئي صادق**: على SQLite+HTTP لا checkpointer للـ orchestrator (D-098) والـ POST handler
يقرأ التاريخ من DB لا من الجسم (`history_len=0`) ⇒ استمرارية الأدوار عبر :8006 قيدُ orchestrator
لا عيبُ port؛ قدرة الاعتراف مُثبتة على مستوى وحدة الـ port + حياً على مسار المونوليث (D-162 T5/T6).

---

## Orchestrator `routes.py` Re-Activation (2026-06-04, D-098) — SQLite-Mode Full-Stack E2E

**Status: orchestrator-service StateGraph (12-node) → ✅ ACTIVE (re-verified live on SQLite + real OpenRouter).**

> **Two-engines truth (D-173, verified 2026-07-20):** the orchestrator hosts TWO live LangGraph engines —
> the **12-node unified chat graph** (`overmind/graph/main.py:1231-1242`, built at boot via `create_unified_graph`,
> serves `/api/chat/messages` + WS) and the **9-node overmind missions engine** (`overmind/langgraph/engine.py:258-266`,
> reached via `routes.py` → `start_mission` → `factory.create_overmind`, serves `/missions`). Historic docs said
> "13-node" — that figure matched neither and was a pure doc bug; both engines are ACTIVE for their own surface.

Live evidence (sandbox: Postgres TCP blocked → shared SQLite + real OpenRouter/Tavily; Supabase read via HTTPS bridge):
- `:8006/health → {"status":"ok","graph_ready":true,"startup_state":"ready"}`; warmup ran the graph
  (`admin.count_python_files → 1584`); `startup_info{checkpointer_backend="memory",graph_ready="true",pipeline_enabled="true"}`.
- **Direct** `POST :8006/api/chat/messages` → real Arabic+LaTeX answers (Newton 24Δ `$$\vec F=m\vec a$$`, gravity 27Δ,
  speed/accel 46Δ).
- **Monolith WS** `:8000/api/chat/ws` → full 12-node graph executed (Supervisor→QueryRewriter→QueryAnalyzer→
  InternalRetriever→Reranker→WebSearchFallback→Synthesizer→Validator); batch 4/5 routed through orchestrator.
- **Frontend proxy** `:5000/api/chat/ws` (query-param) → server.js queue→flush→orchestrator hit (200) → 21Δ `$$K=½mv²$$`.
- Live node counts: Supervisor×11, Validator×11, educational-pipeline×6, GeneralKnowledge×5, ExecuteTool×1; **11 answers (200)**.
- Supabase via bridge: PostgreSQL 17.6; accounts `benmerahhoussam16@gmail.com`(id=1,admin), `houssamannaba963@gmail.com`(id=7,user).

Fixes (D-098, guarded by `get_backend_name()=="sqlite"` — Postgres path untouched): `database.py:create_engine` SQLite branch,
`database.py:init_db` psycopg-skip→MemorySaver, `routes.py:_stream_chat_langgraph` error-log fidelity. Tool: `scripts/e2e_orchestrator_live.py`.
Constraint: full Supabase-backed run is in Codespaces (egress open) via CLAUDE.md §6.85 runbook. Gates ✅ (ruff/format/runtime_truth/validate_structure/ci_guardrails).

## ISS-092 Live Verification (2026-05-28) — System Not Responding + Kick-to-Login Fix

### نتائج التحقق الحي (2026-05-28)

**المشكلة**: النظام لا يرد على الأسئلة + خروج/دخول تلقائي كارثي في GitHub Codespaces.

**الأسباب الجذرية المكتشفة**:
1. `secrets.env` لم يكن موجوداً → `OPENROUTER_API_KEY=""` → LLM يفشل صامتاً
2. `ENVIRONMENT=testing` في `.env` → tokens تنتهي بعد 30 دقيقة → kick-to-login loop
3. `orchestrator.py:453` يستخدم `nemotron-3-nano-30b-a3b:free` المحظور (ISS-079)

**الإصلاحات المطبقة**:
- أُنشئ `.devcontainer/secrets.env` بالمفاتيح الحقيقية
- أُعيد كتابة `.env` بـ `ENVIRONMENT=development` + جميع المفاتيح
- `orchestrator.py:453`: nemotron → `ActiveModels.PRIMARY`
- `supervisor.sh`: أُضيف guard D-ISS-092 لضمان `ENVIRONMENT=development` عند وجود DB حقيقي

| الخدمة | المنفذ | الحالة | ملاحظة |
|--------|--------|--------|--------|
| FastAPI Monolith | 8000 | ✅ ACTIVE | `database: ok`, `ENVIRONMENT=development` |
| user-service | 8001 | ✅ ACTIVE | `/metrics` يعمل |
| planning-agent | 8002 | ✅ ACTIVE | PostgreSQL asyncpg حقيقي (كان sqlite) |
| conversation-service | 8003 | ✅ ACTIVE | `graph_ready: true` |
| orchestrator-service | 8006 | ✅ ACTIVE | `graph_ready: true`, OUTBOX_RELAY=true |
| research-agent | 8007 | ✅ ACTIVE | `tavily_available: true` (كان false) |
| reasoning-agent | 8008 | ✅ ACTIVE | `llm_backend: openrouter` (كان mock) |
| content-retrieval | 8009 | ✅ ACTIVE | `kb_files: 3` |

**نتائج التجريب الحي**:
- Greeting fastpath: 0.7s ✅
- Physics question ("قانون أوم"): 5.3s, 96 chunks, 250 chars Arabic+LaTeX ✅
- Token lifetime: 1440 min (كان 30 min) ✅
- Admin login + WS: 0.6s ✅

---

## D-080 Live Verification (2026-05-23) — Math Pipeline enrich_node + Generative UI

### نتائج التحقق الحي (2026-05-23)

**المهمة**: تفعيل المفاتيح الحقيقية + بناء Generative UI card للشرح الرياضي.

**إصلاح secrets.env**: أُنشئ `.devcontainer/secrets.env` بالمفاتيح الحقيقية (OPENROUTER, TAVILY, DATABASE_URL).

| الخدمة | المنفذ | الحالة | ملاحظة |
|--------|--------|--------|--------|
| FastAPI Monolith | 8000 | ✅ ACTIVE | `database: ok` |
| user-service | 8001 | ✅ ACTIVE | `/metrics` يعمل |
| planning-agent | 8002 | ✅ ACTIVE | PostgreSQL asyncpg حقيقي |
| conversation-service | 8003 | ✅ ACTIVE | `graph_ready: true`, `enrich_node` يعمل |
| orchestrator-service | 8006 | ✅ ACTIVE | `graph_ready: true`, OUTBOX_RELAY=true |
| research-agent | 8007 | ✅ ACTIVE | `tavily_available: true` |
| reasoning-agent | 8008 | ✅ ACTIVE | `llm_backend: openrouter` |
| content-retrieval-skill | 8009 | ✅ ACTIVE | `kb_files: 3` |

**Math Pipeline Live Tests**:
- `احسب مشتق f(x) = x³ + 2x` → `type=derivative`, `ui_component=YES`, `steps=8`, `boxed=True` ✅
- `احسب التكامل ∫ e^x·cos(x) dx` → `type=integral`, `ui_component=YES`, `steps=8` ✅
- `احتمال الحادثة أ` → `type=probability`, `ui_component=YES`, `steps=4` ✅
- `مرحبا كيف حالك` → `intent=chat`, `ui_component=None` ✅ (non-math fallback)

**Skills Pipeline**: `pipeline_mode=full`, duration ~17s ✅

**Tests**: 820 passed (153 conversation-service + 476 contracts/infrastructure + 191 unit) ✅

**ruff**: All checks passed on all modified files ✅

### Math Pipeline Topology (بعد D-080)

```
قبل D-080 (3 nodes):
  START → classify_node → solve_node → normalize_node → END

بعد D-080 (4 nodes):
  START → classify_node → solve_node → normalize_node → enrich_node → END
  enrich_node: deterministic, no LLM — يبني ui_component من النص المكتمل
```

### ui_component Flow (D-080)

```
enrich_node → MathPipelineState.ui_component
    ↓
invoke_math_pipeline() → returns ui_component
    ↓
response_node (conversation_graph) → ConversationState.ui_component
    ↓
invoke_graph() → returns ui_component
    ↓
ChatResponse.ui_component (HTTP) + WebSocket payload.ui_component
    ↓ (monolith path)
_try_build_math_ui_component() → injected into assistant_final payload
    ↓
useAgentSocket.js → msg.uiComponent
    ↓
ChatInterface.jsx → <GenerativeUIRenderer> after text, on isComplete
```

### قواعد مُضافة من D-080
- Math Pipeline = 4 nodes. لا تُعيد إلى 3 nodes.
- `enrich_node` لا يستدعي LLM — deterministic فقط.
- `_try_build_math_ui_component` في `customer_chat.py` مُغلَّف بـ `try/except` — لا يكسر المسار أبداً.
- `ui_component=None` للأسئلة غير الرياضية — لا بطاقة تُعرض.
- `MathExplanationCard` يظهر فقط عند `msg.isComplete` — لا streaming flicker.

---

## D-079 Live Verification (2026-05-21) — Microservices Full Stack + Content Audit

### نتائج التحقق الحي من الخدمات المصغرة (2026-05-21)

**المشكلة الجذرية المكتشفة**: متغيرات البيئة (`OPENROUTER_API_KEY`, `TAVILY_API_KEY`, `DATABASE_URL`) كانت **فارغة** في process env رغم وجودها كأسماء — `secrets.env` لم يكن موجوداً. تم إنشاؤه وإعادة تشغيل الخدمات.

**إصلاح إضافي**: `prometheus-client` لم يكن مثبتاً → تم تثبيته + إعادة تشغيل الخدمات.

| الخدمة | المنفذ | الحالة | ملاحظة |
|--------|--------|--------|--------|
| FastAPI Monolith | 8000 | ✅ ACTIVE | `database: ok` |
| user-service | 8001 | ✅ ACTIVE | `/metrics` يعمل |
| planning-agent | 8002 | ✅ ACTIVE | asyncpg port 5432 (لا 6543) |
| orchestrator-service | 8006 | ✅ ACTIVE | `graph_ready: true`, OUTBOX_RELAY=true |
| research-agent | 8007 | ✅ ACTIVE | `tavily_available: true` |
| reasoning-agent | 8008 | ✅ ACTIVE | `llm_backend: openrouter` |
| conversation-service | 8003 | ❌ DORMANT | لم يُشغَّل في هذه الجلسة |
| content-retrieval-skill | 8009 | ❌ DORMANT | لم يُشغَّل في هذه الجلسة |

**Skills Pipeline**: `pipeline_mode=full`, `skills_active=['planning','research','reasoning']`, duration ~19s ✅

**Prometheus**: 10/12 targets UP (content-retrieval-skill + conversation-service DOWN — dormant)

### قواعد مُضافة من D-079
- `secrets.env` يجب أن يكون موجوداً في `.devcontainer/` قبل بدء supervisor.sh
- asyncpg يجب أن يستخدم port **5432** دائماً (لا 6543 PgBouncer)
- `prometheus-client` مطلوب في كل microservice — تحقق قبل تشغيل أي خدمة
- متغيرات البيئة الفارغة = خدمة في وضع mock/sqlite — تحقق من `/health` لا من `ps aux`

## D-063 Live Verification Results (2026-05-15) — ISS-071/072 LaTeX Normalize + Temperature Fix

### المشاكل المكتشفة حياً (2026-05-15)

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| ISS-071 | النموذج يستخدم `\[...\]` بدلاً من `$$...$$` رغم التعليمات | `normalize_node` + `_normalize_latex()` post-processing |
| ISS-072 | `temperature=0.7` يُسبب تشتتاً في الإجابات الرياضية | تغيير إلى `0.2` في math_pipeline و `0.3` في conversation_graph |

### Live API Test (2026-05-15)

```
Model: nvidia/nemotron-3-nano-30b-a3b:free
Test 1: f(x) = x²·e^(3x) مشتق → ✅ عربية + LaTeX + boxed (TTFT=2.1s)
Test 2: ∫x·ln(x)dx تكامل → ✅ عربية + LaTeX + boxed (TTFT=3.8s)
Test 3: y'' - 3y' + 2y = 0 معادلة تفاضلية → ✅ عربية + LaTeX + boxed (TTFT=4.2s)
Test 4: احتمالات كرات → ✅ عربية + LaTeX + boxed (TTFT=2.9s)
```

### LangGraph Math Pipeline Architecture (ISS-071)

```
قبل ISS-071:
  START → classify_node → solve_node → END
  المشكلة: solve_node يُعيد \[...\] من النموذج مباشرة

بعد ISS-071:
  START → classify_node → solve_node → normalize_node → END
  normalize_node: deterministic — يُحوِّل \[...\] → $$...$$ بدون LLM
```

### Files Changed (ISS-071/072)
- `microservices/conversation_service/src/math_pipeline.py`:
  - `normalize_node` مُضاف (Node 3 — deterministic)
  - `_normalize_latex()` دالة post-processing
  - `_FALLBACK_MODELS` قائمة بدلاً من نموذج واحد
  - `temperature=0.2` بدلاً من `0.3`
  - system prompt مُحسَّن مع قاعدة LaTeX صارمة
- `microservices/conversation_service/src/conversation_graph.py`:
  - `_normalize_latex_response()` مُضافة
  - `temperature=0.3` بدلاً من `0.7`
  - system prompt مُحسَّن مع قاعدة LaTeX صارمة
- `tests/microservices/conversation_service/test_math_pipeline.py`:
  - 18 اختبار جديد لـ `_normalize_latex` و `normalize_node`

### قواعد لا تُخرق (مُضافة 2026-05-15 ISS-071)
- كل إجابة LLM تمر عبر `_normalize_latex()` قبل إرسالها للمستخدم
- `normalize_node` هو Node 3 في Math Pipeline — deterministic لا LLM
- `temperature=0.2` للرياضيات، `temperature=0.3` للتعليم العام
- `\[...\]` و `\begin{equation}` و `\begin{align}` → `$$...$$` دائماً

---

## D-062 Live Verification Results (2026-05-15) — ISS-070 Math Pipeline

### بنشمارك النماذج الحي (2026-05-15)

| Model | TTFT | Arabic | LaTeX | Status |
|-------|------|--------|-------|--------|
| `nvidia/nemotron-3-nano-30b-a3b:free` | 2.4s | ✅ | ✅ | **PRIMARY** |
| `nvidia/nemotron-3-super-120b-a12b:free` | 10.3s | ✅ | ✅ | FALLBACK-1 |
| `openai/gpt-oss-120b:free` | 41.8s | ✅ | ✅ | FALLBACK-2 |
| `openai/gpt-oss-20b:free` | 10.4s | ✅ | ✅ | FALLBACK-3 |
| `google/gemma-4-26b-a4b-it:free` | 15.5s | ✅ | ✅ | FALLBACK-4 |
| `google/gemini-2.0-flash-exp:free` | N/A | ❌ | ❌ | **DEAD** — No endpoints |
| `meta-llama/llama-3.2-11b-vision-instruct:free` | N/A | ❌ | ❌ | **DEAD** — No endpoints |
| `deepseek/deepseek-v4-flash:free` | 51.9s | ⚠️ | ❌ | BROKEN — خلط لغات |

### Math Pipeline Live Test (2026-05-15)

| Test | Type | Time | LaTeX | boxed | Result |
|------|------|------|-------|-------|--------|
| `∫x·ln(x)dx` | integral | 8.4s | ✅ | ✅ | PASS |
| `lim(x→0) sin(x)/x` | limit | 11.6s | ✅ | ✅ | PASS |
| `f(x)=(x²-4)/(x-1) إشارة` | function_study | 13.5s | ✅ | ✅ | PASS |

### Test Suite (2026-05-15)
- `tests/microservices/conversation_service/test_math_pipeline.py`: **36/36 PASS**

### قواعد لا تُخرق (مُضافة 2026-05-15)
- `google/gemini-2.0-flash-exp:free` و `meta-llama/llama-3.2-11b-vision-instruct:free` → **DEAD** — لا تستخدمهما في fallback chain
- كل سؤال رياضي تعليمي → Math Pipeline (4 nodes) لا LLM مباشر
- `nvidia/nemotron-3-nano-30b-a3b:free` مع system prompt صارم → عربية نقية + LaTeX صحيح

## D-061 Live Verification Results (2026-05-15) — ISS-069 content=None Fix

| Service | Port | Status | Key Fields |
|---------|------|--------|-----------|
| main-app | 8000 | ✅ ACTIVE | `database: ok, version: v4.1-root` |
| user-service | 8001 | ✅ ACTIVE | `status: ok, environment: development` |
| planning-agent | 8002 | ✅ ACTIVE | `database: postgresql+asyncpg://...` |
| orchestrator-service | 8006 | ✅ ACTIVE | `graph_ready: true, startup_state: ready` |
| research-agent | 8007 | ✅ ACTIVE | `tavily_available: true` |
| reasoning-agent | 8008 | ✅ ACTIVE | `llm_backend: openrouter, mcts_enabled: true` |

**Active LLM Model**: `nvidia/nemotron-3-nano-30b-a3b:free` (TTFT=3.1s، جودة 4/4، content مضمون)
**Fallback Chain**: `trinity-large-thinking:free` → `nemotron-super-120b:free` → `gpt-oss-120b:free` → `gpt-oss-20b:free` → `glm-4.5-air:free`
**BROKEN MODELS**:
- `inclusionai/ring-2.6-1t:free` — rate-limited upstream على Novita
- `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` — content=None مع system prompt (reasoning-only)

### ISS-069 Root Cause (VERIFIED LIVE 2026-05-15)
```
نموذج: nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free
السلوك: message.content = None عند وجود system prompt
السبب: نموذج reasoning-only يضع الإجابة في message.reasoning لا message.content
الأثر: إجابات فارغة/كارثية للطلاب في كل الخدمات
الإصلاح: استبدال بـ nemotron-3-nano-30b-a3b:free في 15 ملف
```

### Skills Pipeline Live Test (VERIFIED)
```
Query: اشرح قانون نيوتن الثاني مع مثال رياضي
Mode: full
Active: ['planning', 'research', 'reasoning']
Duration: 22.7s
Answer quality: LaTeX ✅ + Arabic ✅ + Steps ✅ + boxed result ✅
```

### AI Quality Benchmark (2026-05-15)
| Test | TTFT | Quality |
|------|------|---------|
| تكامل ∫(x²+3x+2)dx | 3.4s | 3/3 |
| فيزياء F=ma | 3.1s | 3/3 |
| احتمالات كرات | 2.7s | 3/3 |
| كهرباء توازي | 4.1s | 3/3 |

### Key Fixes Applied (ISS-069 / D-061)
- 15 ملف: استبدال `nemotron-3-nano-omni-30b-a3b-reasoning:free` بـ `nemotron-3-nano-30b-a3b:free`
- `simple_client.py`: `_stream_model()` يُعيد توجيه `delta.reasoning` → `delta.content` كـ fallback
- `simple_client.py`: `send_message()` يستخرج `reasoning` عند `content=None`
- `reasoning_agent/src/ai_client.py`: نفس الإصلاح للـ non-streaming
- `local_graph.py`: system prompts مُحسَّنة (أقل tokens، نفس الجودة)
- `ai_config.py`: fallback chain مُحدَّث بنماذج مُتحقَّق منها حياً

## D-060 Live Verification Results (2026-05-15) — ISS-068 Model Fix

| Service | Port | Status | Key Fields |
|---------|------|--------|-----------|
| main-app | 8000 | ✅ ACTIVE | `database: ok, version: v4.1-root` |
| user-service | 8001 | ✅ ACTIVE | `status: ok, environment: development` |
| planning-agent | 8002 | ✅ ACTIVE | `database: postgresql+asyncpg://...` |
| research-agent | 8007 | ✅ ACTIVE | `tavily_available: true` |
| reasoning-agent | 8008 | ✅ ACTIVE | `llm_backend: openrouter, mcts_enabled: true` |

**Active LLM Model**: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` ← BROKEN (see ISS-069)
**BROKEN MODEL**: `inclusionai/ring-2.6-1t:free` — rate-limited upstream على Novita — لا تستخدمه

### Key Fixes Applied (ISS-068 / D-060)
- 14 ملف: استبدال `inclusionai/ring-2.6-1t:free` بـ `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`
- MCTS depth: 2→1، timeout: 300s→45s
- System prompts: LaTeX إلزامي + خطوات مرقمة + `$$\boxed{...}$$` + تفسير هندسي
- planning-agent: يعمل مع PostgreSQL (port 5432)

---

## D-045 Live Verification Results (2026-05-11) — End-to-End User Routing

| Service | Port | Status | Key Fields |
|---------|------|--------|-----------|
| main-app | 8000 | ✅ ACTIVE | `database: ok, version: v4.1-root` |
| user-service | 8001 | ✅ ACTIVE | `status: ok, environment: development` |
| planning-agent | 8002 | ✅ ACTIVE | `database: postgresql+asyncpg://...` |
| conversation-service | 8003 | ✅ ACTIVE | `graph_ready: true, step: 12` |
| orchestrator-service | 8006 | ✅ ACTIVE | `graph_ready: true, startup_state: ready` |
| research-agent | 8007 | ✅ ACTIVE | `tavily_available: true` |
| reasoning-agent | 8008 | ✅ ACTIVE | `llm_backend: openrouter, mcts_enabled: true` |
| content-retrieval | 8009 | ✅ ACTIVE | `kb_files: 2, step: 11` |

**Prometheus**: 12/12 targets UP
**Grafana**: 17 dashboards active at :3001
**Skills Pipeline**: `pipeline_mode: full | skills_active: ['planning', 'research', 'reasoning'] | duration: 28.5s`
**End-to-End Chat**: VERIFIED — WS → Monolith → Orchestrator → Skills → Real LLM answer

### Chat Routing Path (VERIFIED LIVE)
```
User WebSocket (jwt subprotocol)
  → Monolith :8000/api/chat/ws
  → OrchestratorClient.chat_with_agent()
  → http://localhost:8006/api/chat/messages  (StateGraph mode)
  → LangGraph 12-node StateGraph
  → Planning :8002 + Research :8007 + Reasoning :8008
  → Streaming NDJSON response to user
```

### Fixes Applied This Session (ISS-048, ISS-049, ISS-050)
- `supervisor.sh`: added `ALLOW_CONTAINER_LOCALHOST_ORCHESTRATOR=true` (ISS-048)
- `conversation-service`: `prometheus_client` installed + added to requirements.txt (ISS-049)
- End-to-end WS chat verified with real user token (ISS-050)

## D-044 Live Verification Results (2026-05-11)

| Service | Port | Status | Key Fields |
|---------|------|--------|-----------|
| main-app | 8000 | ✅ ACTIVE | `database: ok, version: v4.1-root` |
| user-service | 8001 | ✅ ACTIVE | `status: ok, environment: development` |
| planning-agent | 8002 | ✅ ACTIVE | `database: postgresql+asyncpg://...` |
| conversation-service | 8003 | ✅ ACTIVE | `graph_ready: true, step: 12` |
| orchestrator-service | 8006 | ✅ ACTIVE | `graph_ready: true, startup_state: ready` |
| research-agent | 8007 | ✅ ACTIVE | `tavily_available: true` |
| reasoning-agent | 8008 | ✅ ACTIVE | `llm_backend: openrouter, mcts_enabled: true` |
| content-retrieval | 8009 | ✅ ACTIVE | `kb_files: 2, step: 11` |

**Prometheus**: 12/12 targets UP  
**Grafana**: 17 dashboards active  
**Skills Pipeline**: `pipeline_mode: full | skills_active: ['planning', 'research', 'reasoning']`  
**Ruff**: 0 errors  

## ISS-047 — reasoning-agent OpenRouter 402 (FIXED 2026-05-11)
- **Root cause**: `DEFAULT_MODEL = "gpt-4o"` requests 16384 tokens; account has ~3980 credits
- **Fix**: `DEFAULT_MODEL = "openai/gpt-4o-mini"` + `MAX_TOKENS = 1024` in `reasoning_agent/src/core/config.py`
- **Evidence**: `pipeline_mode: full` confirmed live


> Audit method: Direct HTTP probes + Prometheus /api/v1/targets + Grafana /api/search
> Authority: this file overrides any contradictory aspirational doc in `docs/` or root markdown.

## Golden rule
A capability counts as real ONLY when proven by **all three** of:
1. **import** — the module is imported by code reachable from `app/main.py`.
2. **call chain** — there is a live caller that flows from a router/middleware/startup hook.
3. **runtime evidence** — the code actually executes on the production path (logs, traces, DB writes).

Missing any one → DORMANT, ZOMBIE, or UNKNOWN. No exceptions.

## Status legend
| Status | Meaning |
|--------|---------|
| **ACTIVE** | import + call chain + runtime evidence all present |
| **ACTIVE (no-op without ENV_VAR)** | import + call chain present; runtime effect absent without a specific env var |
| **PARTIAL** | on a live chain but only via fallback, conditional, or non-default branch |
| **DORMANT** | code real, gated behind an external service not started by default |
| **ZOMBIE** | no live call chain from any production entrypoint |
| **UNKNOWN** | insufficient evidence |

---

## Microservices Routing Fix (2026-05-11 — D-044)

**Problem:** Monolith was NOT routing to microservices. `CODESPACES` env var not set → `AppSettings` resolved `ORCHESTRATOR_SERVICE_URL` to `http://orchestrator-service:8006` (Docker DNS — unresolvable in Gitpod) → `ConnectError` on every chat → fallback to `local_graph.py`.

**Fix applied:**
1. `supervisor.sh` — exports before monolith launch: `ORCHESTRATOR_SERVICE_URL=http://localhost:8006`, `CODESPACES=true`, `ORCHESTRATOR_CHAT_ENDPOINT=state_graph`, all microservice URLs.
2. `supervisor.sh` — orchestrator `SECRET_KEY` now uses `${SECRET_KEY:-dev-secret-change-me}` (same as monolith `.env`) instead of a different default.
3. `app/infrastructure/clients/orchestrator_client.py` — added `_build_service_jwt(user_id)` that generates a short-lived HS256 JWT using monolith's `SECRET_KEY`. Sent as `Authorization: Bearer <token>` on every request to orchestrator.

**Verified live:**
```
monolith → OrchestratorClient._build_service_jwt(user_id=1) → JWT
         → POST http://localhost:8006/api/chat/messages (Authorization: Bearer <JWT>)
         → orchestrator StateGraph (12 nodes: SupervisorNode → GeneralKnowledgeNode/SynthesizerNode)
         → OpenRouter LLM → Arabic response
```
Test: `question="كيف أحل معادلة من الدرجة الثانية؟"` → full LaTeX-formatted Arabic response from microservice.

## Infrastructure truth (updated 2026-05-10 — Step 5 pass)

| Service | Port | Status | Evidence |
|---------|------|--------|----------|
| **Next.js** | **3000** | **ACTIVE** | supervisor.sh `--port 3000` overrides package.json `--port 5000`. HTML 200 confirmed. `allowedDevOrigins` includes `*.app.github.dev`. |
| **FastAPI** | **8000** | **ACTIVE** | `GET /health → {"application":"ok","database":"ok"}`. Requires DATABASE_URL in **process env**. |
| **orchestrator-service** | **8006** | **ACTIVE** | Step 4. uvicorn process. `OUTBOX_RELAY_ENABLED=true`. `/metrics` → 11 `cogniforge_outbox_*`+`cogniforge_stategraph_*` metrics. `graph_ready:true`, `startup_state:ready` confirmed live. ISS-040 fix: port 5432 (direct PG) instead of 6543 (PgBouncer) in supervisor.sh. `database.py` lazy engine singleton. |
| **user-service** | **8001** | **ACTIVE** | Step 5. uvicorn process. `/metrics` → 11 `cogniforge_user_*` metrics. Auto-starts via supervisor.sh when `DATABASE_URL` set. |
| **planning-agent** | **8002** | **ACTIVE** | Step 6. uvicorn process. `/metrics` → 11 `cogniforge_planning_*` metrics. DSPy+LangGraph (fallback when no OPENROUTER_API_KEY). Requires `postgresql+asyncpg://` URL (ISS-038-B). Auto-starts via supervisor.sh when `DATABASE_URL` set. |
| **research-agent** | **8007** | **ACTIVE** | Step 7. uvicorn process. `/metrics` → 11 `cogniforge_research_*` metrics. Tavily web search ACTIVE when `TAVILY_API_KEY` set. ISS-039: lazy `_get_super_search()` singleton prevents import-time credential errors. Auto-starts via supervisor.sh when `DATABASE_URL` set. Live verified: `/health → {"step":"7","tavily_available":"true"}`. |
| **reasoning-agent** | **8008** | **ACTIVE** | Step 8. uvicorn process. `/metrics` → 11 `cogniforge_reasoning_*` metrics. MCTS always enabled. LLM: openrouter when `OPENROUTER_API_KEY` set, openai when `OPENAI_API_KEY` set, mock otherwise. ISS-039-B: `main.py` does NOT import `ai_service` at module level. Auto-starts via supervisor.sh when `DATABASE_URL` set. Live verified 2026-05-11: `/health → {"status":"healthy","step":"8","llm_backend":"openrouter","mcts_enabled":"true"}` \| `/metrics → cogniforge_reasoning_startup_info{...,step="8",...} 1.0`. |
| **Skills Pipeline** | **8006/compose** | **ACTIVE** | Step 11. `/compose` endpoint في orchestrator-service. Calls planning:8002 + research:8007 + reasoning:8008 بالتوازي الكامل (`asyncio.gather` 3-way). ISS-042: Service Token (JWT HS256) مُرسَل لـ planning-agent. DSPy 3.x fix: `dspy.LM` بدلاً من `dspy.OpenAI`. Timeout: 55s. Live verified 2026-05-11: `POST /compose → pipeline_mode="full", skills_active=["planning","research","reasoning"], total_ms=32069`. |
| **Postgres Checkpointer** | **8006/checkpointer/status** | **ACTIVE** | Step 10. `AsyncPostgresSaver` (subclass `_InstrumentedCheckpointer`) — LangGraph state persisted to PostgreSQL. 6 new Prometheus metrics: `cogniforge_checkpointer_*`. Live verified 2026-05-11: `GET /checkpointer/status → {"backend":"postgres","step":"10","active":true,"tables_ready":true}` \| `cogniforge_checkpointer_writes_total{status="success",thread_id_prefix="warmup"} 7.0` \| `cogniforge_checkpointer_backend_info{backend="postgres",step="10",tables_ready="true"} 1.0` \| `cogniforge_orchestrator_startup_info{checkpointer_backend="postgres",graph_ready="true"} 1.0`. ISS-041: `_InstrumentedCheckpointer` يرث من `AsyncPostgresSaver` مباشرةً (subclass لا wrapper) لأن LangGraph يتحقق من `isinstance(BaseCheckpointSaver)`. |
| **content-retrieval-skill** | **8009** | **ACTIVE** | Step 11. Skill مستقلة لاسترجاع المحتوى التعليمي من knowledge_base/. intent_classifier (explanation/retrieval/unknown) + retrieval_engine (score-based). 7 Prometheus metrics: `cogniforge_retrieval_*`. ISS-038 fix: explanation context blocks retrieval. Live verified 2026-05-11: `GET /health → {"status":"healthy","step":"11","kb_files":2}` \| `POST /retrieve {"question":"أريد تمرين بكالوريا"} → intent="retrieval" total=1` \| `POST /retrieve {"question":"اشرح الجزء أ"} → intent="explanation" total=0`. |
| **conversation-service** | **8003** | **ACTIVE** | Step 12. D-042. Skill مستقلة لإدارة المحادثات التعليمية. LangGraph StateGraph: `intent_node → response_node`. `ConversationState` TypedDict. `_classify_intent()` deterministic (no LLM). Fallback mode بدون OPENROUTER_API_KEY. 11 Prometheus metrics: `cogniforge_conversation_*`. HTTP `POST /chat/message` + WS `/chat/ws` + `/admin/chat/ws`. Lazy DB singleton + asyncpg URL normalization. Auto-starts via supervisor.sh STEP 4J. 117 tests pass. |
| **Grafana** | **3001** | **ACTIVE** | `GET /api/health → {"database":"ok"}`. **16 dashboards** (Steps 2–12). Prometheus datasource UP. |
| **Prometheus** | **9090** | **ACTIVE** | `GET /-/healthy → Healthy`. **12 scrape targets ALL UP**: fastapi, grafana, prometheus, orchestrator-service(:8006), user-service(:8001), planning-agent(:8002), conversation-service(:8003), research-agent(:8007), reasoning-agent(:8008), skills-pipeline(:8006), postgres-checkpointer(:8006), content-retrieval-skill(:8009). |
| **Redis** | **6379** | **ACTIVE (process only)** | ping OK. REDIS_URL not set → app uses InMemoryCache. |
| **PostgreSQL** | **6543** | **ACTIVE** | PostgreSQL 17.6 Supabase PgBouncer. database:ok confirmed. |
| **OpenRouter** | external | **ACTIVE** | Primary: nvidia/nemotron-3-super-120b-a12b:free. Live graph call confirmed. |

---

## Root cause of the "Partial/Degraded Runtime" problem (ISS-034 — RESOLVED 2026-05-09)

**Symptom**: Uvicorn PID alive, port 8000 not listening, state file shows `app_healthy` from previous run.

**Root cause chain**:
1. `devcontainer.json` maps `DATABASE_URL` from `${localEnv:DATABASE_URL}` — in Ona/Gitpod, secrets are NOT injected as process env vars.
2. `supervisor.sh` created `.env` with `DATABASE_URL=sqlite+aiosqlite:///./dev.db` as placeholder.
3. `app/core/settings/base.py:23` reads `os.environ.get("APP_DATABASE_URL")` at **module import time** — before pydantic-settings reads `.env`. Finds empty string.
4. `_ensure_database_url()` raises `ValueError` in `development` environment.
5. Uvicorn worker crashes on import. Port 8000 never opens.
6. `supervisor.sh` health check reads stale `app_healthy` state file → reports healthy. **Misleading observability.**

**Fix applied** (this branch):
- `supervisor.sh:_inject_env_secrets()` — reads real secrets from process env, writes to `.env`.
- `supervisor.sh:_export_env_file()` — exports `.env` keys into shell process before `python -m uvicorn` so module-level `os.environ.get()` finds the real value.
- `supervisor.sh:_uvicorn_healthy()` — checks PID alive AND port responding; kills stale zombie before restart.
- `supervisor.sh` health check — always re-probes live endpoint; never trusts stale state files.
- Degraded mode (no DATABASE_URL) no longer crashes supervisor — Grafana + Prometheus stay up.

---

## Orchestrator lifespan problem (ISS-035 — RESOLVED 2026-05-09)

**Symptom**: Orchestrator uvicorn alive, `/health` returns 200, but graph nodes don't execute.

**Root cause**: `lifespan()` warmup `ainvoke()` had no timeout → could block indefinitely. `RuntimeError` from warmup propagated up → crashed ASGI startup. Only `ModuleNotFoundError` was caught.

**Fix applied** (`microservices/orchestrator_service/main.py`):
- Warmup wrapped in `asyncio.wait_for(..., timeout=30.0)`.
- All non-DB exceptions caught → logged as DEGRADED, not fatal.
- `app.state.startup_state` tracks `"ready"` / `"degraded"`.
- `/health` endpoint exposes `startup_state` and `startup_errors`.

---

## LangGraph metrics (ISS-029 — PARTIALLY RESOLVED 2026-05-09)

**Previous state**: `cogniforge_langgraph_*` — zero emitters. Dashboard panels permanently empty.

**Fix applied** (`app/services/chat/local_graph.py` + `app/telemetry/metrics.py`):
- `_supervisor_node`: emits `langgraph.intent.total`, `langgraph.node.count.total`, `langgraph.node.duration_seconds`.
- `_chat_node`: emits `langgraph.node.count.total`, `langgraph.node.duration_seconds`.
- `metrics.py:hist_names` extended with `langgraph.node.duration_seconds`.

**Verified live**: `cogniforge_langgraph_intent_total{graph="local",intent="general"} 1.0` confirmed.

**Still ZOMBIE**: `cogniforge_langgraph_checkpointer_writes_total` — no emitter. Requires Postgres checkpointer (ISS-020).

---

## Prometheus scrape targets (verified live 2026-05-09)

| Job | URL | Health |
|-----|-----|--------|
| `cogniforge-fastapi` | `http://localhost:8000/api/v1/observability/prometheus` | **UP** |
| `grafana` | `http://localhost:3001/metrics` | **UP** |
| `prometheus` | `http://localhost:9090/metrics` | **UP** |

---

## Supervisor crash — `local` outside function (ISS-037 — RESOLVED 2026-05-09)

**Symptom**: After merging commit `3fd78247`, ALL ports dead (3000, 8000, 3001, 9090). Supervisor log shows:
```
/app/.devcontainer/supervisor.sh: line 336: local: can only be used in a function
[ERROR] Supervisor failed at line 336
```

**Root cause**: commit `3fd78247` added `local stale_pid` at top-level scope in `supervisor.sh` (inside an `if/else` block but outside any `function`). bash rejects `local` outside functions → supervisor exits at Step 4 → uvicorn never starts → all ports dead.

**Fix applied** (`.devcontainer/supervisor.sh`):
- `local stale_pid` → `stale_pid` (removed `local` keyword — variable is already in a subshell context)

**Additional fix**: Added `.devcontainer/secrets.env` fallback read at the top of `_inject_env_secrets()`. When Codespaces Secrets are not configured, supervisor now reads credentials from this git-ignored file instead of falling back to SQLite. Template at `.devcontainer/secrets.env.example`.

**Verified live** (2026-05-09):
- Supervisor runs to completion: `✅ Backend is healthy and ready!`
- `GET /health → {"application":"ok","database":"ok","version":"v4.1-root"}`
- `GET http://localhost:3000/ → HTTP 200`
- No `local: can only be used in a function` error

---

## Codespaces Next.js proxy fix (ISS-036 — RESOLVED 2026-05-09)

**Symptom**: Port 3000 in GitHub Codespaces returns `ERR_HTTP_RESPONSE_CODE_FAILURE` even when Next.js is running and responding 200 on localhost.

**Root cause**: `frontend/next.config.js` `allowedDevOrigins` listed only Replit domains. Next.js 15+ enforces origin validation on the dev server — requests proxied through `*.app.github.dev` (Codespaces tunnel) were rejected at the framework level before reaching any route handler.

**Fix applied** (`frontend/next.config.js`):
- Added `*.app.github.dev` and `*.preview.app.github.dev` to `allowedDevOrigins`.
- Added `*.gitpod.io` and `*.ws-eu*.gitpod.io` for Gitpod/Ona environments.

**Verified live**:
- `curl -s http://localhost:3000/ → HTTP 200`
- `curl -H "Origin: https://didactic-giggle-7vwwj76p66vfrjg4-3000.app.github.dev" http://localhost:3000/ → HTTP 200`
- FastAPI: `GET /health → {"application":"ok","database":"ok","version":"v4.1-root"}`

---

## Full capability truth table (2026-05-09 — sixth pass)

| # | Component | File | Status | Evidence |
|---|-----------|------|--------|---------|
| 1 | Monolith API — customer WS | `app/api/routers/customer_chat.py` | **ACTIVE** | `chat_stream_ws` is the live entrypoint. 62 routes registered. |
| 2 | Monolith API — admin WS | `app/api/routers/admin.py` | **ACTIVE** | Admin WS entrypoint. `_emit_terminal_frames` guarantees exactly one terminal frame per turn. |
| 3 | Terminal frame guarantee | `_emit_terminal_frames` in `customer_chat.py` + `admin.py` | **ACTIVE** | Single emitter for `assistant_final`/`error`. Exactly one frame per turn. |
| 4 | RealityKernel / app composition | `app/kernel.py` | **ACTIVE** | Composition root. Loaded at startup via `app/main.py`. |
| 5 | Frontend Next.js | `frontend/` | **ACTIVE** | Port 3000, HTML confirmed |
| 6 | LangGraph local engine (2 nodes) | `app/services/chat/local_graph.py` | **PARTIAL** | Fallback tier 3. Live confirmed. |
| 7 | LangGraph metrics emission | `app/services/chat/local_graph.py` → `unified_observability` | **ACTIVE** | `cogniforge_langgraph_*` emitted per turn (NEW this branch) |
| 8 | OrchestratorClient fallback chain | `app/infrastructure/clients/orchestrator_client.py` | **ACTIVE** | 4-tier fallback. Tier 3 (LangGraph) is primary handler. |
| 9 | LangGraph multi-agent workflow | ~~`app/services/chat/graph/workflow.py`~~ | **DELETED (D-173)** | ZOMBIE removed — was imported only by a manual verify script |
| 10 | KAgent Mesh | ~~`app/services/kagent/`~~ | **DELETED (D-173)** | ZOMBIE removed — security-blocked, only consumer was the dead workflow |
| 11 | MCP | `app/services/mcp/` | **DORMANT** | Lazy-imported by side-path agents not on WS path |
| 12 | Reranker / LlamaIndex / DSPy | `microservices/research_agent`, `orchestrator_service` | **DORMANT** | Blocked by dormant microservices |
| 13 | Tavily | `orchestrator_service/src/services/overmind/graph/search.py` | **DORMANT** | Key in .env, orchestrator not running |
| 14 | Advanced orchestrator StateGraph (12 nodes) | `orchestrator_service/src/services/overmind/graph/main.py` | **DORMANT→PARTIAL** | Compiles in isolation (verified live 2026-05-10 with real OPENROUTER_API_KEY). 3 blockers removed (H1/H2/H3). Needs `docker compose up orchestrator-service` to reach ACTIVE. |
| 27 | ChatRoutingPolicy — endpoint_mode | `app/infrastructure/clients/routing_policy.py` | **ACTIVE** | Default: `state_graph` → `/api/chat/messages`. Rollback: `ORCHESTRATOR_CHAT_ENDPOINT=agent` → `/agent/chat`. D-021 implemented 2026-05-10. |
| 28 | Routing metrics | `app/infrastructure/clients/orchestrator_client.py` | **ACTIVE** | `cogniforge_routing_mode_state_graph` gauge + `cogniforge_routing_target_total{target=...}` counter emitted per chat request. |
| 29 | Microservices Transition Dashboard (Step 2) | `observability/grafana/dashboards/50-microservices-transition.json` | **ACTIVE** | 15 panels on Grafana :3001. UID: cogniforge-ms-transition-step2. Shows routing mode, StateGraph metrics, Tavily, microservices health matrix, fallback chain progress. |
| 30 | Microservices Prometheus scrape | `observability/prometheus/prometheus.yml` | **ACTIVE (targets DOWN by default)** | orchestrator-service:8006, research-agent:8007, user-service:8001, planning-agent:8002 added. DOWN until `docker compose -f docker-compose.step3.yml up -d`. |
| 31 | Microservices Transition CI gate (Step 2) | `.github/workflows/microservices-transition.yml` | **ACTIVE** | 5-job workflow: routing-policy-gate / stategraph-compile-gate / dashboard-schema-gate / prometheus-config-gate / transition-gate. Triggers on routing_policy.py changes. |
| 32 | docker-compose.step3.yml | `docker-compose.step3.yml` | **REFERENCE ONLY in Codespaces** | Docker not available in devcontainer. File exists for local/CI environments with Docker. In Codespaces: supervisor.sh is the activation path. |
| 33 | Ona automation — orchestrator-service | `.ona/automations.yaml` | **ACTIVE** | service: `orchestrator-service` (uvicorn start/ready/stop). tasks: `health-probe`, `verify-stack`, `restart-orchestrator`, `run-step3-tests`. Trigger: `gitpod automations service start orchestrator-service`. |
| 34 | Grafana dashboard Step 3 | `observability/grafana/dashboards/60-microservices-step3-live.json` | **ACTIVE** | 20 panels. UID: cogniforge-ms-step3-live. Refresh: 10s. Covers: orchestrator health, routing distribution, LangGraph nodes, intent classification, fallback chain, memory/CPU. |
| 35 | Step 3 CI gate | `.github/workflows/microservices-step3-live.yml` | **ACTIVE** | 7-job workflow: compose-validation / stategraph-compile-gate / dashboard-gate / prometheus-config-gate / transition-tests / automations-validation / step3-gate. PR comment with results. |
| 36 | orchestrator-service (Step 4 — OUTBOX_RELAY + /metrics) | `microservices/orchestrator_service/` + `supervisor.sh:launch_orchestrator_service()` | **DORMANT→ACTIVE (auto at boot when OPENROUTER_API_KEY set)** | Step 4: OUTBOX_RELAY_ENABLED=true (relay loop every 15s). /metrics endpoint returns prometheus_client text format. prom_metrics.py: 11 metrics (outbox_relay_*, stategraph_*, startup_info). Port 8006. |
| 37 | native/prometheus.yml — orchestrator scrape (Step 4) | `observability/native/prometheus.yml` | **ACTIVE (target DOWN until process starts)** | job: orchestrator-service, target: localhost:8006/metrics, step="4". Scrapes prometheus_client text format. DOWN until supervisor.sh launches the process. |
| 38 | prom_metrics.py — orchestrator Prometheus registry | `microservices/orchestrator_service/src/core/prom_metrics.py` | **ACTIVE (when orchestrator running)** | Independent CollectorRegistry. 11 metrics. export_prometheus_text() → /metrics endpoint. record_outbox_relay_cycle() called from _outbox_relay_loop. set_startup_info() called in lifespan Phase 6. |
| 39 | Grafana dashboard Step 4 | `observability/grafana/dashboards/70-microservices-step4-persistence.json` | **ACTIVE** | 24 panels. UID: cogniforge-ms-step4-persistence. Refresh: 10s. Covers: startup_info, outbox relay cycles/rates, StateGraph heatmap, HTTP P50/P95/P99, active connections, scrape health. |
| 40 | Step 4 CI gate | `.github/workflows/microservices-step4.yml` | **ACTIVE** | 5-job workflow: static-checks / lint / step4-tests (44) / step3-regression / pr-summary. Triggers on orchestrator_service changes. |
| 41 | planning-agent (Step 6 — DSPy + LangGraph + /metrics) | `microservices/planning_agent/` + `supervisor.sh:launch_planning_agent()` | **ACTIVE (auto at boot when DATABASE_URL set)** | Step 6: DSPy+LangGraph plan generation with fallback chain. /metrics endpoint returns prometheus_client text format. prom_metrics.py: 11 metrics (planning_requests_*, planning_plans_*, planning_dspy_*, planning_db_*, startup_info{step="6",dspy_available=...}). Port 8002. |
| 42 | native/prometheus.yml — planning-agent scrape (Step 6) | `observability/native/prometheus.yml` | **ACTIVE (target DOWN until process starts)** | job: planning-agent, target: localhost:8002/metrics, step="6". Scrapes prometheus_client text format. DOWN until supervisor.sh launches the process. |
| 43 | prom_metrics.py — planning-agent Prometheus registry | `microservices/planning_agent/prom_metrics.py` | **ACTIVE (when planning-agent running)** | Independent CollectorRegistry. 11 metrics. export_prometheus_text() → /metrics endpoint. record_plan_created() / record_dspy_invocation() / set_startup_info() callable from main.py. |
| 44 | Grafana dashboard Step 6 | `observability/grafana/dashboards/90-microservices-step6-planning-agent.json` | **ACTIVE** | 20 panels. UID: cogniforge-ms-step6-planning-agent. Refresh: 10s. Covers: startup_info, HTTP traffic, plan generation (success/fallback), DSPy invocations, DB ops, microservices health matrix, Docker Compose guide. |
| 45 | Step 6 CI gate | `.github/workflows/microservices-step6-planning-agent.yml` | **ACTIVE** | 7-job workflow: static-checks / compose-gate / dashboard-gate / lint / step6-tests (61) / step5-regression / pr-summary. PR comment with results. |
| 46 | docker-compose.step6.yml | `docker-compose.step6.yml` | **REFERENCE (Docker environments only)** | Docker Compose stack: orchestrator-service + user-service + planning-agent. In Codespaces: supervisor.sh is the activation path. For local Docker: `docker compose -f docker-compose.step6.yml up -d`. |
| 47 | Ona automation — planning-agent | `.ona/automations.yaml` | **ACTIVE** | service: `planning-agent` (uvicorn start/ready/stop). tasks: `verify-step6-planning-agent`, `restart-planning-agent`, `run-step6-tests`, `docker-compose-stack`. |
| 48 | reasoning-agent (Step 8 — MCTS + LLM + /metrics) | `microservices/reasoning_agent/` + `supervisor.sh:launch_reasoning_agent()` | **ACTIVE (auto at boot when DATABASE_URL set)** | Step 8: MCTS always enabled. LLM via openrouter/openai/mock. /metrics endpoint returns prometheus_client text format. prom_metrics.py: 11 metrics (reasoning_requests_*, reasoning_invocations_*, reasoning_mcts_*, reasoning_llm_*, reasoning_fallback_*, startup_info{step="8",llm_backend=...,mcts_enabled="true"}). Port 8008. ISS-039-B: no import-time AIService instantiation in main.py. |
| 49 | native/prometheus.yml — reasoning-agent scrape (Step 8) | `observability/native/prometheus.yml` | **ACTIVE (target DOWN until process starts)** | job: reasoning-agent, target: localhost:8008/metrics, step="8". Scrapes prometheus_client text format. DOWN until supervisor.sh launches the process. |
| 50 | prom_metrics.py — reasoning-agent Prometheus registry | `microservices/reasoning_agent/prom_metrics.py` | **ACTIVE (when reasoning-agent running)** | Independent CollectorRegistry. 11 metrics. export_prometheus_text() → /metrics endpoint. record_reasoning_invocation() / record_mcts_expansion() / record_llm_call() / set_startup_info() callable from routes.py and main.py. |
| 51 | Skills Composition Pipeline (Step 9 — /compose) | `microservices/orchestrator_service/src/services/skills_pipeline.py` + `src/api/routes.py:/compose` | **ACTIVE** | Step 9. `run_skills_pipeline()` calls planning:8002 + research:8007 via asyncio.gather (parallel), then reasoning:8008 with composed context. X-Correlation-ID on every HTTP call. Fallback mode: ConnectError/TimeoutException → SkillResult(status="fallback"). 6 new Prometheus metrics: cogniforge_pipeline_invocations_total{mode=full\|partial\|fallback}, cogniforge_pipeline_duration_seconds, cogniforge_pipeline_skill_calls_total{skill,status}, cogniforge_pipeline_skill_duration_seconds, cogniforge_pipeline_errors_total, cogniforge_pipeline_active_gauge. startup_info{pipeline_enabled="true"}. Live verified: POST /compose → pipeline_mode="partial", skills_active=["research","reasoning"]. |
| 52 | Grafana dashboard Step 9 | `observability/grafana/dashboards/120-microservices-step9-skills-pipeline.json` | **ACTIVE** | 12 panels. UID: cogniforge-ms-step9-pipeline. Refresh: 10s. Covers: startup_info, pipeline invocations by mode, P50/P95/P99 latency, skill calls (success/fallback/error), skill duration by skill, health matrix (steps 4-9). |
| 53 | skills-pipeline Prometheus scrape (Step 9) | `observability/native/prometheus.yml` | **ACTIVE (target DOWN until orchestrator starts)** | job: skills-pipeline, target: localhost:8006/metrics, step="9". Scrapes cogniforge_pipeline_* metrics. Same process as orchestrator-service:8006 — separate job for step label. |
| 54 | Step 9 CI gate | `.github/workflows/microservices-step9-skills-pipeline.yml` | **ACTIVE** | 7-job workflow: static-checks / prometheus-gate / dashboard-gate / lint / step9-tests (87) / regression-steps-4-8 / pr-summary. Triggers on skills_pipeline.py, prom_metrics.py, routes.py changes. |
| 55 | Postgres Checkpointer (Step 10) | `microservices/orchestrator_service/src/core/database.py:_InstrumentedCheckpointer` | **ACTIVE** | Step 10. `_InstrumentedCheckpointer` يرث من `AsyncPostgresSaver` (subclass لا wrapper — ISS-041). `_make_instrumented_class(AsyncPostgresSaver)` ينشئ subclass يقبله LangGraph. `AsyncConnectionPool` (psycopg, max_size=5). جداول checkpoint موجودة في Postgres. Live: writes=7, reads=3, errors=0. |
| 56 | Checkpointer Prometheus metrics (Step 10) | `microservices/orchestrator_service/src/core/prom_metrics.py` | **ACTIVE** | 6 مقاييس جديدة: `cogniforge_checkpointer_writes_total{thread_id_prefix,status}`, `cogniforge_checkpointer_reads_total{thread_id_prefix,status}`, `cogniforge_checkpointer_duration_seconds{operation}`, `cogniforge_checkpointer_errors_total{error_type}`, `cogniforge_checkpointer_active_threads`, `cogniforge_checkpointer_backend_info{backend,step,pool_size,tables_ready}`. `set_startup_info` أُضيف إليه `checkpointer_backend` label. Live: backend_info{backend="postgres",step="10",tables_ready="true"} 1.0. |
| 57 | /checkpointer/status endpoint (Step 10) | `microservices/orchestrator_service/src/api/routes.py` | **ACTIVE** | `GET /checkpointer/status` → `{"backend":"postgres","step":"10","active":true,"tables_ready":true,"active_threads":1,"pool_size":5}`. Runtime evidence للـ checkpointer. |
| 58 | Grafana dashboard Step 10 | `observability/grafana/dashboards/130-microservices-step10-postgres-checkpointer.json` | **ACTIVE** | 13 panels. UID: cogniforge-ms-step10-checkpointer. Refresh: 10s. Covers: backend info, active threads, writes/reads rate, duration P50/P95/P99, errors by type, health matrix (steps 4-10). |
| 59 | postgres-checkpointer Prometheus scrape (Step 10) | `observability/native/prometheus.yml` | **ACTIVE (target DOWN until orchestrator starts)** | job: postgres-checkpointer, target: localhost:8006/metrics, step="10". Scrapes cogniforge_checkpointer_* metrics. |
| 60 | Step 10 CI gate | `.github/workflows/microservices-step10-postgres-checkpointer.yml` | **ACTIVE** | 7-job workflow: static-checks / routes-gate / infrastructure-gate / lint / step10-tests (101) / regression-steps-4-9 / pr-summary. |
| 55 | config.py service_map port fix | `microservices/orchestrator_service/src/core/config.py` | **FIXED** | planning-agent was mapped to port 8001 (wrong). Fixed to 8002. research-agent: 8007. reasoning-agent: 8008. user-service: 8001. |
| 56 | supervisor.sh CODESPACES + Skills URLs | `.devcontainer/supervisor.sh:launch_orchestrator_service()` | **ACTIVE** | Added CODESPACES=true + PLANNING_AGENT_URL=http://localhost:8002 + RESEARCH_AGENT_URL=http://localhost:8007 + REASONING_AGENT_URL=http://localhost:8008 + USER_SERVICE_URL=http://localhost:8001 to orchestrator launch env. |
| 51 | Grafana dashboard Step 8 | `observability/grafana/dashboards/110-microservices-step8-reasoning-agent.json` | **ACTIVE** | 20+ panels. UID: cogniforge-ms-step8-reasoning-agent. Refresh: 10s. Covers: startup_info, LLM backend, HTTP traffic, invocations (success/error/fallback), MCTS expansions, LLM calls/errors, microservices health matrix (steps 4-8), Prometheus scrape health, activation guide. |
| 52 | Step 8 CI gate | `.github/workflows/microservices-step8-reasoning-agent.yml` | **ACTIVE** | 7-job workflow: static-checks / infrastructure-gate / dashboard-gate / lint / step8-tests (79) / regression-steps-4-7 / pr-summary. PR comment with results. |
| 53 | Ona automation — reasoning-agent | `.ona/automations.yaml` | **ACTIVE** | service: `reasoning-agent` (uvicorn start/ready/stop on :8008). tasks: `verify-step8-reasoning-agent`, `restart-reasoning-agent`, `run-step8-tests`. |
| 15 | Database | `app/core/database.py` | **ACTIVE** | PostgreSQL 17.6 Supabase. database:ok confirmed. |
| 16 | Cache | `app/caching/factory.py` | **ACTIVE (InMemoryCache)** | REDIS_URL not set → InMemoryCache |
| 16b | Cognitive cache | `app/core/cognitive_cache.py` | **ACTIVE (Arabic-aware, D-180)** | `get_cognitive_engine()` → real singleton. `memorize()` on every successful user turn (`simple_client.py`); `recall()` wired as resilience fallback before SafetyNet. Arabic `_normalize` verified live (recall hit ISS-133). Metrics: `cogniforge_cognitive_cache_*`. |
| 17 | AI Gateway | `app/core/gateway/simple_client.py` | **ACTIVE** | nvidia/nemotron-3-super-120b-a12b:free. Live call confirmed. |
| 18 | Microservices stack | `microservices/*/` | **DORMANT** | Not started by devcontainer. Revival Step 1 applied 2026-05-10: H1+H2+H3 unblock orchestrator_service. |
| 19 | Grafana | native binary `/opt/grafana` | **ACTIVE** | Port 3001. 5 dashboards. Datasource connected. |
| 20 | Prometheus | native binary `/opt/prometheus` | **ACTIVE** | Port 9090. 3 targets UP. |
| 21 | OTEL export | `app/telemetry/otel_setup.py` | **ACTIVE (no-op)** | Endpoint set to localhost:4317 but no collector running |
| 22 | UnifiedObservabilityService | `app/telemetry/unified_observability.py` | **ACTIVE** | In-process. Every HTTP request traced. |
| 23 | IntentDetector / ChatOrchestrator | `app/services/chat/intent_detector.py` | **PARTIAL (loaded-not-invoked)** | Constructed by boundary service, never called on WS path |
| 24 | Outbox relay | `orchestrator_service/main.py` | **DORMANT** | OUTBOX_RELAY_ENABLED=False by default |
| 25 | Postgres checkpointer | `orchestrator_service/src/core/database.py` | **DORMANT** | AsyncPostgresSaver importable, not configured |
| 26 | cogniforge_langgraph_checkpointer_writes_total | `observability/grafana/dashboards/20-langgraph.json` | **ZOMBIE metric** | No emitter. Requires Postgres checkpointer. |

---

## Rules (immutable)

1. **Code presence ≠ runtime usage.** Triple proof required: import + call chain + runtime evidence.
2. **No DATABASE_URL = no FastAPI.** A running uvicorn PID is NOT proof of a healthy server. Check `/health`.
3. **Process env wins over `.env`.** `app/core/settings/base.py:23` reads `os.environ` at module import time — before pydantic-settings reads `.env`. Secrets must be in the process environment.
4. **Stale state files are a finding.** `.devcontainer/state/app_healthy` from a previous run does NOT mean the current uvicorn is healthy. Always re-probe the live endpoint.
5. **ACTIVE (no-op) is not ACTIVE.** Missing env var = no observable output = not truly ACTIVE.
6. **Zombie metrics are worse than no metrics.** Always-zero panels are indistinguishable from "system not running". Add emitters or remove the panel (D-016).
7. **Degraded ≠ Dead.** A microservice that passes `/health` but has a failed warmup is DEGRADED. The `/health` endpoint must expose `startup_state`.
8. **Warmup must be timeout-guarded.** Any `ainvoke()` in a lifespan context must use `asyncio.wait_for(..., timeout=N)`.
9. **Supervisor must not trust stale state.** On every boot, re-verify uvicorn is actually serving (PID alive AND port responding).
10. **Grafana :3001 requires process env at boot.** `GF_SERVER_HTTP_PORT=3001` set by supervisor.sh before launching grafana-server.
11. **Orchestrator StateGraph NOT on monolith chat path.** `ChatRoutingPolicy` returns `/agent/chat` → `OrchestratorAgent.run()`, NOT the 12-node StateGraph.
12. **thread_id namespaces incompatible.** Local graph: `str(conversation_id)`. Orchestrator: `f"u{user_id}:c{conversation_id}"`. Never mix.
13. **LangGraph metrics now ACTIVE for local graph.** `cogniforge_langgraph_intent_total`, `cogniforge_langgraph_node_count_total`, `cogniforge_langgraph_node_duration_seconds_bucket` emitted per WS turn.
14. **Lock file staleness is a finding.** Always check `generated_at_utc` in `.runtime/truth_table.lock.json` before trusting it.
15. **`allowedDevOrigins` must include all hosting environments.** Next.js 15+ rejects dev-server requests from unlisted origins. Always include `*.app.github.dev` (Codespaces), `*.replit.dev` (Replit), and `*.gitpod.io` (Gitpod/Ona) in `frontend/next.config.js`.
16. **`local` is illegal outside bash functions.** Using `local var` in top-level script scope (even inside `if/else`) causes bash to abort with `local: can only be used in a function`. In `supervisor.sh`, any variable at top-level must use plain assignment (`var=value`). This was the root cause of ISS-037 (commit `3fd78247`) — all ports dead after merge.
17. **`.devcontainer/secrets.env` is the Codespaces fallback.** When Codespaces Secrets are not configured, `supervisor.sh` reads `.devcontainer/secrets.env` (git-ignored) before falling back to SQLite. Copy `.devcontainer/secrets.env.example` and fill in real values. Never commit `secrets.env`.
19. **`cognitive_engine` حارس None دفاعي فقط (مُصحَّح D-180 — 2026-07-22).** الادّعاء القديم «`get_cognitive_engine()` يُرجع `None` دائماً» **كان خاطئاً** — يُرجع نسخة حقيقية من `CognitiveResonanceEngine` (`cognitive_cache.py`). الحارس `if self.cognitive_engine is not None` يبقى كـ**كود دفاعي** (قد يحقن اختبار/DI قيمة `None`) — لا تُزِله. المحرك الآن ACTIVE عربيّ-أولاً: `memorize()` يخزّن كل دور مستخدم ناجح، و`recall()` مُوصَّل كطبقة صمود في البوّابة (D-180 / ISS-133).
20. **`postgresql://` يُفشل `create_async_engine` — يجب `postgresql+asyncpg://` (ISS-038-B — مكتشف حياً 2026-05-10).** `DATABASE_URL` من Supabase يستخدم `postgresql://` الذي يُعيَّن إلى psycopg2 المتزامن. `create_async_engine` يرفعه بـ `InvalidRequestError`. الإصلاح في `supervisor.sh` و `automations.yaml`: تحويل inline بـ bash substitution + إزالة `sslmode` من query string (asyncpg يتعامل مع SSL عبر `connect_args`). **القاعدة:** أي microservice يستخدم SQLAlchemy async يجب أن يستقبل `postgresql+asyncpg://` وليس `postgresql://`.
21. **orchestrator-service يبدأ في وضع `degraded` مع `graph_ready:true` — هذا طبيعي.** `startup_state: degraded` يعني warmup probe فشل بسبب PgBouncer prepared statement conflict (`prepared statement "_pg3_0" already exists`). لكن `graph_ready: true` يعني الـ StateGraph 12 عقدة يعمل. الخدمة تستجيب وتعالج الطلبات. هذا سلوك متوقع مع PgBouncer transaction mode — ليس خطأً مميتاً.
23. **planning-agent يعمل في وضع fallback بدون OPENROUTER_API_KEY.** `_dspy_dependencies_available()` تتحقق من DSPy قبل التهيئة. عند غياب المفتاح أو فشل DSPy، `_get_fallback_plan()` تُولِّد خطة احتياطية بدلاً من رفع استثناء. `cogniforge_planning_fallback_plans_total{reason=...}` يُسجِّل السبب. هذا سلوك مقصود — الخدمة لا تتعطل بدون DSPy.
24. **docker-compose.step6.yml مخصص لبيئات Docker فقط.** في Codespaces: `supervisor.sh:launch_planning_agent()` هو المسار الوحيد. `docker-compose.step6.yml` للتطوير المحلي وCI فقط. لا تحاول تشغيل Docker Compose في Codespaces devcontainer — Docker-in-Docker غير مدعوم.
25. **PLANNING_* env vars prefix.** `PlanningAgentSettings` تستخدم `env_prefix="PLANNING_"`. لذا `OPENROUTER_API_KEY` في البيئة يُقرأ كـ `PLANNING_OPENROUTER_API_KEY`. في supervisor.sh: `PLANNING_OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}"` يُحوِّل المفتاح العام إلى المتغير المُقيَّد بالـ prefix.
20. **`TAVILY_API_KEY` يجب أن يكون في `docker-compose.yml` لكلا الخدمتين (H1 — 2026-05-10).** `WebSearchFallbackNode` في `orchestrator_service` و`SuperSearchOrchestrator` في `research_agent` تتجاهلان البحث صامتتين عند غياب المفتاح. القيمة الآمنة: `${TAVILY_API_KEY:-}`.
21. **`ddgs>=6.0` مطلوب في `research_agent/requirements.txt` (H2 — 2026-05-10).** بدونه، `SuperSearchOrchestrator` ترفع `ImportError` عند غياب `TAVILY_API_KEY` — وهو الوضع الافتراضي في بيئة التطوير.
18. **Exercise retrieval requires intent classification, not keyword matching (ISS-038).** `detect_exercise_retrieval()` must use a two-phase classifier: (1) explanation-intent patterns cancel retrieval at highest priority; (2) only explicit retrieval patterns trigger it. A flat keyword list on "تمرين"/"احتمالات" causes context blindness — every explanation request returns the same static knowledge-base file. When in doubt, do NOT trigger retrieval; LangGraph handles ambiguous questions better. The `knowledge_base/` directory currently contains exactly one file — any retrieval trigger without explicit context returns that file unconditionally.
22. **`ORCHESTRATOR_CHAT_ENDPOINT` controls routing target (Step 2 — 2026-05-10).** Default: `"state_graph"` → `/api/chat/messages` (StateGraph 12 nodes). Rollback: `"agent"` → `/agent/chat` (OrchestratorAgent). Unknown values fall back to `"state_graph"` with a warning. Do NOT change the default without an ADR (D-021).
23. **Routing metrics are emitted per chat request.** `cogniforge_routing_mode_state_graph` (gauge: 1=StateGraph, 0=Agent) and `cogniforge_routing_target_total{target=...}` (counter) are emitted by `orchestrator_client.py` on every `chat_with_agent` call. These feed the `50-microservices-transition.json` dashboard on Grafana :3001.
24. **Microservices Prometheus targets are DOWN by default.** `orchestrator-service`, `research-agent`, `user-service`, `planning-agent` scrape targets added to `prometheus.yml`. They show as DOWN until `docker compose -f docker-compose.yml up -d` is run. DOWN is the expected state in the default devcontainer — it is not an error.
25. **Grafana :3001 has 6 dashboards after Step 2.** `50-microservices-transition.json` (UID: `cogniforge-ms-transition-step2`) added. 15 panels covering routing mode, StateGraph execution, Tavily, microservices health matrix, and fallback chain transition progress.
26. **Grafana :3001 has 7 dashboards after Step 3.** `60-microservices-step3-live.json` (UID: `cogniforge-ms-step3-live`) added. 20 panels, 10s refresh. Covers orchestrator health, routing distribution, LangGraph node execution, intent classification, fallback chain progress, memory/CPU, and activation guide.
27. **docker-compose.step3.yml is the Step 3 activation file.** Runs only 3 services: `postgres-orchestrator` (5441), `redis-orchestrator` (6380), `orchestrator-service` (8006). Isolated from the main `docker-compose.yml`. Use `docker compose -f docker-compose.step3.yml up -d` to activate. Volumes are named `cogniforge-postgres-orchestrator-step3-data` to avoid conflicts.
28. **Ona automation `orchestrator-stack` is the canonical Step 3 trigger.** `gitpod automations service start orchestrator-stack` → builds + starts the 3-service stack → waits for `/health` → reports LIVE. `ready` command: `curl -sf http://localhost:8006/health`. Stop: `docker compose -f docker-compose.step3.yml down`.
29. **Step 3 CI gate has 7 jobs.** `.github/workflows/microservices-step3-live.yml` validates: compose syntax + required services + port assignments + StateGraph imports + /health structure + asyncio.wait_for guard + dashboard JSON (20 panels, correct UID) + Prometheus orchestrator-service job + automations.yaml schema (no `dependsOn` in services). PR comment posted automatically.
30. **`OUTBOX_RELAY_ENABLED=false` in Step 3.** Disabled in both `docker-compose.step3.yml` and `supervisor.sh:launch_orchestrator_service()`. Enabled in Step 4 after verifying the full persistence path (D-006 compliance check).
31. **Docker is NOT available in the default Codespaces devcontainer.** `devcontainer.json` intentionally omits `docker-in-docker` (fails on `python:3.12-slim` + `network_mode: host`). `docker-compose.step3.yml` is for local/CI environments only. In Codespaces, `supervisor.sh:launch_orchestrator_service()` is the canonical Step 3 activation path.
32. **orchestrator-service auto-starts at Codespace boot when `OPENROUTER_API_KEY` is set.** `supervisor.sh` STEP 4D calls `launch_orchestrator_service()` in background. If `OPENROUTER_API_KEY` is absent, it logs a warning and skips — no crash. Add the key to Gitpod Secrets to activate automatically.
33. **`ORCHESTRATOR_DATABASE_URL` defaults to `DATABASE_URL` in Codespaces.** The orchestrator uses Supabase (same DB as monolith) with a separate schema. No local postgres needed. This is intentional for Step 3 — Step 4 may introduce a dedicated schema or separate DB.
34. **native/prometheus.yml is the real Prometheus config in Codespaces.** `observability/prometheus/prometheus.yml` is used by Docker compose stack only. `observability/native/prometheus.yml` is what the native Prometheus binary reads (launched by supervisor.sh). Always edit `native/prometheus.yml` for Codespaces scrape targets.

## Update 2026-05-20 — BKT Cognitive Layer + Abstraction Ban (D-074, Protocol V6.0)

35. **`student_bkt_analytics` table is ACTIVE — append-only.** Registered in `app/core/db_schema_config.py` (`_ALLOWED_TABLES` + `REQUIRED_SCHEMA`); auto-created on boot via `app/kernel.py:233 → validate_schema_on_startup()`. Each student interaction inserts ONE row (never upsert). Prior mastery read from the latest row per `(user_id, concept_id)`. Schema: `concept_id`, `cognitive_load_estimate` (low/medium/high), `student_mastery_probability ∈ [0,1]`, `interaction_timestamp`.
36. **`BKTEngine` (`app/services/skills/bkt_engine.py`) is ACTIVE — deterministic.** import + call chain (`customer_chat._evaluate_and_emit_bkt → BKTAnalyticsService.evaluate_and_record → BKTEngine.evaluate`) + runtime evidence (Prometheus `cogniforge_skill_bkt_*`, DB rows). It is the foundational cognitive layer for all future adaptive pedagogical skills. Consumes `BKT_COGNITIVE_DOCTRINE` (v1.0.0).
37. **Abstraction Ban is ACTIVE.** `OrchestratorClient._build_probability_tree_props` (hybrid: deterministic `_extract_concrete_events` → LLM `_enrich_tree_labels_with_llm` → concrete generic fallback) guarantees no `A`/`B|A`/`Ā` reaches any generative-UI node. Verified live (deterministic path + OpenRouter reachable; free model 429 → concrete fallback).
38. **`bkt_hint_display` frontend portal is PARTIAL (STUB).** The `bkt_tracking` payload flows end-to-end (emit → contract `BKTTrackingPayload` → `useAgentSocket` → `GenerativeUIRenderer`) and is persisted, BUT `GenerativeUIRenderer.jsx` renders `bkt_hint_display` via `BktHintStub` (fallback-text info-note only). The rich BKT visualization is NOT built yet. `probability_tree` → `ProbabilityTree.jsx` IS fully built. Do not claim the BKT visual portal is ACTIVE — it is a stub.
39. **Codespaces firewall blocks Postgres egress (6543/5432).** Live Supabase row-insert proof cannot run from the agent sandbox (HTTPS/443 open, Postgres blocked). The boot auto-creation mechanism is the canonical schema path; `scripts/verify_bkt_live.py` runs the live proof inside Codespaces where egress is open.

40. **Live DB RAG Readiness:** The live Supabase instance has been verified to contain strict JSONB `parsed_entities` and vector embeddings for 3 distinct BAC exercises: 2024 Probability, 2024 Complex Numbers, and 2016 Numerical Functions. Local fallback gracefully reads from `knowledge_base/` but production RAG queries successfully slice between these exercises using `topic` and `exam_ref` to avoid semantic blindness (Bug B).

## Update 2026-07-04 — Honest Mastery Engine (D-157, Phase A · ISS-123)

41. **Three-state correctness signal is ACTIVE (import + call chain).** `bkt_engine.infer_correctness_signal_3state` + `update_mastery_3state` — UNKNOWN carries prior unchanged (fixes the default-`False` downward bias). Call chain: `BKTEngine.evaluate → update_mastery_3state`. Runtime evidence (mastery no longer depressed on neutral turns) pending Codespaces live WS. Backward-compat `infer_correctness_signal` (bool) retained.
42. **Continuous forgetting-curve durable channel is ACTIVE (import + call chain).** `bkt_engine.durable_update_continuous` (+ `half_life_days`, `predicted_recall`) replaces the strict binary gate (removed `_DURABLE_UNAIDED_LEVEL`/`_DURABLE_MIN_DELAY_HOURS`/…). Called from `bkt_persistence.evaluate_and_record`. Anti-illusion invariant proven in `test_d126_two_signal_bkt.py` (support=1 gain ≈ 1/10 of support=5). Runtime evidence (durable actually rising on unaided-delayed evidence) pending Codespaces live — durable can only rise once the M8 mechanism (Phase B) generates unaided-delayed evidence; within a single session it stays low (correct by design).
43. **Symbolic-verified evidence override (A1b) is ACTIVE (import + call chain).** `customer_chat._derive_correctness_override` reuses the deterministic D-155 oracle (`OrchestratorClient._verify_numeric_answer`/`_verify_answer_against_combo`/`_load_canonical_combinations`) to authoritatively mark a probability answer CORRECT (high-precision; never marks INCORRECT). fail-open. Threaded `customer_chat → bkt_persistence → BKTEngine.evaluate`.
44. **BKT ordering fix (A2): `_bkt_task` now created AFTER `support_level`.** Was launched at the old `customer_chat.py:953` before `_build_pedagogy_directive` computed `support_level` ⇒ durable frozen. Now created right after `support_level = pedagogy_snapshot.support_level`, still a background task (D-WS-FLAP-001), and it also removes a prior read/write race (pedagogy reads the true prior before this turn's write). `novel_item` derived from `prior_count == 0`.
45. **M9 illusion-gap metrics are ACTIVE (emitter present, scrape pending live).** `tutor_metrics.record_illusion_gap`/`record_mastery_channels`/`record_durable_rise` emit `cogniforge_tutor_illusion_gap` + `_assisted_mastery` + `_durable_mastery` (Histograms) + `_durable_rise_total{cause}`, called from `bkt_persistence.evaluate_and_record` (fail-open). Same `prometheus_client` default-registry path as the existing `cogniforge_tutor_*` counters. Grafana dashboard `observability/grafana/dashboards/180-illusion-gap.json` (UID `cogniforge-illusion-gap`, valid JSON). Runtime evidence (panels populate) pending Codespaces live traffic.
46. **`BKT_COGNITIVE_DOCTRINE` bumped v2.0.0 → v3.0.0.** Reflects the continuous forgetting curve + three-state signal + M9 emission. `check_bkt_baseline_integrated` gate still passes (checks doctrine consumption + `_evaluate_bkt_cards` wiring + `await _bkt_task` — all intact). Note: the doctrine/skills gate cannot run in the agent sandbox (no `pydantic`) — verified in CI/Codespaces.
47. **Sandbox limits (unchanged):** the honest-mastery LOGIC is proven standalone (32 tests, ALL PASS) but live WS + Supabase row-writes + Prometheus scrape require Codespaces (Postgres 6543/5432 + pydantic + prometheus scrape blocked in sandbox — §6.55). Phase A is ACTIVE-by-wiring; full runtime proof is the Codespaces gate.
48. **D-158 — `tutor_state` persistence was DEAD on prod, now FIXED (verified live via bridge).** Root: the 7 D-144 columns were missing on the live table (auto_fix ALTERs mis-filed under `bac_exercise_questions`, not `tutor_state`; `create_table` is `IF NOT EXISTS`) ⇒ every `record_turn` write failed silently (live: 2 rows, last write 2026-06-26 — D-142→D-157 never persisted). Fixed: ALTERs moved to `tutor_state.auto_fix` in `db_schema_config.py` + applied live via `scripts/db_bridge.py` (HTTPS:443) → `tutor_state` 12→19 columns confirmed. `kc_progress` now WRITTEN (`record_turn(kc_progress=...)` deep-merge; was loaded-never-written — the mechanical reason skills fell back to transcript scanning).
49. **D-158 — Cognitive Turn Engine is ACTIVE-by-wiring, flag-gated OFF.** `orchestrator_client._cognitive_turn` (deterministic, zero-LLM, fail-open) is the single turn-decision layer over persisted `kc_progress`; wired in `chat_with_agent` behind `COGNITIVE_TURN_ENABLED` (default False → today's behavior unchanged). Decision logic proven on the **real method source** by `scripts/verify_d158_live.py` (6/6: S3 probe-not-dump, S1 single progressive step, S2 correct-answer confirmed after a 1536-char prior message = 600-char prison broken, no step repeated). `semantic_tutor` flag unified in `app/core/feature_flags.py` (single default True). Full WS+Supabase runtime proof with the flag ON is the Codespaces gate.
50. **Docker full-stack (docker-compose.yml) — REPRODUCIBLE + R0.1/R0.2 CLOSED (D-172, verified live 2026-07-19).** `docker compose up --build` boots the microservices stack with real local Postgres/Redis + Prometheus/Grafana (self-creating network, auto secret bridge). `scripts/verify_full_stack_docker.py` = 16/16: orchestrator `checkpointer_backend=postgres` (AsyncPostgresSaver ACTIVE, 4 checkpoint tables in PG), planning `database=postgresql`, reasoning `llm_backend=openrouter`, `/compose` real 1370-char answer, Prometheus targets UP, Grafana db=ok. Fail-loud health guards (production-gated) proven — orchestrator reported `degraded` not false `ok` before the fixes. **Sandbox limit:** 5 torch-heavy/deeper-defect services (memory/user/observability/research/conversation) excluded from the 30GB sandbox proof (build in Codespaces/CI; not on the /compose path). The self-contained Docker stack uses LOCAL Postgres — NOT Supabase (that remains the live monolith path, §6.55).
51. **D-174 — the "ZOMBIE" drivers/council are import-live behind a flag; NOT freely deletable.** `.runtime/truth_table.lock.json` classifies `app/drivers/llamaindex_driver.py`, `app/drivers/reranker_driver.py`, and `app/services/chat/agents/education_council.py` as ZOMBIE (never invoked at *runtime*). That label is about runtime invocation, NOT the import graph: the two drivers are the backing of `RetrievalRerankSkill` (lazy imports inside its methods; re-exported by `app/drivers/__init__.py`; registered in `app/services/skills/registry.py`; served by the live `/api/v1/skills` router — behind `ENABLE_RETRIEVAL_RERANK_SKILL`), and `education_council.py` is imported by `app/services/chat/agents/orchestrator.py` (used by 4 tests). Deleting any of them breaks imports (monolith startup + tests) and removes the documented RAG/Reranker extension seam (`docs/architecture/EXTENSION_SEAMS.md` §4). Decision: **keep as extension seams, promote via the three-leg proof — do not delete.** The lock classifications are unchanged (still accurate as *runtime* status; `runtime_truth.py --check` passes); only this clarifying note was added. Live-path entrypoints unchanged: `app/api/routers/customer_chat.py`, `app/api/routers/admin.py`, `app/services/chat/local_graph.py`, `app/infrastructure/clients/orchestrator_client.py`, `app/kernel.py`, `_emit_terminal_frames`.
