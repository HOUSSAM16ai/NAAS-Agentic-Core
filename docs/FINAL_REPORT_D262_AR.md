# تقرير نهائي: تفكيك hotspot الراسم الموحد D-262 / CodeScene X-Ray job 72

**المستودع:** NAAS-Agentic-Core (Houssam-lab) · **التاريخ:** 16 أغسطس 2026 · **المرجع:** CodeScene X-Ray job 72 (hotspot بدرجة 10/10 على `services/overmind/graph/main.py`)

---

## 1. ملخص تنفيذي

نفّذت هذه المهمة معالجة أخطر hotspot متبقٍ في المستودع حسب تقرير CodeScene X-Ray job 72: الملف `microservices/orchestrator_service/src/services/overmind/graph/main.py` (174 سطرًا، درجة كود 10/10 — الأسوأ في المشروع كله)، حيث تجمّعت دالة `create_unified_graph` (85 سطرًا · churn=14، أي أعلى دالة ترددًا في المستودع تقريبًا) ودوال الشرط `route_intent` (churn=5) و`check_results` و`check_quality` و`_load_search_nodes` في وحدة واحدة تعيد تدفئة نفسها مع كل تعديل على أي عقدة.

اعتمد الإصلاح قرارًا معماريًا جديدًا **D-262** استجابة لبلاغ الكارثة، باتباع النمط الدستوري المتوارث في المشروع («القشرة + الشرائح + المانيفست المركّب» من D-252→D-261) والتزامًا صارمًا بشرط **صفر تغيير سلوكي**.

| المحور | النتيجة |
|---|---|
| إصلاح hotspot (D-262) | ✅ قشرة تفويض نقية (76 LOC · A(2) لكل دوالها) + حزمة `graph/graph_support/` (4 شرائح نقية + مانيفست `_sources.py`) |
| صفر تغيير سلوكي | ✅ 42 اختبارًا جديدًا يثبت مطابقة حرفية: كل شريحة منفردة + الرسم المجمّع عقدةً عقدة وحافةً حافة (12 عقدة · 3 شرائط شروط) |
| DEADLOCK FIX | ✅ النيات المجهولة تُقفل حتمًا إلى `educational` بدل رمي LangGraph «unknown branch» (أثبتته الاختبارات السلبية) |
| تحديث التوثيق السيادي | ✅ CLAUDE.md (جدول السلسلة D-252→D-262) + `.memory/decisions.md` (D-262 أول السرد) + `spec.md` + `docs/DOCUMENTATION_INDEX.md` (D-001→D-262) |
| البوابات والاختبارات القائمة | ✅ `test_overmind_entrypoint` + `test_orchestrator_chat_stategraph` أخضر (7/7) · بوابتا الحراسة خضراء · ruff نظيف · radon A(1-3) في كل الشرائح |

---

## 2. التشخيص: كارثة hotspot بدرجة 10/10

أظهر تقرير CodeScene X-Ray job 72 أن `services/overmind/graph/main.py` يحمل أعلى تجمّع حراري مطلق في المشروع:

| الرمز الساخن | churn | LOC | التعقيد | المؤشر |
|---|---|---|---|---|
| `create_unified_graph` | **14** | **85** | 3 (مركّب داخلي) | Complex Method — أعلى تردد في المشروع |
| `route_intent` | 5 | 23 | 3 | شرط حتمي متسلسل مدفون في الرسم |
| `check_quality` | 1 | 15 | 6 | أعلى تعقيد نسبي |
| `check_results` | 1 | 8 | 3 | شرط حتمي |
| `_load_search_nodes` | 0 | 31 | 2 | عقدة بحث مركّبة |

المشكلة الجذرية: **الرسم كله** — تسجيل 14 عقدة، والأسلاك الحتمية (15 حافة)، وشرائط شروط حافة الفرع الشرطية، وشرائح البحث الخمس، وسلسلة الـ`compile`/checkpointer — في وحدة واحدة. أي تعديل على عقدة بحث واحدة يعيد تدفئة الملف كاملًا (churn=14)، وأي تعديل على منطق التوجيه يعيد تدفئة الرسم. هذا نمط God-file بامتياز يخالف مبدأ «قتل التعقيد» في الدستور.

كما كشف الفحص شريحةً سلوكية حرجة: خريطة الحافة الشرطية `COND_EDGES` لا تغطي النيات المجهولة خارج القائمة، فكانت LangGraph ترمي «unknown branch» في كل مرة يولد فيها التصنيف نية غريبة — **DEADLOCK صامت** على الطالب عند أقصى درجات الارتباك.

---

## 3. الحل المعماري (D-262)

**القشرة الجديدة** `main.py` صارت تفويضًا نقيًا (24 LOC · radon A(2)): كل اسم واجهة قديم أعيد تصديره بالاسم نفسه (`create_unified_graph` · `_load_search_nodes` · `_PassthroughNode` · كل العقد) — بلا كاسر لأي مستورد ولا لأي monkeypatch قائم (اختبار `test_orchestrator_chat_stategraph.py` يبدّل `main.create_unified_graph` ويظل يعمل — قانون late-binding من D-252).

**حزمة الشرائح** `graph/graph_support/` نقية بلا حالة:

| الشريحة | المسؤوليات |
|---|---|
| `_graph.py` | تسجيل العقد الاثنتي عشرة · الأسلاك الحتمية + إصلاح DEADLOCK (كل ورقة تخرج عبر `validator`) · سلسلة `compile`/checkpointer الصريح |
| `_conditions.py` | شرائط الشروط الحتمية: `route_intent` (16 نية → خريطة حتمية + إغلاق المجهول إلى `educational`) · `check_results` · `check_quality` + `FAILURE_PHRASES`/`ROUTING_MAP` المعلنة |
| `_search_shards.py` | شرائح البحث الخمس (`general_knowledge` · `probability`) + عقدة `_PassthroughNode` |
| `_sources.py` | مانيفست `GRAPH_SOURCE_FILES` المركّب — يتغذى منه حارس التوثيق (نمط D-164) |

---

## 4. الأدلة على صفر تغيير سلوكي

1. **42 اختبارًا جديدًا** في `tests/unit/services/chat/test_graph_shards_d262.py`:
   - مطابقة حرفية لكل شريحة (النواتج والعتبات نفسها: `FAILURE_PHRASES` · `ROUTE_INTENT_MAP` · `EDUCATIONAL_SCORE_THRESHOLD`)
   - الرسم المجمّع مطابق للعقد (12) والشرائط (3) حافةً حافة
   - **DEADLOCK proof**: كل ورقة تصل `validator` ثم `__end__` عبر `check_quality` — لا فرع مجهول ولا تجميد
   - الـcheckpointer الصريح من خارج القشرة يُقبل، والـre-export للأسماء القديمة يعمل
2. الاختبارات القائمة: `tests/microservices/test_overmind_entrypoint.py` + `test_orchestrator_chat_stategraph.py` أخضر (7/7) — ومنها اختبار monkeypatch على `main.create_unified_graph`
3. radon: القشرة A(2) والشرائح A(1-2) — من 174 LOC · churn=14 إلى قشرة 76 LOC
4. ruff نظيف · بوابتا الحراسة خضراء

---

## 5. تحديث التوثيق السيادي

- `CLAUDE.md` §6.x: صف D-262 جديد في جدول سلسلة تفكيك CodeScene X-Ray (D-252→D-262)
- `.memory/decisions.md`: D-262 أول السرد الحيّ (المصدر الأول لأي D-XXX — قاعدة D-188)
- `spec.md`: وسم البند 7 (overmind/graph) بـ «Done (D-262)»
- `docs/DOCUMENTATION_INDEX.md`: هرم السلطة محدّث D-001→**D-262**

---

## 6. الالتزام المتبقي

يُدمج الـPR مع التحقق من GitHub Actions أخضر 100%؛ وعند الدمج يصبح التقرير هذا مرجعًا مؤرَّخًا في `docs/archive/`.
