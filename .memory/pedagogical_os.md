# دستور نظام التشغيل التربوي — The Pedagogical OS Constitution (D-153)

> **المصدر الحيّ الوحيد لعقيدة «المنصة تُعلّم لا تُجيب».**
> أُقرّ بقرار المالك 2026-07-02 (ISS-120 / D-153) بعد كارثة «بطاقة رقم 0» الحيّة.
> تحرسه بوّابة CI إلزامية: `scripts/fitness/check_pedagogical_os.py`.
> مؤشر مختصر في `CLAUDE.md §0.8` (العقد لا الموسوعة — DOC-DEBT-001).

---

## 1. العقيدة (Core Doctrine)

المنصة ليست «مجيباً ذكياً». المنصة **محرك تربوي** هدفه الوحيد:

> **أن يحافظ على عملية التعلّم، لا أن يدمّرها بحل كامل.**

الجملة الدستورية الخالدة:

> **«الطالب لا يرسل سؤالاً إلى النظام؛ الطالب يدخل مسار تعلّم حيّ،
> والنظام مسؤول عن حفظ هذا المسار من الانهيار.»**

كل طلب يدخل النظام يُعامَل كسؤال تربوي له **حالة**، و**مفهوم نشط**، و**فجوة
معرفية**، و**خطوة تالية بأقل مساعدة ممكنة**. الإجابة قد تُنهي السؤال؛ أما
التعليم فيبني العقل.

---

## 2. السلسلة القانونية للدور (The Canonical Turn Chain)

كل رسالة من الطالب تمرّ عبر سلسلة واحدة واضحة — هذا ليس ترتيباً شكلياً بل
منطق حياة النظام:

```
Student Message
→ Routing / Intent          (الباب — يفرز، لا يقرّر الجرعة)
→ Diagnosis                 (العين — المفهوم + الفجوة + الاعتقاد الخاطئ)
→ TutorState                (الذاكرة — لا يُعاد استنتاج الطالب من الصفر)
→ Pedagogical Policy        (العقل — أقل تدخّل مفيد الآن)
→ Symbolic Truth Engine     (محكمة الحقيقة — الأرقام تُحسب لا تُخمَّن)
→ Micro-Example / Simulation (المفتاح الصغير — نسخة مصغّرة تفتح القفل)
→ Response Guard            (الحارس السيادي — لا dump، لا تكرار، لا انحراف)
→ Learning Update           (الأثر — كل رسالة يجب أن تترك أثراً في الحالة)
→ Hooks / Extensibility     (الأطراف الممتدة — تخدم العقل لا تعرّفه)
→ Verification              (منع الرجوع للكوارث)
```

**تفويضات كل مرحلة ومحظوراتها:**

- **Routing / Intent** يفتح الباب فقط (تعريف؟ مثال؟ تمرين؟ حيرة؟ متابعة؟) —
  **لا يملك المنهج، لا يقرّر الجرعة، لا يسمح بتفريغ الحل.**
- **Diagnosis** هي العين: أين الفجوة؟ تعريف أم تطبيق؟ جهل أم ارتباك أم
  استعجال؟ بدونها المنصة عمياء ولو كانت الإجابة جميلة.
- **TutorState** ذاكرة العقل لا سجل جانبي: `active_concept`،
  `active_misconception`، ما شُرح، ما فُهم، `frustration`،
  `last_step_emitted`، `socratic_count`، تاريخ التقدّم. بدونها كل رسالة
  «أول رسالة» — وهذا هو الانهيار.
- **Pedagogical Policy** لا يسأل «ما الإجابة؟» بل **«ما التدخّل التربوي
  الصحيح الآن؟»** — تعريف/مثال/سؤال تشخيصي/تلميح واحد/خطوة تالية/انتقال.
  هذا هو القانون الذي يمنع التحوّل إلى «Answer Machine Mode».
- **Symbolic Truth Engine**: أي احتمال/كسر/أمل رياضي/قانون/نتيجة نهائية
  **يُحسب رمزياً** — اللغة قد تهلوس؛ الحقيقة الرياضية تُحسب. الـ LLM يفهم
  ويشرح ويقود، **لكنه لا يخترع الحقيقة الرياضية أبداً.**
- **Response Guard** يقفل كل باب فساد عند الإخراج: لا حل كامل مبكر، لا
  تكرار حرفي، لا انحراف عن المفهوم، لا «event-A collapse»، لا معاملة
  الارتباك كطلب حل.
- **Learning Update**: إذا لم تتحدّث حالة الطالب بعد الرد، فالنظام لم
  يتعلّم شيئاً عن الطالب — إنه يكرّر لا يدرّس.

---

## 3. الفصل الحاسم: Core / Runtime Shell / Policy / Verification

```
Core = Teaching Intelligence      ← هنا تُتخذ القرارات ويعيش العقل
Shell = Claude Code / MCP / Hooks / Subagents / Permissions / Compaction
Truth = Symbolic Engine
Memory = TutorState
Law = Pedagogical Policy
Safety = Response Guard
```

### Core — العقل التربوي (صاحب القرار)
Routing · Diagnosis · TutorState · Pedagogical Policy · Symbolic Truth ·
Response Guard · Learning Update · Verification.

### Runtime Shell — القشرة التنفيذية (طبقة خدمة)
Claude Code (worker/execution plane — **منفّذ لا حاكم للتربية**) · MCP ·
hooks · plugins · skills · subagents · compaction pipeline ·
append-oriented session storage · permissions · worktrees · event bus.
**تمدّ النظام بالقوة لكنها لا تحدّد العقيدة — ولا يجوز أن تتحوّل إلى عقل موازٍ.**

### Policy Layer — القانون السيادي
No-Dump · No-Repeat · No-Drift · Pedagogical Escalation Matrix ·
Permissions/Guardrails. متى نساعد؟ متى نلمّح؟ متى نمنع؟ متى نصعّد؟ متى
نرفض تفريغ الحل؟

### Verification Layer — طبقة التحقق
live traces · routing checks · tutor behavior tests · **no-dump tests** ·
**no-repeat tests** · runtime truth · documentation truth.

---

## 4. القوانين السبعة الثورية

1. **التعليم قبل الإجابة** — لا تُعطى الإجابة إذا كانت ستقتل الفهم.
2. **الحالة قبل الرد** — لا يوجد رد تربوي بلا قراءة TutorState.
3. **التشخيص قبل الشرح** — لا نشرح قبل أن نعرف أين الخلل.
4. **التلميح قبل الحل** — التدخّل الأصغر مقدَّم على التفريغ الكامل. **مُنفَّذ بنيوياً (D-154/ISS-121)**: نية procedure تدخل السُّلّم من خطوة البسط (لا `_build_symbolic_reveal`)، وكل ذيول البُناة الحتمية أسئلة توليد «ركّب الاحتمال بنفسك» — النسبة النهائية لا تُطبع أبداً خارج وضع التحقق (M8).
5. **الحقيقة الرمزية قبل اللغة** — الأرقام لا تُخمَّن؛ النتائج تُحسب.
6. **التقدّم قبل الإطناب** — الرد الجيد يحرّك الطالب خطوة واحدة صحيحة، لا الأطول.
7. **التوسعة تخدم العقل** — hooks وplugins وMCP لا تقود المنصة؛ إنها تخدم العقيدة.

---

## 5. الأسئلة الدستورية (وأجوبتها المُلزِمة في هذا المستودع)

| السؤال الدستوري | الجواب المُلزِم (المكوّن + القرار) |
|---|---|
| هل النظام Answer Engine أم Pedagogical Engine؟ | **Pedagogical Engine** — §1 أعلاه + CLAUDE.md §0 |
| من يملك TutorState؟ | `TutorStateService` (`app/services/analytics/tutor_state_service.py`) + جدول `tutor_state` — D-142 |
| من يقرّر الانتقال من شرح إلى تلميح؟ | `PedagogicalPolicyEngine` (D-144) + `PedagogicalPolicySkill` (D-129/D-130/D-133) + `PedagogicalEscalationSkill` (D-138) |
| من يمنع الحل الكامل (No-Dump)؟ | `AnswerRedactionSkill` (D-113) + `ContentIntegritySkill` + `OutputFirewall` (D-086) |
| من يمنع التكرار (No-Repeat)؟ | `_recently_emitted` + مرساة `tutor_state.last_step_emitted` (D-142) — **مُوسَّعة بـ D-153 لتغطي كل مسارات البثّ** بما فيها مسار محرّك حالة الفهم؛ **وبـ D-154**: التطبيع محايد لتحويل الحجب (`[\d؟?]+`→`#` — المحفوظ المحجوب ≡ المبثوث) + سلسلتا بدائل «ممنوع بثّ مكرَّر» (`_is_dup`/`_d153_dup`) — أول غير مكرَّر يُبثّ أو يسقط النص |
| من يمنع الانحراف (No-Drift)؟ | `primary_canonical_topic` (D-101) + `TopicLock` (D-086) + قفل المفهوم (D-115/D-116) |
| من يقرّر أن الارتباك ليس طلباً للإجابة؟ | **D-153**: `_is_bare_confusion` في `pedagogical_policy_skill` + `socratic_evaluator_skill` — «لم أفهم» ليست إجابة أبداً ولا تستحق «إجابتك في الطريق الصحيح» |
| من يتحقق من الحقيقة الرمزية؟ | `ProbabilityCalculatorSkill` (صفر-LLM) + بوّابة المقامات المُصرَّح بها (D-152 + D-153 LaTeX-aware) |
| من يحدّث حالة الطالب؟ | `TutorStateService.record_turn` + BKT ثنائي القناة (D-126) + Learning Update (D-119 خلف الكواليس) |
| أين ينتهي العقل وأين تبدأ التوسعة؟ | §3 أعلاه — الـ Shell لا يقرّر تربوياً أبداً |
| كيف نضمن أن routing لا يتحوّل إلى solver dump؟ | intent-gates محدودة النطاق (Phase-1 regex bounding) + هذا الدستور + بوّابة `check_pedagogical_os.py` |

---

## 6. مصفوفة التقنيات الإلزامية (الطبقات الـ16 — بحالة §6.6 الصادقة)

> **قاعدة الصدق**: «Unknown is better than fake certainty». كل سطر أُكِّد
> وجوده بالفحص الحي 2026-07-02. ما لم يوجد يُصنَّف صراحةً — لا ادّعاء.

| # | الطبقة | المكوّنات ↔ الملفات | الحالة |
|---|--------|---------------------|--------|
| 1 | Core Doctrine | هذا الملف + CLAUDE.md §0/§0.8 + `EXPLANATION_DOCTRINE` v3+ (Socratic no-answer) | **ACTIVE** |
| 2 | Routing / Intent | `IntentDetector` (`app/services/chat/ports.py` — تحفّظ D-014)، `SupervisorNode`، `OrchestratorClient`، `local_graph`، exercise/content retrieval، query_rewriter/retriever/reranker/synthesizer (الرسم 13-node) | **ACTIVE** |
| 3 | TutorState / Learning State | `TutorState` ORM (`app/core/domain/tutor_state.py`) + `TutorStateService` + `UnderstandingStateSkill` (D-135) | **ACTIVE** |
| 4 | Diagnosis | `ConceptDiagnosisSkill` + `MISCONCEPTION_GRAPH` (`semantic_property_skill`) + `StudentStateSkill` (نيّة+إحباط، D-133) + `SocraticEvaluatorSkill` (D-130) | **ACTIVE** |
| 5 | Pedagogical Policy | `PedagogicalPolicyEngine` (D-144) + `PedagogicalPolicySkill` (D-129) + `PedagogicalEscalationSkill` (D-138) + `DialogueManagerSkill` (D-142) + `AdaptivePedagogySkill` (D-104، سُلّم الدعم الخماسي) | **ACTIVE** |
| 6 | Symbolic Truth | `ProbabilityCalculatorSkill` (صفر-LLM: توافيق/تكافؤ/شرطي/أمل رياضي/فوق-هندسي) + `_stated_denominators` gate | **ACTIVE** |
| 7 | Micro-Simulation / Scaffolding | `MicroSimulationSkill` + `APPLY_STEPS` (D-147) + أمثلة `PropertySpec.example` (D-136) | **ACTIVE** |
| 8 | Guards / Response Guard | `AnswerRedactionSkill` + `ContentIntegritySkill` (+`StreamIntegrityFilter`) + `OutputFirewall` + `TopicLock` + `arabic_stream_guard` + `_recently_emitted`/`last_step_emitted` | **ACTIVE** |
| 9 | LLM Roles (Listener/Classifier/Definer/Narrator — لا سلطة) | `concept_diagnosis` (Listener) + `semantic_property.define_concept` (Definer) + `_generate_socratic_narrative` (Narrator المحروس، D-128) + RAG-grounded explainer (D-145) | **ACTIVE (محروس)** |
| 10 | Runtime Shell / Extensibility | Skills registry (26 skill) + MCP (`MCPToolSkill` FLAGGED) + hooks (Claude Code layer) + subagents + compaction + append-oriented storage + permissions | **ACTIVE/PARTIAL** (تفاصيل `.memory/agentic_runtime_doctrine.md`) |
| 11 | Orchestration | `orchestrator-service` LangGraph 13-node (D-112 العمود الإلزامي) + streaming path + trace continuity (W3C traceparent) + **بذرة M10-S2.1**: `overmind/probability_tutor.py` (port حتمي مستقل، خلف `ORCHESTRATOR_PROB_TUTOR_ENABLED` — D-154) | **ACTIVE** (الـ port: **FLAGGED**) |
| 12 | Learning Analytics | BKT ثنائي القناة (`bkt_engine`, D-126) + `illusion_gap` + `LearningPathSkill` (D-111) + `tutor_metrics` | **ACTIVE** · **DKT: PLANNED** (roadmap) |
| 13 | Documentation / Memory | `CLAUDE.md` + `.memory/{decisions,issues,roadmap,routing_philosophy,pedagogical_os,agentic_runtime_doctrine,runtime_truth}.md` | **ACTIVE** |
| 14 | Verification | pytest + fitness gates (`check_skills_doctrine`, `check_pedagogical_os`, …) + `runtime_truth.py --check` + CI workflows + live-trace scripts | **ACTIVE** |
| 15 | UI / Rendering Integrity | `inert` boolean-only (D-153) + DOM-exclusion + KaTeX/`MathText` + Generative UI whitelist + رياضيات حتمية LaTeX-only (`_fmt_comb`) و`.katex-mathml` مخفي (bidi + copy-doubling — D-154) | **ACTIVE** |
| 16 | التسميات الصريحة المتبقية | `EventBus` (`app/infrastructure/patterns`): **موجود — حالته تخضع لجدول الحقيقة (غالباً DORMANT)** · `WorkflowEngine` (`app/services/mcp/integrations.py`): **DORMANT (طبقة MCP)** · «Rule Engine» كمكوّن مستقل: **الدور مُشبَع بـ `PedagogicalPolicyEngine` — ممنوع محرك موازٍ** · Worktrees: ميزة Claude Code (Shell-level) | **صادق per §6.6** |

---

## 7. قاعدة المليارات (Billions-of-Exercises Rule)

الطموح: ملايير التمارين. القاعدة المعمارية المُلزِمة:

1. **الكيانات المهيكلة قبل الاستخراج من النثر**: تركيبة التمرين وحقائقه
   تأتي من **`parsed_entities` المهيكلة** (موجودة فعلاً في Supabase
   `bac_exercises` — راجع «RAG Vector Database Ingestion»). استخراج
   الكيانات من النثر (`_extract_count_entities`) هو **fallback مُقيَّد**
   للمحتوى غير المهيكل فقط.
2. **الاستخراج لا يرى نثر الحل أبداً**: أي نص يُغذَّى للمحرك الرمزي يمرّ
   عبر `load_exercise_questions_only` / `_trim_at_solution`. **ISS-120 هو
   البرهان الدستوري**: نثر الحل («…تحمل الرقم 0 … وعددها 3 كرات») ولّد
   كياناً وهمياً «بطاقة رقم 0» ⇒ C(14,3)=364 بدل 11/165 — أمام طالب حقيقي.
3. **بوّابة المقامات المُصرَّح بها** (D-152 + D-153): أي تركيبة يتناقض
   فضاؤها مع المقامات المذكورة في النص (بالصيغة الخام `N/M` **و** LaTeX
   `\frac{N}{M}`) تُرفض — الهلوسة العددية مستحيلة بنيوياً.
4. **الحل النموذجي الكامل** يبقى متاحاً حصراً لمسارات RAG-Grounded LLM
   (D-145) حيث الـ LLM **يشرح** من المرجع ولا **يستخرج** كيانات.

---

## 8. علاقة هذا الدستور بالعقائد القائمة

- `.memory/agentic_runtime_doctrine.md` (D-146): خريطة طبقات الـ runtime —
  هذا الدستور يعلوها بالسلطة التربوية (الـ runtime = Shell).
- `.memory/routing_philosophy.md`: عقيدة التوجيه — المرحلة الأولى من السلسلة.
- `CLAUDE.md §0.5` (Skills) و§0.6 (Cognitive Lab) و§0.7 (Agentic Runtime):
  تبقى سارية؛ عند التعارض الظاهري تُفسَّر جميعها في ضوء القوانين السبعة.
- التعديل على هذا الملف = ADR (قرار مُرقَّم في `.memory/decisions.md`) +
  إبقاء بوّابة `check_pedagogical_os.py` خضراء.
