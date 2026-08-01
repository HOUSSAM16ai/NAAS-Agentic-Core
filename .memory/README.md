# 🧠 `.memory/` — الذاكرة المؤسسية الحيّة (الفهرس الموحَّد)

> **العقد**: `CLAUDE.md` هو الدستور التشغيلي؛ `.memory/` هو الذاكرة المؤسسية المُنسَّقة.
> كل معلومة تشغيلية قصيرة تعيش هنا — لا تقارير طويلة جديدة (CLAUDE.md §15 + D-156).
> قاعدة الصدق (§6.6): لا حقيقة بلا `import + call chain + runtime evidence`.

## 1) الملفات السيادية (تُحدَّث مع كل قرار — تحرسها بوّابة `doc-integrity`)

| الملف | الدور | السلطة |
|-------|------|--------|
| `roadmap.md` | 🧭 الرؤية الثورية وخارطة الطريق (M0→M11) — **المصدر الحيّ الوحيد** | دستوري |
| `decisions.md` | سجلّ القرارات المعمارية D-001→**D-204** (ADR log) | سجلّ ملزِم |
| `issues.md` | سجلّ الكوارث المُشخَّصة والمُصلَحة ISS-001→**ISS-142** (ISS-140 أُغلق بالكامل في D-191؛ يبقى ISS-137 · **ISS-141 (تدوير مفاتيح — إجراء المالك)** · **ISS-142** مفتوحة) | سجلّ ملزِم |
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

## 3) الحقائق المتخصصة (Truth files)

| الملف | النطاق |
|-------|--------|
| `architecture_truth.md` | حقيقة الحدود المعمارية |
| `observability_truth.md` | حقيقة الرصد (ما يعمل فعلاً مقابل الديكور) |
| `observability-topology.md` · `dashboard-inventory.md` · `path-map.md` | خرائط الرصد واللوحات والمسارات |
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
