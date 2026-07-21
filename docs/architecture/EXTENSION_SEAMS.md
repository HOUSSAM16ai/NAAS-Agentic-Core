# Extension Seams — كيف تُضاف التقنيات دون كود ميت (D-173)

> **قاعدة YAGNI الصادقة:** لا نُنزِل stub لتقنية غير مستخدمة. بدل ذلك، نُوثّق **المقعد**
> (seam) الذي تُركَّب فيه التقنية عند الحاجة الفعلية — نقطة توصيل حقيقية موجودة اليوم،
> مع عقد جاهز حيث ينطبق. هذا يحقّق «القدرة المُتحقَّقة على الإضافة» بلا ZOMBIE.
>
> كل مقعد أدناه: **الحالة الآن** · **المقعد (الملف الحقيقي)** · **شرط التبنّي** · **خطوة التركيب**.

---

## 1. مقعد الأحداث (Event Seam) — Kafka / أي وسيط رسائل

- **الحالة الآن:** العمود الفقري للأحداث هو **outbox relay قائم على قاعدة البيانات**
  (`microservices/orchestrator_service/main.py` + `src/api/routes.py` — `OUTBOX_RELAY_ENABLED`).
  الأحداث تُكتَب في جدول outbox داخل نفس معاملة الكتابة (تسليم مضمون once)، ثم يُصرّفها relay.
- **المقعد:** مُصرِّف الـ relay هو نقطة التبديل. استبداله بمنتج Kafka = تغيير **مستهلك الـ relay**
  فقط، دون لمس مُنتِجي الأحداث (يبقون يكتبون في الـ outbox).
- **العقد جاهز:** `docs/contracts/asyncapi/event-bus.yaml` + `events-api.yaml` (AsyncAPI) تصف
  الرسائل بالفعل — لا حاجة لاختراع مخطط عند التبنّي.
- **شرط التبنّي (متى Kafka؟):** عند تجاوز معدّل الأحداث ما يتحمّله الـ relay القائم على الـ DB،
  أو عند حاجة مستهلكين متعددين مستقلين (fan-out حقيقي). حتى ذلك الحين: **ABSENT-by-YAGNI**.
- **خطوة التركيب:** أضف producer إلى المُصرِّف يكتب رسالة AsyncAPI إلى topic؛ حوّل المستهلكين
  للاشتراك على Kafka. لا تغيير في منطق الأعمال (المُنتِجون يبقون على الـ outbox).

## 2. مقعد المتجهات (Vector Seam) — Vector DB / RAG fine-tuning

- **الحالة الآن:** **pgvector ACTIVE** — عمود `embedding` في `bac_exercises` (Supabase)،
  مُسجَّل في `app/core/db_schema_config.py`. الاسترجاع الحي عبر
  `app/services/capabilities/bac_db_retriever.py` (D-099) + fallback نصّي على `knowledge_base/`.
  التضمينات موجودة لعيّنة من التمارين؛ التوسّع = backfill (`scripts/backfill_exercise_embeddings.py`).
- **المقعد:** `bac_db_retriever` هو طبقة candidate-gen-then-rerank المستقلة عن مصدر المتجهات.
  استبدال pgvector بمتجر مخصّص (Qdrant/Weaviate/…) = تغيير مُولِّد المرشّحين فقط، مع بقاء
  إعادة الترتيب متعددة الإشارات كما هي.
- **شرط التبنّي:** عند تجاوز حجم بنك التمارين ما يخدمه pgvector بكفاءة (مليارات المتجهات + فلاتر
  معقّدة). حتى ذلك: pgvector كافٍ ومُفهرَس.
- **خطوة التركيب (RAG الحيّ):** شغّل `scripts/backfill_exercise_embeddings.py` (idempotent —
  `WHERE embedding IS NULL`) عبر جسر `scripts/db_bridge.py` (HTTPS:443) لتوليد التضمينات على الصفوف
  الجديدة؛ الاسترجاع يعمل تلقائياً. لا كود جديد للاسترجاع.

## 3. مقعد سجل النماذج (Model Registry Seam) — أي مزوّد LLM

- **الحالة الآن:** سلسلة النماذج في `app/core/ai_config.py` +
  `microservices/orchestrator_service/src/core/ai_config.py` (مرآة D-013): PRIMARY + fallback chain
  من نماذج `:free` على OpenRouter، مع حُرّاس (تجاوز 404/429 آلياً — D-167).
- **المقعد:** `ActiveModels`/سلسلة الـ fallback. إضافة مزوّد جديد = مدخل في السلسلة (اسم النموذج +
  مفتاح البيئة). النماذج المحظورة (reasoning-only، D-067) موثّقة صراحةً.
- **شرط التبنّي:** بنشمارك حي قانوني (نفس system prompt + سؤال رياضي) قبل ترقية أي نموذج إلى PRIMARY.
- **خطوة التركيب:** أضف النموذج إلى السلسلة في **العقلين** (monolith + orchestrator)؛ حدّث سكربتات
  التحقق؛ شغّل البنشمارك الحي. لا تغيير في مسار الاستدعاء.

## 4. مقعد أعلام المهارات (Skill Flags Seam) — آلية تبنّي التقنيات المُتحقَّقة

- **الحالة الآن:** `app/services/skills/registry.py` — كل مهارة لها `status ∈ {ACTIVE, FLAGGED, PARTIAL}`.
  **FLAGGED** = القدرة موصولة لكنها خلف علم بيئة (تُفعَّل عند رفع العلم). مثالان حيّان:
  `RetrievalRerankSkill` (LlamaIndex + Reranker، `ENABLE_RETRIEVAL_RERANK_SKILL`) و
  `MCPToolSkill` (MCP، `ENABLE_MCP_TOOL_SKILL`) — قدرات كانت DORMANT، فُعِّلت كمهارات اختيارية (D-100).
- **المقعد:** نمط FLAGGED **هو** آلية تبنّي التقنيات: LlamaIndex/DSPy/Reranker/MCP تُركَّب كمهارة
  بعقد Pydantic + مقاييس Prometheus + اختبارات + علم، ثم تُرقّى إلى ACTIVE بعد الإثبات الثلاثي
  (import + call chain + runtime evidence).
- **شرط التبنّي/الترقية:** ACTIVE يتطلّب البرهان الثلاثي الحي (§6.6). FLAGGED افتراضه OFF (صفر تغيير سلوكي).
- **خطوة التركيب:** أنشئ Skill جديداً في `app/services/skills/` (contract + metrics + tests)، سجّله في
  `registry.py` مع علم، ثم فعّله في البيئة والتحقق الحي قبل الترقية.

## 5. تقنيات ABSENT-by-YAGNI (لا كود، شرط تبنّي صريح)

| التقنية | الحالة | شرط التبنّي | المقعد عند التبنّي |
|---------|--------|-------------|--------------------|
| **Kafka** | ABSENT | معدّل أحداث يتجاوز الـ DB-relay أو fan-out متعدد | §1 (مُصرِّف الـ relay) |
| **TLM** (Trustworthy LM) | ABSENT (غير مُثبَّت) | حاجة مُثبَتة لطبقة ثقة/توجيه نماذج بالكلفة/الجودة | §3 (سلسلة ai_config) |
| **Kagent** | **DELETED (D-173)** | — (كان ZOMBIE محظوراً أمنياً «Invalid token»، صفر مستهلك حي) | — |
| **متجر متجهات مخصّص** | ABSENT | حجم بنك تمارين يتجاوز pgvector | §2 (bac_db_retriever) |

> **درس Kagent (D-173 Stage 5):** حُذف بالكامل (`app/services/kagent/` + `kagent_driver.py` +
> multi-agent workflow + 3 عُقد + توصيلة DI) لأنه ZOMBIE — DI-registered singleton مستهلكه الوحيد
> رسمٌ ميت لا يستدعيه إلا سكربت تحقق يدوي. القاعدة: القدرة بلا مستهلك حي تُحذَف لا تُترك stub.

---

## 6. الرؤية الثورية (أهداف هذه الجلسة — D-173)

> مصدر الحقيقة الحيّ لخارطة الطريق: `.memory/roadmap.md` (ملخّص CLAUDE.md §0.6). هذا القسم يوثّق
> **الأهداف المعمارية** التي وجّهت D-173.

- **API-first 100%:** كل خدمة مصغرة (10/10) لها عقد OpenAPI ملتزَم يغطّي مساراتها الفعلية، مفروض
  ببوّابة تكافؤ دلالية (`scripts/fitness/check_openapi_parity.py`). العقود = الحدود الصريحة بين الخدمات.
- **منظومة وكيلة قابلة للاستبدال:** العقل الحتمي وحدة واحدة (`probability_tutor_brain.py`)، والـ port
  المستقل (`probability_tutor.py`) يخدم الخدمة المصغرة — تكافؤ محروس بـ20 عقداً (split-brain gate).
  الرسمان (12-node chat + 9-node missions) كلاهما حي، والانتقال التدريجي للخدمات المصغرة محكوم
  بـ`ORCHESTRATOR_PROB_TUTOR_ENABLED` (رافعة رجوع فوري، نمط D-025).
- **قتل التعقيد (SOLID/KISS/DRY/YAGNI):** God-files قُتلت (D-163→D-172)، والملفات الضخمة فُكِّكت
  عبر مانيفستات DRY (`TUTOR/BRAIN/API/DOCTRINE/CUSTOMER_CHAT/GRAPH_SOURCE_FILES`) — كل استخراج = سطر
  واحد، البوّابات تقرأ المصدر المُركَّب.
- **خارطة القدرات (متى/كيف نُضيف):** المقاعد أعلاه هي الإجابة الملموسة على «هل نستطيع إضافة
  Kafka/VectorDB/RAG/LlamaIndex/DSPy/Reranker/MCP؟» — نعم، عبر مقعد موجود، بشرط تبنّي صريح، وبلا كود ميت.
- **مقياس النجاح الوحيد (§0.6):** فجوة الوهم = الأداء المدعوم − القدرة غير المدعومة المؤجَّلة. نُحسّن
  على تقليصها — لا على مدة الجلسة/عدد الرسائل/الرضا اللحظي.

**قاعدة الإغلاق:** أي قدرة تُضاف تُثبَّت بالبرهان الثلاثي (import + call chain + runtime evidence)
قبل إعلانها ACTIVE؛ حتى ذلك فهي FLAGGED أو موثّقة كمقعد — لا ZOMBIE.
