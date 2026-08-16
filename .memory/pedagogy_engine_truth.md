# Pedagogy Engine — الحقيقة الجارية (D-263 · ISS-174→ISS-177)

> **المصدر الحيّ الوحيد لادّعاءات «العقل التربوي» في D-263.**
> أيّ ادّعاءٍ تسويقيٍّ أو منتجٍ عن تعلّمٍ أفضل يُتحقَّق هنا أولًا — ولا يُكتب «+X%»
> قبل برهانٍ منشورٍ في هذا الملف (القيد الأحمر ISS-177 · حدّ المصداقية D-227).
> تحرسه `scripts/fitness/check_authority_links.py` + `check_memory_coherence.py`.
> الطموح غير المبنيّ يُصنَّف `PLANNED`/`SEAM`/`ABSENT` صراحةً — لا يُكتب كواقع (D-209).

---

## 1. البرهان الحيّ الأحدث (runtime حقيقي — لا mocks)

| الفحص | التاريخ | النتيجة | الدليل |
|---|---|---|---|
| E2E حيّ كامل: Monolith :8000 + Orchestrator :8006 فوق Supabase الإنتاجية، OpenRouter/Tavily حقيقيان | 2026-08-16 | ✅ 6/6 WS round-trips (جولتان) حتى `persisted` · /health application+database ✅ · ADMIN + USER login ✅ · persistence على Supabase قبل→بعد كل دورة ✅ | `docs/archive/e2e/D263_E2E_LIVE_2026-08-16.md` |
| L2/L4 حيّ: سؤال احتمالٍ تربوي (3 حمراء/2 زرقاء) — الرد بدأ بسؤالٍ سقراطي استقصائي بدل الجواب المباشر («سؤال واحد قبل أي حساب: أيّ الألوان...») | 2026-08-16 | ✅ | الجولة الثانية من E2E أعلاه — الحيرة تُسأل لا تُحسب، سُلّم البسط أولًا |
| BKT ثنائي القناة + FSRS-5 حيّ في مسار التعلّم | مستمر | ✅ ACTIVE | `.memory/runtime_truth.md` سطر 80: FSRS-5 حتمي من `shared/scheduling/fsrs.py` + `ReviewSchedulerSkill`، موصول حيًّا من نتيجة BKT في `customer_chat_support/pedagogy.py`؛ برهان حيّ: إجابة صحيحة بسقالة ⇒ ١٫٢ يوم، وبلا سقالة ⇒ ١٥٫٧ |

**قيد المصداقية (ISS-177):** لا يوجد حتى اليوم برهانٌ مقيسٌ أمام مجموعةٍ ضابطة:
لا pre/post-test موحَّد، لا follow-up متأجّل، لا +X% منشور. أيّ صفحةٍ تقول
«يتحسّن التعلّم بنسبة X» قبل أن يُحسب هذا الرقم هنا **كذبٌ دستوري** (D-227).

---

## 2. الأبواب الأربعة — الحالة الصادقة (SULLAM §6.6)

| الباب | ISS | الحامل الحيّ | الحالة | الفجوة الصادقة |
|---|---|---|---|---|
| النموذج المعرفي للمتعلم | ISS-174 | `TutorState` (D-142) + BKT ثنائي القناة (D-126) + `UnderstandingStateSkill` (D-135) + `illusion_gap` | **ACTIVE** | `illusion_gap` ليس إتقانًا — ممنوع عرض رقم إتقانٍ بلا فجوةِ وهمٍ (P-D) بجانبه |
| ذاكرة التعلّم طويلة الأمد | ISS-175 | BKT (D-126) + FSRS-5 (D-194 · D-229) + الاعتقادات في `semantic_property` | **PARTIAL** | DKT مخطَّط (roadmap) — لا تتبّع عميق قبل بياناتٍ ضخمة (D-229) |
| محرك القرار التربوي | ISS-176 | `PedagogicalPolicyEngine` (D-144) + السُّلّم الخماسي (D-104) + مصفوفة التصعيد + `_build_diagnostic_probe` (D-155) | **ACTIVE** | `pedagogical_trace` (قرار + سبب لكل تدخّل) يحتاج إكمال توثيقه في كل مسار حيّ |
| إثبات Learning Gain | ISS-177 | — | **PLANNED** | القفل الدستوري: pre-test ← تدخّل ← post-test ← follow-up متأجّل + مجموعة ضابطة — لا برهان منشور حتى الآن |

---

## 3. البوابات الحارسة (CI)

`scripts/fitness/check_pedagogy_engine.py` (قوانين L1–L10) ·
`scripts/fitness/check_understanding_evidence.py` ·
`scripts/fitness/check_confusion_never_an_answer.py` ·
`scripts/fitness/check_symbolic_reveal_ledger.py` ·
`scripts/fitness/check_ui_component_parity.py` ·
`scripts/e2e/pedagogy_xproof.py` (L9 — التجربة الخارقة قبل الميزات المائة، مع مراجعة بشرية ملزمة).

**الأدلة النهائية 2026-08-16:** 49/49 بوابة محلية خضراء · ruff 0.14.0 نظيف ·
مؤشر D-263 في `CLAUDE.md §0.15` · القرار في `.memory/decisions.md` ·
البرهان الحيّ في `docs/archive/e2e/D263_E2E_LIVE_2026-08-16.md`.

> **القاعدة الدائمة (D-192/D-209):** هذا الملف يُحدَّث مع كل برهانٍ جديد.
> الرقم المكتوب هنا هو المصدر الوحيد لادّعاء Learning Gain — والرقم يُشتَقّ
> من القياس ولا يُكتب يدويًا.
