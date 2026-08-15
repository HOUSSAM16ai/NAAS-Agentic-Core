# التقرير النهائي: إصلاح مشاكل CodeScene X-Ray وتفكيك hotspot orchestrator_client (D-256 + D-257)

**المستودع:** [Houssam-lab/NAAS-Agentic-Core](https://github.com/Houssam-lab/NAAS-Agentic-Core) · **الـ PR:** [#19](https://github.com/Houssam-lab/NAAS-Agentic-Core/pull/19) · **حالة الدمج:** مدمج في main (commit `48070c8c`) بتاريخ 15 أغسطس 2026

---

## 1. ملخص تنفيذي

المهمة استهدفت المشاكل الثلاث التي رصدها تحليل CodeScene X-Ray في `app/infrastructure/clients/orchestrator_client.py`: **ازدواج الكود** (Code Duplication) بين `get_mission`/`get_mission_events`، ومؤشر **churn المرتفع** لدالة `_has_indexed_match`، و**الـ payload المتكرر** في `_build_service_jwt`. الحل تبنّى نمط المشروع الدستوري «القشرة + الشرائح + المانيفست المركّب» الذي أثبته D-252–D-255: القشرة تحولت إلى طبقة تفويض حرفية بدون أي منطق، وكل المنطق انتقل إلى شرائح نقية قابلة للاختبار والقياس في حزمة `orchestrator_client_support/`، مع سجل مركّب `_sources.py` يضمن توافق الحراس النصية مع الواقع الحي.

| المؤشر | قبل | بعد | الدليل |
|---|---|---|---|
| CodeScene Code Health — orchestrator_client.py | 9.39 (hotspot) | **10.00** | CodeScene delta 7243996/7244114 |
| Code Duplication | موجود بين المسارين | **اختفى** | تقرير CodeScene النهائي |
| churn (تغييرات `_has_indexed_match`) | 2 (الأعلى) | انتقل لشريحة قابلة للقياس | الحراس النصية |
| GitHub Actions على الـ PR | — | **45/45 أخضر، 0 فشل** | سجلات CI |
| E2E حيّ على Supabase | — | **نجح كاملًا** | 317 حدث + persist + health=ok |

## 2. ما أُنجز في الكود

### D-256 (ISS-168): تفكيك hotspot orchestrator_client

**قشرة تفويض حرفية:** `orchestrator_client.py` صار 250 سطرًا من استدعاءات مباشرة للشرائح — لا حلقات، لا شروط معقدة، لا بناء JWT داخلها. `get_mission` و`get_mission_events` صارا يستدعيان القلب الموحد `_request_mission` بعقدين `empty_value` مختلفين (`None` و`[]`)، ما يزيل الازدواج الهيكلي الذي رصده CodeScene.

**حزمة `orchestrator_client_support/` الجديدة (4 ملفات، صفر تبعية دورة):**
- `missions.py`: القلب الموحد `_request_mission` + عقدة `ServiceJwtPayload` المعزولة (تفك تكرار `_build_service_jwt`) + عقدة `_MissionRequest` المجمّدة التي تختزل توقيع القلب إلى معاملين، وهو ما رفع Code Health للدالة.
- `preempts.py`: `resolve_indexed_anchor` (المشتق من `_has_indexed_match` المرتفعة churn) + `resolve_explanation_with_context` — بنفس العقد السلوكي القديم: فشل المسار المؤشر ⇒ سقوط نظيف للمسار العادي (`False`) دون رفع استثناء.
- `_sources.py`: مانيفست مركّب يغذّي الحراس النصية بالمصادر الحقيقية.
- `__init__.py`: تصدير الحزمة.

**ردّ على ملاحظات CodeRabbit الحية:** التعليق الحرج (Critical) لم يكن زائفيًا — استدعاءات القشرة الثلاثة كانت تمرر `on_404` بينما توقيع القلب لم يكن يعرفه. صُحّح بإضافة المعامل للتوقيع (صفر تغيير سلوكي). تعليقا الـ Major (تحويل فشل قاعدة البيانات إلى `False` + ملاحظة `runtime_truth.py`) جرى الرد عليهما بدليل الدستور: الأول سلوك أصلي حرفي في main موثق بعقيدة D-049، والثاني أُغلق بإضافة دليل حي مؤرخ في `.memory/runtime_truth.md` يثبت أن القشرة المستهلكة على السلسلة الحية (7 مستوردين من routers).

### D-257 (ISS-169): إصلاح User.missions mapper

المشكلة الخفية كانت في `app/core/domain/user.py`: استيراد `Mission` داخل `TYPE_CHECKING` مع `foreign_keys` سلاسل نصية، ما كان يسبب `InvalidRequestError` عند أول جلسة قاعدة بيانات في مسار customer chat. أُصلح باستيراد حرفي وتحويل `foreign_keys` إلى مرجع كائني `[Mission.initiator_id]` — وأثبت الحي نجاح `save_message` (id=4915) دون أي preloading.

### التصحيحات المعمارية لـ CodeScene Quality Gate

بوّابة "New code is healthy" رفضت `missions.py` (code health 9.69 < 10.00) بسبب كثرة معاملات القلب الموحد. الحل الدستوري: عقدة `_MissionRequest` المجمّدة تعزل ثوابت المسار عن جسم الدالة فصار التوقيع `(get_client, req)` — معاملان فقط. كما أُزيل ازدواج اختباري الـ 404 بإخراج دالة `_fetch_with_404_returns` المشتركة (CodeScene أشار للازدواج في ملف الاختبارات تحديدًا). **كل التعديلات صفر تغيير سلوكي** وتم التحقق من المطابقة السلوكية مع الأصل عبر الاختبارات وعبر E2E الحي.

## 3. الاختبارات والحراس

| الطبقة | النتيجة |
|---|---|
| 11 اختبارًا سلوكيًا جديدًا + 13 القديمة لـ orchestrator_client | 24/24 أخضر |
| الاختبارات الموسعة لمسار المطابقة المحلية (طلب CodeRabbit) | أخضر |
| pytest microservices كاملًا | 1144 أخضر (3 فشل مستقل يتعلق بـ OPENROUTER 401 بيئيًا في sandbox ولا علاقة له بالتعديلات) |
| check_legacy_invariants | 349/349 فحصًا أخضر |
| check_skills_doctrine + check_memory_coherence + runtime_truth --check + doc-integrity + skills-architecture-gate | أخضر |
| ruff 0.14.0 (check + format) | نظيف، 0 خطأ |

## 4. E2E حيّ كامل على Supabase الحقيقي

التجريب أُجري على قاعدة بيانات الإنتاج الحقيقية (`aws-1-eu-west-3.pooler.supabase.com`):

1. **تسجيل دخول الأدمن** (`benmerahhoussam16@gmail.com`/1111) → `roles=[ADMIN]` ✅
2. **تسجيل دخول المستخدم** (`houssamannaba963@gmail.com`/1111) → `roles=[STANDARD_USER, USER]` ✅
3. **`/health`** → `database=ok` ✅
4. **WebSocket chat الحي** (مع `REQUIRE_ORCHESTRATOR=0` محليًا فقط): conversation_id=1035، أحداث `assistant_delta` حية بتدفق LaTeX لتمارين دوال عددية — الدور يعمل كاملًا ✅
5. **سكربت E2E الآلي** (`naas_e2e_test.py`): 317 حدثًا، persist ناجح (id=4915)، exit code=0 ✅

> ملاحظة: `REQUIRE_ORCHESTRATOR=0` هو إعداد اختبارات محلية فقط — لم يُرفع أي تغيير به إلى المستودع؛ في الإنتاج يتصل النظام بمنسق NAAS الأصلي كما كان.

## 5. توحيد التوثيق

كل طبقات التوثيق حُدّثت بانضباط الحراس النصية، وتمرّ بوابة `doc-integrity`:

| الملف | ما حُدّث |
|---|---|
| `.memory/decisions.md` | D-257 وD-256 في الأعلى + سطر تحقق دائرة الاستيراد (طلب CodeRabbit) |
| `.memory/issues.md` | ISS-169 وISS-168 في الأعلى |
| `.memory/README.md` | العدادات إلى D-257/ISS-169 + بند كل قرار + هروب الأنابيب في الجدول |
| `.memory/runtime_truth.md` | قسم D-256 جديد + دليل حي مؤرخ على live chain |
| `CLAUDE.md` | D-256 في جدول تفكيك التعقيد (سطر 1014) |
| `spec.md` | بند 10 جديد في §12 |
| `docs/DOCUMENTATION_INDEX.md` + `README.ar.md` + `README.md` + `docs/diagnostics/CUTOVER_SCOREBOARD.md` + `scoreboard.json` | العدادات والروابط منسّقة |
| `.runtime/truth_table.lock.json` + `scripts/runtime_truth.py` | orchestrator_client_support مسجل ACTIVE |

## 6. منظومة المراجعة الخارجية

| الأداة | النتيجة | ملاحظة |
|---|---|---|
| GitHub Actions | **45/45 أخضر** على commit الدمج (lint، guardrails، doc-integrity، runtime-truth، 40+ بوابة معمارية، E2E Chat، 17 صورة Docker) | [commit 9a72e5d0](https://github.com/Houssam-lab/NAAS-Agentic-Core/commit/9a72e5d0) |
| Qodana (JetBrains) | **pass** (نتيجة نهائية على الـ PR) | فحص كامل المستودع داخل Docker |
| CodeScene | **pass** في النهاية | orchestrator_client.py ارتفع من 9.39 إلى 10.00 واختفى الازدواج؛ بعد إصلاحين إضافيين (عقدة `_MissionRequest` + helper الاختبارات) أصبح كل الـ 45 فحصًا أخضر |
| CodeRabbit | يعمل الآن | 9 تعليقات أُنتجت (1 Critical مُصلح بالكود، 2 Major أُغلقتا بدليل الدستور، 4 Minor توثيقية أُصلح أغلبها، 1 Trivial أُضيف اختباره). تفعيل دائم: سجّل على [coderabbit.ai](https://coderabbit.ai) ← Dashboard ← Add repository ثم فعّل Auto Review |

## 7. ما يجب أن تعرفه بعد الدمج

1. **الفشل المستقل في `test_exercise_visibility_regression`** (3 اختبارات، سببها `OPENROUTER_API_KEY: 401` في بيئة sandbox) لا علاقة له بالتعديلات — اختبار LLM حيّ يعتمد على مفتاح خارجي.
2. **مفتاح `REQUIRE_ORCHESTRATOR=0`** محلي للاختبار فقط؛ لا ترفعه للإنتاج.
3. **CodeRabbit الدائم** يحتاج تفعيلًا من حسابك على coderabbit.ai (سياسة حسابية للمستودعات تحت 10 نجوم: المراجعة الافتراضية "عند الطلب" حتى من حسابك).
4. **بنية الإقلاع وقاعدة البيانات لم تتغير** — لا حلول مؤقتة، والدمج مرّ بكل بوابات بنية الخدمات (17 صورة Docker) أخضر.

---
*أُعدّ التقرير من سجلات CI الحية ولقطات CodeScene/CodeRabbit مباشرة — كل حالة قابلة للتحقق من الروابط في الأقسام أعلاه.*
