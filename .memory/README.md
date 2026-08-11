# 🧠 `.memory/` — الذاكرة المؤسسية الحيّة (الفهرس الموحَّد)

> **العقد**: `CLAUDE.md` هو الدستور التشغيلي؛ `.memory/` هو الذاكرة المؤسسية المُنسَّقة.
> كل معلومة تشغيلية قصيرة تعيش هنا — لا تقارير طويلة جديدة (CLAUDE.md §15 + D-156).
> قاعدة الصدق (§6.6): لا حقيقة بلا `import + call chain + runtime evidence`.

## 1) الملفات السيادية (تُحدَّث مع كل قرار — تحرسها بوّابة `doc-integrity`)

| الملف | الدور | السلطة |
|-------|------|--------|
| `roadmap.md` | 🧭 الرؤية الثورية وخارطة الطريق (M0→M11) — **المصدر الحيّ الوحيد** | دستوري |
| `decisions.md` | سجلّ القرارات المعمارية D-001→**D-238** (ADR log) | سجلّ ملزِم |
| `issues.md` | سجلّ الكوارث المُشخَّصة والمُصلَحة ISS-001→**ISS-157** (**ISS-153 (راية `persisted` تُقتَل قبل السلك ⇒ كتابة مزدوجة على ذراع التراجع — مفتوح، D-238)** · **ISS-154 (دورٌ فارغ صامت + تسريب نصّ استثناء — مفتوح)** · **ISS-155 (توأما WS على المسار الحيّ — مؤجَّل بقرار، مُجمَّدان فلا ينموان)**؛ **ISS-156 (ترميزٌ مزدوج ⇒ تسمّم `customer_messages`) وISS-157 (النموذج المحظور بـD-067 افتراضاً حيّاً) أُغلقا في D-238**؛ **ISS-152 أُغلق في D-236** — «Login failed»: عقدُ أخطاءٍ مُعلَن بنصفه فوق قفلٍ عالمي بعنوان مشترك؛ **ISS-151 (أيقونات من نطاقٍ ثالث — مفتوح مُخفَّف، D-232)** · ISS-150 (تسريب شظايا لاتينية — مفتوح)؛ (ISS-149 أُغلق في D-208؛ ISS-148 في D-207؛ ISS-144 في D-206؛ **ISS-145 أُغلق بالتفنيد في D-209** — الـ212 صفّاً تحمل `ui_component` كلّها، و`truly_silent = 0` على كامل الإنتاج؛ يبقى ISS-137 · **ISS-141 (تدوير مفاتيح — إجراء المالك)** · ISS-142 · **ISS-146 (توجيه تربوي بدور user)** · **ISS-147 (تذبذب 401)** مفتوحة) | سجلّ ملزِم |
| `runtime_truth.md` | جدول الحقيقة التشغيلية (ACTIVE/PARTIAL/DORMANT/ZOMBIE) | **الحقيقة المرجعية** |
| `context.md` | السياق التشغيلي المُلخَّص (يُحمَّل آلياً عند بدء الجلسات) | مرجع سريع |
| `architecture.md` | الخريطة المعمارية المُختصرة | مرجع |
| `tasks.md` · `progress.md` · `logs.md` | تتبّع المهام والتقدّم | تشغيلي |

## 2) العقائد (Doctrines — لا تُكسر بدون ADR)

| الملف | العقيدة |
|-------|---------|
| `pedagogical_os.md` | 📜 دستور نظام التشغيل التربوي (D-153) — السلسلة القانونية + القوانين السبعة |
| `agentic_runtime_doctrine.md` | طبقات الـ Agentic Runtime الـ13 مُقيَّمة بصدق (D-146) |
| `cognitive_lab_philosophy.md` | فلسفة المختبر المعرفي (ليس Chat Tutor) |
| `routing_philosophy.md` | عقيدة التوجيه (intent gates محدودة النطاق) |
| `runtime-rules.md` | قواعد runtime الدائمة |
| `aesthetics_of_absence.md` | جماليات الغياب — مصدر القوانين L8→L12 (D-206). كان موجوداً وغير مفهرَس حتى D-209 |
| `agentic_runtime_doctrine.md` | **حالة** طبقات التنسيق التسع + الثلاث عشرة (D-146/D-209). القانون في `docs/architecture/AGENTIC_ORCHESTRATION_DOCTRINE.md` |
| `coverage-roadmap.md` | خارطة التغطية (D-182). كان موجوداً وغير مفهرَس حتى D-209 |

## 3) الحقائق المتخصصة (Truth files)

| الملف | النطاق |
|-------|--------|
| `architecture_truth.md` | حقيقة الحدود المعمارية |
| `observability_truth.md` | حقيقة الرصد (ما يعمل فعلاً مقابل الديكور) |
| `observability-topology.md` · `dashboard-inventory.md` · `path-map.md` | خرائط الرصد واللوحات والمسارات |
| `revenue_engine_truth.md` | **حالة** طبقات القيمة والإيراد (D-210→D-223) — 12 طبقة · 14 وحدة · 4 خطوط إيراد. القانون في `docs/VALUE_DOCTRINE.md` + `docs/REVENUE_ENGINE_SPEC.md`، وتحرسها `check_revenue_doctrine` |
| `cognitive_execution_truth.md` | **حالة** محرّك التنفيذ المعرفي (D-224/D-225) — ١٣ طبقة + ٤ آفاق سوق. القانون في `docs/architecture/COGNITIVE_EXECUTION_ENGINE.md`، وتحرسها `check_cognitive_execution` (بها **قفل D-187**: نموذجٌ لغوي موصولٌ بمُنفِّذ الصندوق ⇒ CI أحمر) |
| `cognitive_twin_truth.md` | **حالة** التوأم الرقمي المعرفي (D-226/D-227) — ٨ محرّكات + ٣ آفاق. القانون في `docs/architecture/COGNITIVE_DIGITAL_TWIN.md`، وتحرسها `check_cognitive_twin` + `check_prerequisite_single_graph` |
| `code_quality_truth.md` | **حالة** أدوات جودة الكود الثلاث (D-235) — ماذا وجد Qodana وCodeScene وCodeRabbit، وحكمٌ لكل نتيجة حرجة (5 حقيقية · 8 كاذبة)، والحدود المُعلَنة، و**البرهان من سجلّ التشغيل** على أنّ للمِسنَن أسناناً. ⚠️ عدد Qodana **ليس درجة جودة**، و`.coderabbit.yaml` **PARTIAL** حتى تُبلِّغ مراجعةٌ إعداداً غير الافتراضي |
| `ci-gates.md` | فهرس بوّابات CI |
| `fragility-patterns.md` | أنماط الهشاشة المُوثَّقة (Patterns 1-4) |
| `architecture/websocket-topology.md` | طوبولوجيا WebSocket (سلسلة D-WS-*) |

## 4) ركائز المختبر المعرفي (Cognitive Lab pillars)

`cognitive_modeling.md` · `error_memory.md` · `dynamic_generation.md` ·
`interactive_object_ui.md` · `simulation_engine.md`

## 5) الـ Runbooks التشغيلية

| الملف | متى |
|-------|-----|
| `runbooks/e2e-codespaces.md` | التحقق الحيّ الكامل في Codespaces |
| `runbooks/realtime-recovery.md` | استعادة الزمن الحقيقي (WS) |
| `runbooks/supabase-bridge.md` | جسر SQL عبر HTTPS حين تُحجَب منافذ Postgres. كان موجوداً وغير مفهرَس حتى D-209 |

## 6) السجلات التاريخية المُجمَّدة (تُقرأ ولا تُحدَّث)

`diagnostic_2026_05_06.md` · `diagnostic_2026_05_06_rescue.md` ·
`observability-forensic-2026-05-07.md` · `langgraph_advanced_forensics.md` ·
`streaming_architecture_breakdown.md` · `architecture-audit-2026-05-21.md` ·
`content-audit-2026-05-21.md`

> التقارير التاريخية الأقدم (خارج `.memory/`) مؤرشفة في **`docs/archive/`** (D-156).

## 7) وثائق السلطة خارج `.memory/` (تُقرأ مع الذاكرة، لا تُنافسها)

| الملف | الدور | العلاقة بالذاكرة |
|-------|------|------------------|
| `CLAUDE.md` (الجذر) | 🏛️ الدستور التشغيلي — **القوانين الدائمة فقط** (D-188) | يشير إلى `.memory/`؛ لا يحمل حالات ولا سرداً مؤرَّخاً |
| `spec.md` (الجذر) | 📐 **مواصفة برنامج التبسيط API-first** (Phases 0→12) — الهدف المعماري | ليست دستوراً ثالثاً: §4 منها تُحيل صراحةً إلى الدستور القائم و§15 تُلزم بتحديث `.memory/` |
| `roadmap.md §6.5` | الدَّين الهندسي (D1→D7) + خارطة الوكيل (M0→M4) | داخل `.memory/` — المصدر الحيّ لترتيب التنفيذ |
| `docs/VALUE_DOCTRINE.md` | 💰 **قانون** القيمة (D-210): لماذا يدفع أحدٌ في سوقٍ مجّاني — الوظائف الأربع + اختبار الحذف + المحرَّمات التسعة | الحالة في `revenue_engine_truth.md` — ⛔ لا يحمل حالات |
| `docs/REVENUE_ENGINE_SPEC.md` | 💰 **قانون** محرّك الإيراد (D-210→D-223): ماذا يُكتب بالضبط — العقود والنماذج والبوّابات | نفس القاعدة: القانون بلا حالة |
| `docs/architecture/COGNITIVE_EXECUTION_ENGINE.md` | 🧠⚙️ **قانون** محرّك التنفيذ المعرفي (D-224) — الحقيقة تُنفَّذ واللغة تصفها؛ والحتمي قبل التوليد البرمجي | الحالة في `cognitive_execution_truth.md` — ⛔ لا يحمل حالات |
| `docs/architecture/COGNITIVE_DIGITAL_TWIN.md` | 👤🧠 **قانون** التوأم الرقمي المعرفي (D-226/D-227) — الطالب قصّة مستمرّة؛ رسمٌ واحد للعلاقة؛ وحدّ المصداقية | الحالة في `cognitive_twin_truth.md` — ⛔ لا يحمل حالات |
| `docs/DOCUMENTATION_INDEX.md` | خريطة السلطة الكاملة لـ`docs/` | مرجع مساند |

## القواعد الملزِمة

1. **قرار جديد** ⇒ إدخال في `decisions.md` + قسم CLAUDE.md §6.x + تحديث `roadmap.md` إن مسّ المراحل.
2. **كارثة جديدة** ⇒ إدخال ISS-### في `issues.md` مع الجذر والدليل الحيّ.
3. **تغيير قدرة تشغيلية** ⇒ تحديث `runtime_truth.md` + `python scripts/runtime_truth.py --update` في نفس الـ PR.
4. **ممنوع** ملف MD تشغيلي جديد خارج `.memory/` — والتقارير المنتهية تذهب إلى `docs/archive/`.
5. **(D-188) هذا الفهرس عقدٌ مفروض آلياً**: أقصى `D-###` في `decisions.md` وأقصى `ISS-###`
   في `issues.md` **يجب** أن يظهرا في الجدول أعلاه، والسجلّان مرتَّبان تنازلياً (الأحدث أولاً).
   تفرضه بوّابة `scripts/fitness/check_memory_coherence.py` ضمن workflow `doc-integrity`.
   السبب: بين 2026-05 و2026-07 انحرف هذا الفهرس عن الواقع بثلاثة قرارات وكارثتين بلا أن يلاحظه أحد.
