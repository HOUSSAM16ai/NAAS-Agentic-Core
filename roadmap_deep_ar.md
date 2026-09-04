# خارطة الطريق المتكاملة — من الحالة الراهنة إلى العملة الصعبة
> **المصدر الوحيد الحي:** `.memory/roadmap.md` (M0→M11) + `.memory/naas_verification_truth.md` (M53→M63) + `.memory/revenue_engine_truth.md` (D-210→D-223) + `docs/commercial/AGENT_ACTION_ASSURANCE_INVESTMENT_CASE.md` (§6–§10) + `.memory/naas_verification_constitution.md` (L1–L10).
> **قاعدة القراءة:** ما هو `PROPOSED` أو `ABSENT` ليس فشلاً — هو إعلان صادق. ما هو `ACTIVE` أو `PARTIAL` ليس نجاحاً تجارياً — هو قدرة تقنية قابلة للقياس.

---

## 1. الهيكل العام — ثلاثة مسارات لنظام واحد

المستودع لا يبني منتجاً واحداً بل **منظومة متكاملة** من ثلاثة مسارات متوازية لا تستعير أدلةً من بعضها:

| المسار | المرجع الدستوري | ما يبني | الحالة الراهنة |
|---|---|---|---|
| **أ. المحرّك التربوي** (M0→M11) | `.memory/roadmap.md` · `CLAUDE.md` §6.91→§6.97 | محرّك تعلّم معرفي قابل للتحقّق لبكالوريا الجزائر | M0–M5.5 ✅ · M7 ✅ · M6 🚧 (BKTTruth) · M8–M10 📋 · M11 ⏸️ |
| **ب. طبقة التحقّق NAAS** (M53→M63) | `.memory/naas_verification_constitution.md` · `NAAS_VERIFICATION_LAYER.md` | مُتحقِّق مستقلّ يُثبت أنّ الوكيل اتّبع القيود والسياسة ووصل الحالة المطلوبة | M53 ✅ · M54 ✅ (على اصطناعية) · M55 `PARTIAL` · M56 `ABSENT` · M57 ✅ · M58 `ABSENT` · M59–M63 `PLANNED` |
| **ج. المحرّك التجاري/الإيرادي** (D-210→D-223) | `.memory/revenue_engine_truth.md` · `VALUE_DOCTRINE.md` · `REVENUE_ENGINE_SPEC.md` | قناة قبض + بنك محتوى + توقع مُعايَر + عقد موسم + تقرير وليّ | D-210 ✅ (قانون) · D-211 `SEAM` · D-212 `ACTIVE` (بلا تقرير) · D-213 `PARTIAL` · D-214–D-216 `ABSENT` · D-217 `PARTIAL` · D-218 `PARTIAL` · D-219 `PARTIAL` · D-220 `PARTIAL` · D-221 `PARTIAL` · D-222 `ABSENT` · D-223 `PARTIAL` |

> ⛔ **الفصل الثلاثي قانون (L1 من الدستور الجديد D-267):** لا استيراد عابر بين المسارات الثلاثة. المنتج (`NAAS`) لا يستورد من المنصّة التعليمية، والمنصّة لا تُعير أدلة تعلّمها للمُتحقِّق، ولا المُتحقِّق يُعير أدلته للمنتج التعليمي. كلٌّ يُثبت نفسه بدليله الخاص.

---

## 2. المسار أ — المحرّك التربوي (الأساس التقني)

### 2.1 المراحل المنجزة (✅) — مع شرط الترقية الذي أثبتها

كل مرحلة في `.memory/roadmap.md` تحمل **برهاناً ثلاثياً (§6.6)** — لا تُرقَّى بمجرد كتابة سطر:

| المرحلة | ما تبنيه | الدليل المُثبَت في المستودع | لماذا يهمّ للمسار التجاري |
|---|---|---|---|
| **M0 — أساس BKT** (`D-074`) | تتبّع معرفي بايزي (`bkt_engine.py`) · سجلّ `append-only` · لا LLM في المسار | `tests/` + `student_bkt_analytics` حيّ | أساس كل قياس صادق لاحق |
| **M1 — بيداغوجيا تكيفية** (`D-104`) | `AdaptivePedagogySkill` يقرأ الإتقان ويقود العمق | `Skill #15` مسجَّل + مستهلك حيّ | لا يمكن بيع «تشخيص» بلا طبقة قياس |
| **M2 — العمود الفقري الإلزامي** (`D-112`) | `microservices` إلزامية؛ لا `fallback` صامت عند فشل خدمة | `ORCHESTRATOR_REQUIRED` · E2E 6/6 ناجحة | البنية التحتية التي يُبنى عليها المُتحقِّق |
| **M3 — مسار تعلّمي** (`D-111`) | `LearningPathSkill` فوق BKT + بطاقة مسار | `Skill #17` + `learning_path_card` | يُقدِّم «ما لا يعرفه الطالب» — السلعة التجارية |
| **M4 — السقراطية ج1** (`D-113` ج1) | `doctrine` سقراطي + أسئلة-فقط + `AnswerRedactionSkill` (`Skill #18`) | `EXPLANATION_DOCTRINE` v3.0.0 · `_stream_exercise_explanation_response` يُمرِّر `display_content` فقط | يمنع كشف الجواب — القانون الذي يجعل المنتج نادراً |
| **M5 — السقراطية ج2** (`D-113` ج2) | حجب في `orchestrator` (`response_sanitizer`) + عقد `SynthesizerNode` + سُلّم دعم خماسي | `redact_final_answers` + `sanitize_response` + `support_level` 1..5 مشتقّ حتمياً | يُجبر الطالب على توليد الخطوات |
| **M5.5 — البروتوكول المنضبط** (`D-115`) | عكس `D-114` (كارثة حيّة: كشف مثال محلول) → بروتوكول مُنضبَط في `orchestrator` | `§6.99` · `COGNITIVE_TURN_ENABLED` | يُصحِّح خطأً تصميمياً كان سيُفشل المصداقية |
| **M7 — مُعلّم الاحتمالات البصري التفاعلي** (`D-116`) | بصري حتمي كامل (`sympy`) · سؤال واحد/شاشة · كشف جزئي بعد تحقق الطالب | `§6.100` · `probability_tutor` · مُطهّر `U+0305`/`ë` | يُثبت أن «الأرقام لا تُولَّد أبداً» قابلة للتطبيق |
| **M9 — مقياس فجوة الوهم** (`D-157`) | `Prometheus` + `Grafana` لوحة 180: `illusion_gap = assisted − unaided_delayed` | `cogniforge_tutor_illusion_gap` مُعرَّف | المقياس التجاري الوحيد المسموح به |

### 2.2 المراحل الجارية (🚧) والمخطَّطة (📋) — مع شروطها

| المرحلة | الهدف | الحالة | **شرط الترقية الصريح (من الملف)** |
|---|---|---|---|
| **M6 — صدق BKT** (`D-157`) | فصل الأداء المدعوم عن الإتقان الحقيقي: `assisted_mastery` vs `unaided_delayed_mastery` + `scaffold_leak` | 🚧 (`M6-A` ✅ محرّك الإتقان الصادق + `M6-0` ✅ محرّك الدور المعرفي) | إشارة صواب ثلاثية + منحنى نسيان متّصل (`durable` يرتفع بصدق) + تجاوز رمزي (`D-155`) + ثابت مضاد للوهم |
| **M7 — واجهات بلا أرقام** | واجهات تُظهر البنية والمنهج دون كشف النتيجة النهائية | 📋 | يحترم `P-B` (منع مطلق للنتيجة) + `P-A` (لا تكشف خطوة قابلة للتوليد) |
| **M8 — وضع التحقق المنفصل** | المسار الوحيد لكشف النتيجة: طلب صريح «تحقّق من حلي» | 📋 | `full_content` متاح فقط لوضع التحقق حسب `D-113` |
| **M10 — هجرة الرسم S2–S4** | `microservices-only` كاملة: المهارات الحتمية داخل `orchestrator` graph + `CritiqueNode` (تحقّق ذاتي) + `Mastery-Aware Orchestrator` | 📋 (`D-108/109/110` مُصمَّمة) | كل مهارة `ACTIVE` مع `import` + سلسلة نداء + دليل تشغيل (`§6.6`) |
| **M11 — الصوت** (`D-107`) | TTS/STT بنماذج صوتية متقدّمة | ⏸️ مؤجَّل (`§6.93`) | لا يُفعَّل قبل إثبات أن الصوت لا يكسر `D-113` (لا يكشف الجواب عبر النطق) |

---

## 3. المسار ب — طبقة التحقّق NAAS (M53→M63)

### 3.1 المبدأ الدستوري (من `.memory/naas_verification_constitution.md`)

> **«الوكيل القويّ مع مُتحقِّقٍ ضعيف = كذبٌ مُقنع.»**

المُتحقِّق ليس ميزة داخل المنصّة التعليمية — هو **منتج مستقلّ** (`core/` مستقل عن `app/` وعن `shared.curriculum`). يقرأ مساراً (`Trajectory`) ويُصدر **دليلاً مُسمَّى** (`Verdict` + `Evidence`)، لا درجة عارية.

### 3.2 المراحل المنجزة (✅ / `ACTIVE` / `PARTIAL`)

| المرحلة | الوحدة | الدليل المُثبَت | الفجوة الصادقة (`.memory/naas_verification_truth.md`) | شرط الترقية |
|---|---|---|---|---|
| **M53** | حزمة الحوكمة والأدلّة | `GATE_STATE_MACHINE.md` + `GATE_LEDGER.json` + `check_naas_verification` (٢٧ تجربة سلبية مُثبَتة) | ✅ حيّة — لا سجلّ دليل واحد مُسجَّل بعد (وهذا صادق لا نقص) | — (مُرقَّاة فعلاً) |
| **M54** | القلب المستقلّ عن المجال (`core/`) | `trajectory.py` · `constraint.py` · `evidence.py` · `verdict.py` | ✅ مُنفَّذ ومُختبَر على مساراتٍ اصطناعية وذخيرة — ⛔ **لم يقرأ بعدُ مسار وكيل حقيقي من نظام خارجي** | أوّل مسار من نظام طرف ثالث يُقرأ ويُحكَم عليه بدليل مُسجَّل |
| **M55** | مُحوِّل المجال (`adapter/` — السلّم) | `multilingual_probe.py` حيّ (`test_corpus_and_probes.py`) | `PARTIAL`: مُحوِّل حي واحد (صف 10)؛ **مُحوِّل السلّم نفسه لم يُبنَ** ومشتقّاته غير مُصدَّرة كبيانات | تصدير ملف بيانات السلّم مُلتزَماً + قراءة صريحة للفشل عند غيابه |
| **M57** | ذخيرة أصناف الاختراق (`corpus/`) | `ar_fr_exploit_classes.json` — ٥ أصناف متمايزة الجذر | ✅ حيّة — **اثنان منها (`ISS-146` · `ISS-150`) `publishable=false`** لأن مصدرَيهما مفتوحان | إغلاق `ISS-146` و`ISS-150` ليصير الخمسة قابلين للنشر |

### 3.3 المراحل الغائبة (`ABSENT`) — الأكثر أهمية للتجاري

| المرحلة | الوحدة | لماذا غائبة | **شرط الترقية** |
|---|---|---|---|
| **M56** | المعايرة القياسية (`calibration/`) | لا اتّفاق مقيس بين المُتحقِّق ومراجع بشري | عيّنة مُصنَّفة بشرياً + معامل اتّفاق (`inter-rater agreement`) محسوب ومنشور |
| **M58** | التحقّق التجاري | لا معاملة مُسوَّاة بمبلغ موجب (`GATE_C` فارغة) | **معاملة مُسوَّاة** بمبلغ موجب ⇒ ترقية `GATE_C`. ⛔ نجوم واجتماعات غير مدفوعة ليست دليلاً |

> ⚠️ **هذه هي العقبة الحاسمة للعملة الصعبة.** كل ما قبل `M58` هو قدرة تقنية. `M58` هو الدليل الوحيد المقبول تجارياً حسب الدستور (`L9` — العتبة كمّية وقابلة للتكرار: `Δ ≥ 15%` على أساس مثبَّت + `≥ 3` أصناف اختراق متمايزة الجذر + دفع حقيقي).

### 3.4 المراحل المقترحة (`PLANNED`) — الامتداد التجاري

من `AGENT_TRUST_CONTROL_PLANE.md` (`ADR-017`) — هذه معمارية مستهدفة **لا حالة تشغيلية**:

| المرحلة | الوحدة | الحالة | **شرط الترقية** (من `AGENT_TRUST_CONTROL_PLANE.md` §2 — "Credibility boundary") |
|---|---|---|---|
| **M59** | مهايئ مسار وكيل خارجي مصرح به | `PLANNED` | مسار طرف ثالث في `sandbox` يُقرأ ويُحكَم عليه بحزمة إعادة إنتاج، دون أسرار إنتاج أو ادعاء تعميم |
| **M60** | `Agent Action Assurance` قابل للبيع | `PLANNED` | **ثلاثة عملاء غير مرتبطين** يدفعون للنتيجة نفسها + فشل شديد يؤكده العميل + إعادة استخدام مقيسة (`≥70%`) بين التجارب |
| **M61** | مراقبة `shadow mode` | `PLANNED` | قياس `held-out` للدقة والإيجابيات الكاذبة والسلبيات الكاذبة والتغطية والكمون — **بصفر أثر حجب على الإنتاج** |
| **M62** | بوابة أفعال `inline` محدودة | `PLANNED` | صنف فعل واحد بموافقة العميل + سياسة فشل صريحة (`fail-open` أو `fail-closed`) + HA/SLO + سلامة الموافقة + تمرين حادثة (`incident drill`) + استعادة (`recovery`) |
| **M63** | هوية وتفويض وثقة متعددة الوكلاء | `PLANNED` | `ADR` أمني مستقل + سلسلة تفويض قابلة للإبطال + تكاملان مستقلان (`independent integration`) + دليل احتفاظ (`retention`) وطلب متكرّر |

---

## 4. المسار ج — المحرّك التجاري والإيرادي (D-210→D-223)

### 4.1 المبادئ الحاكمة (من `VALUE_DOCTRINE.md` و`.memory/revenue_engine_truth.md`)

- **القاعدة الدستورية (`D-210`):** المجّاني يبيع الإجابة؛ الإجابة صارت سلعة بلا ثمن. نحن نبيع **المعرفة بما لا يعرفه الطالب** — سلعة لا تُنتَج من سؤال واحد بل من **تاريخ** (`BKT` + `FSRS`).
- **اختبار الحذف (`D-210`):** كل ميزة مقترحة تُسأل: لو حُذفت، أيٌّ من الوظائف الأربع (`قِس` · `رتِّب` · `أجبر على التوليد` · `أثبت للدافع`) يتوقّف؟ إذا كان الجواب «لا شيء» — تُحذَف.
- **المحرَّمات التسع (`D-210`):** مكتبة محتوى · نموذج مُدرَّب من الصفر · تتبّع معرفي عميق قبل بيانات كبيرة · جدارية تصنيف · أي آلية إدمانية.

### 4.2 خريطة الحالة الحالية مع الفجوات الصادقة

من `.memory/revenue_engine_truth.md` (§2.a — «سُلَّم الحالة»):

| الوحدة | الدليل في المستودع | الحالة | الفجوة الصادقة | شرط الترقية |
|---|---|---|---|---|
| **D-211** `billing_service` (`microservices/`) | **غير موجود في المجلد** | `SEAM` | لا مزوّد دفع (`Chargily`/`SATIM`) ولا عربون (`Deposit`) ولا دفتر حركات (`Ledger`) | عقد `Chargily Pay V2` (`EDAHABIA` + `CIB`) + `Entitlement` مصدر واحد + `check_entitlement_single_source` |
| **D-212** محرّك فجوة الوهم (`shared/illusion/`) | `IllusionGapSkill` + `POST /api/v1/skills/illusion` | `ACTIVE` | المحرّك جاهز؛ **لا التقاط ثقة في الواجهة** (`confidence` قبل الإجابة) ولا **تقرير معروض قابل للتصوير** (`single-page report`) | واجهة التقاط ثقة (`JOL` — `Nelson & Narens`) + قالب تقرير (`PDF`/صورة) يُظهر الخانة الحمراء (`DANGEROUS`) للولي |
| **D-213** بنك العناصر المُعايَر | `content_items` (٣ سجلات) · `content_solutions` (`steps_json` فارغة) | `PARTIAL` | **الثلاثة تصف نفس التمرين** (`bac-2024-exp-math-s1-ex1`) · لا `Elo` · لا `content_hash` مانع للتكرار · لا بوّابة `MIN_ITEMS_PER_CONCEPT` | بناء بنك حقيقي + بوابة تغطية (`MIN_ITEMS_PER_CONCEPT`) + `content_hash` + `verified_by_human` |
| **D-214** التصحيح بالسلم (`shared/scoring/`) | لا حامل — وجهة `barem.py` | `ABSENT` | يحتاج رقمنة سلالم رسمية (`DZ-BAC`) + قناة التقاط بالصورة (`OCR`) | رقمنة السلم + `OCR` + اختبار `contract` |
| **D-215** البرهان الرمزي (`shared/verify/`) | لا حامل — وجهة `sympy` | `ABSENT` (`SEAM` فقط إذا بُني) | `sympy` تبعية جديدة تحتاج `ADR` (`D-215`) + ⛔ `TIMEOUT` لا يُمرَّر أبداً حين تُبنى | `ADR` + تبنّي `sympy` + `check_symbolic_no_timeout_pass` |
| **D-216** التوقّع المُعايَر (`shared/forecast/`) | لا حامل | `ABSENT` | مشروط بـ`D-213` أولاً (`content bank` مُعايَر) + لا `Monte Carlo` ولا `CalibrationCard` | بناء `D-213` أولاً + `Monte Carlo` + `CalibrationCard` منشورة (`Brier score` + `reliability curve`) |
| **D-217** أطلس الأخطاء (`shared/misconceptions/`) | سِمَة `misconception` بلا سجلّ (`concept_diagnosis_skill`) | `PARTIAL` | لا `verified_by_human` ولا دورة حياة أسبوعية ولا ربط بتمارين علاجية | سجلّ `misconception` + مراجعة بشرية أسبوعية (`weekly review cycle`) + ربط بتمارين علاجية (`remediation exercises`) |
| **D-218** مُحسِّن الوقت (`shared/scheduling/`) | `ReviewSchedulerSkill` (داخل المادة فقط) | `PARTIAL` | لا دالّة هدف عبر المواد (`cross-subject optimizer`) + `MAX_CONSECUTIVE_SAME_CONCEPT` غير مفروض | دالّة هدف (`objective function`) عبر المواد بمعاملات الشعبة + قيد `MAX_CONSECUTIVE_SAME_CONCEPT` |
| **D-219** اقتصاد الاستدلال (`shared/ai_models/`) | سلسلة نماذج (`model_chain.py`) + `preempts` حتمية | `PARTIAL` | لا `Tier` مُعلَن (`Tier 1/2/3`) ولا `cogniforge_cost_per_student_month_dzd` كمقياس من الدرجة الأولى | تصنيف `Tier` + مقياس تكلفة (`cost per student per month` بالدينار الجزائري) |
| **D-220** عقد الموسم (`shared/commitment/`) | `shared/habit/streak.py` (بتقويم الطالب `D-195`) | `PARTIAL` | لا عقد موسم (`season contract`) ولا مرساة بداية جديدة (`new start anchor`) ولا إشعار مرتبط بالنسيان (`forgetting-linked notification`) | عقد موسم (`opt-in`, قابل للفسخ) + مرساة جديدة + إشعار |
| **D-221** قناة الولي (`app/services/guardian/`) | `guardian/report.py` (داخل المنتج) | `PARTIAL` | **قناة خروج غائبة** (لا `WhatsApp` ولا `SMS` ولا `email`) + لا `collapse_alert` (تنبيه انهيار المسار) | `WhatsApp`/`SMS` + `collapse_alert` + `single_action` (ربط برضا الطالب) |
| **D-222** المعيار العمومي (`benchmarks/dz_bac_bench/`) | لا حامل — وجهة المجلد | `ABSENT` | مشروط بـ`D-213` (`content bank`) · نشر نتائج النماذج العامة على المعيار نفسه جزء من العقد (`D-210`) | بناء `D-213` أولاً + `DZ-BAC-Bench` + نشر نتائج (`public benchmark results`) |
| **D-223** البوّابة الجامعة (`check_revenue_doctrine`) | `scripts/fitness/check_revenue_doctrine.py` | `PARTIAL` | تحرس **الوثائق والتصنيف** اليوم؛ بوّابات التغطية (`MIN_ITEMS_PER_CONCEPT`) والسلّم (`barem`) والتدرّج (`Tier`) تُضاف مع كل وحدة | إضافة بوابات فرعية (`sub-gates`) مع كل ترقية وحدة (`D-213`→`coverage`, `D-214`→`scoring`, `D-219`→`tier`) |

---

## 5. المسار د — المحرّك المعرفي الرقمي والتوأم (M31→M52 · M45→M52)

من `.memory/roadmap.md` (§4.5 · §4.8) و`docs/architecture/COGNITIVE_EXECUTION_ENGINE.md` + `COGNITIVE_DIGITAL_TWIN.md`:

### 5.1 المحرّك المعرفي (M31→M44) — من الفهم إلى التحسين الذاتي

> **القانون الحاكم (`D-224`):** الحقيقة تُنتَج بمحرّكٍ حتمي يُنفَّذ ويُتحقَّق منه، واللغة تصفها ولا تُقرّرها. ⛔ **الحتمي أوّلاً والتوليد البرمجي آخِراً:** `REGISTRY → FOUNDATIONS → SYMBOLIC → SYNTHESIS`.

| المرحلة | المحرّك | **شرط الترقية** | الحالة |
|---|---|---|---|
| **M31** | الفهم اللغوي (`textnorm` + `intent`) | ✅ حيّة — يبقى مجموعة اختبارٍ موسومة (`labeled test set`) تقيس الفهم عبر اللغات الثلاث (`ar`/`fr`/`darija`) | ✅ |
| **M32** | الرسم المعرفي (`knowledge_graph`) | أنماط الخطأ (`misconception`) تصير عُقَداً في الرسم — يشترط `D-217` أولاً | 📋 |
| **M33** | تصنيع البرنامج (`program_synthesis`) | ⛔ **مقفول بـ`D-187`:** لا يُفتَح قبل `M1→M4` من `§6.5.ج`. توليد رقعة بنموذج + تنفيذها = حمولة القفل | ⛔ مُقفَل |
| **M34** | الصندوق الآمن (`sandbox`) | ✅ مبنيّ ومُشدَّد (`python`/`pip`/`git`/`npm`) — الترقية إلى `ACTIVE` **تعني** `M1→M4` لا مستهلكاً ذكياً قبلها | ✅ |
| **M35** | التحقّق الصوري (`sympy`) | `ADR` لتبنّي محرّك جبر رمزي + `check_symbolic_no_timeout_pass` (`D-215`) | 📋 |
| **M36** | التحويل التربوي (`pedagogical_transform`) | ✅ حيّ — يبقى إغلاق المرحلة 12 من مراحل الدور (`ISS-148`) | ✅ |
| **M37** | النموذج المعرفي (`cognitive_model`) | ✅ حيّ (`BKT` + `FSRS`) — يبقى التقاط الثقة المُعلَنة (`declared confidence`) في الواجهة (`D-212`) | ✅ |
| **M38** | الذاكرة طويلة المدى (`long_term_memory`) | ✅ حيّة — يبقى ربط «لماذا أخطأ» (`why did I fail`) برسم الذاكرة (`D-217`) | ✅ |
| **M39** | التخطيط التكيّفي (`adaptive_planning`) | دالّة هدف (`objective function`) عبر المواد + قيد تشبيك (`cross-subject constraint`) مفروض (`D-218`) | 📋 |
| **M40** | نموذج العالم (`world_model`) | بيانات جلساتٍ حقيقية بحجم كافٍ (`sufficient session volume`). ⛔ **يُصنَّف ولا يُدَّعى** (`D-227` حدّ المصداقية) | 📋 |
| **M41** | مجتمع الوكلاء (`agent_society`) | `Critic` مستقل حي (`D-109` · `M10`) — والكاتب (`writer`) لا يُصحِّح نفسه (`self-correction` ممنوع) | 📋 |
| **M42** | التحسين الذاتي (`self_improvement`) | تقييم (`evaluation`) قبل تطبيق (`before application`) + `check_agent_self_modification` (`M4`) | 📋 |
| **M43** | المعرفة المُتحقَّقة (`verified_knowledge`) | اكتمال الحلقات 3 (`synthesis`) و5 (`verification`) — السلسلة لا تُغلَق بحلقة مفقودة | 📋 |
| **M44** | آفاق السوق (`market_expansion`) | الجزائر مُثبَتة ⇒ الفرنكوفونية ⇒ أوروبا ⇒ الولايات المتحدة. ⛔ **كلٌّ بدليل مقيس** (`measured evidence`) لا إعلان (`D-209` · `D-225`) | 📋 |

### 5.2 التوأم الرقمي المعرفي (M45→M52) — من الرسم إلى الذاكرة عبر السنوات

من `.memory/roadmap.md` (§4.8) و`docs/architecture/COGNITIVE_DIGITAL_TWIN.md`:

> **القانون (`D-226`):** الطالب **قصّة مستمرّة** لا سلسلة أحداث مستقلّة. والألم المُعالَج اسمه **كرة ثلج سوء الفهم (`snowball misunderstanding`)**: ثغرة مبكّرة لا يتذكّرها شيء تُسقِط عقلاً بعد سنوات.

| المرحلة | المحرّك | **شرط الترقية** | الحالة |
|---|---|---|---|
| **M45** | رسم المنهاج (`curriculum_graph`) | ✅ حيّ (`D-193`) — يبقى توسيع التغطية إلى منهاج كامل (`full curriculum coverage`) | ✅ |
| **M46** | رسمٌ واحد للعلاقة (`relationship_graph`) | ✅ **أُصلح في `D-226`** — كان أعمى عن ٢٦ حافّة (`edges`) والتقاطع صفر (`intersection zero`) | ✅ |
| **M47** | تتبّع المعرفة (`BKT tracking`) | ✅ حيّ بقناتين (`assisted`/`unaided`) — ⛔ لا `DKT` قبل حجم بيانات ضخم (`massive data volume`) | ✅ |
| **M48** | التدخّل على الجذر (`root_intervention`) | ✅ حيّ عبر المواد (`cross-subject`) — يبقى نصّ تدخّل مكتوب (`written intervention text`) لكل مفهوم منهاج | ✅ |
| **M49** | التكرار المتباعد (`spaced_repetition`) | ✅ حيّ داخل المادة (`FSRS`) — يبقى **نسجُ مفهوم قديم داخل تمرين جديد** (`embedding old concept in new exercise`) | 📋 |
| **M50** | البُعد الزمني (`temporal_dimension`) | حقل `term`/`month` في سجلّ المنهاج (`curriculum_registry`). ⛔ **حتى ذلك: لا ادّعاء توقيت** (`no timing claim`) | 📋 |
| **M51** | الذاكرة عبر السنوات (`cross-year_memory`) | انتقال الحالة (`state transition`) عبر سنة دراسية + هجرة مُعرِّفات (`identifier migration`) بلا فقد للتاريخ (`history preservation`) | 📋 |
| **M52** | منهاج ثانٍ (`french_curriculum`) | سجلّ يمرّ ببوّابات `D-193` نفسها + مُعرِّفات (`identifiers`) لا تصطدم بالمُخزَّن (`no collision`) | 📋 |

---

## 6. القفل الأمني — أهم سطر في الخارطة

من `.memory/roadmap.md` (§4.5 · `M33`) و`docs/architecture/COGNITIVE_EXECUTION_ENGINE.md`:

> ⛔ **`M33` (تصنيع البرنامج / `program_synthesis`) لا يُفتَح قبل `M1→M4`** (`§6.5.ج` · `D-187`).
> الصندوق (`sandbox`) مبنيّ ويُشغِّل `python`/`pip`/`git`/`npm`، والمستخدمون **قاصرون** (`minors`).
> توصيل نموذج لغوي به (`LLM` → `sandbox` → `execution`) بلا عقد قدرات (`contract`) ولا ميزانية (`budget`) ولا سجلّ تدقيق (`audit log`) هو **الطريق المعروف إلى حادثة أمنية**.

> **القدرة (`capability`) ≠ الأمان (`safety`).** ويُفرضه بند `AST` داخل `check_cognitive_execution`: وحدة تجمع مُنفِّذ الصندوق (`sandbox executor`) مع عميل نموذج (`model client`) في وحدة واحدة ⇒ `CI` أحمر. خمس تجارب سلبية (`negative tests`) مُثبَتة.

---

## 7. المسار نحو العملة الصعبة — خطة الـ90 يوماً المُنظَّمة

من `AGENT_ACTION_ASSURANCE_INVESTMENT_CASE.md` (§10 — "Ninety-day evidence plan"):

### الأيام 1–30: دليل المشكلة (`Problem Evidence`)
- إجراء **15 مقابلة مشتري مؤهل** (`qualified buyer interviews`) — تسجيل المشكلة (`problem`)، العملية الحالية (`current process`)، التكلفة السنوية (`annual cost`/`risk`)، سلطة القرار (`authority`)، والميزانية (`budget`).
- تنفيذ **مهايئ مسار واحد** (`authorized trace adapter`) في `sandbox`.
- تعريف المقارنة (`held-out comparison`) مقابل عملية `QA`/`security` الحالية للعميل.

### الأيام 31–60: إثبات الدفع (`Paid Proof`)
- إغلاق **أوّل تجربة ضمان أفعال مدفوعة** (`first bounded paid pilot`) بالعملة الصعبة (`foreign currency`).
- تشغيل الأساس (`baseline`) و`NAAS` على نفس المسارات (`same traces`).
- نشر **فقط نتائج مُعتمَدة من العميل** (`customer-approved, anonymized results`) مع المقامات (`denominators`) والقيود (`limitations`).
- حساب `ROI` من مدخلات مُسجَّلة (`recorded inputs`) باستخدام نموذج المستودع (`shared/agent_assurance_roi.py`).

### الأيام 61–90: التكرار (`Repeatability`)
- تكرار مع **اثنين من العملاء غير المرتبطين** (`two unrelated customers`).
- قياس نسبة إعادة استخدام الأصول (`reusable test/policy/adapter %`)، التكلفة المباشرة (`direct cost`)، الهامش الإجمالي (`gross margin`)، الإيجابيات الكاذبة (`false positives`)، ووقت التسليم (`delivery time`).
- السعي لتجديد (`renewal`) أو اتفاقية مراقبة متكرّرة (`recurring monitoring agreement`).
- **قرار نهائي** (`build` · `narrow` · `service-only` · `stop`) من البوّابات (`gates`) — لا من الزخم السردي (`narrative momentum`).

> ⛔ **كل رقم سعر أو سوق يجب أن يحمل `PRICING HYPOTHESIS` أو `MARKET HYPOTHESIS`** (`L10` · `D-227`). الرقم بلا وسم يُقرأ بعد أسبوعين دليلاً — وهذا بالضبط ما يحرّمه الدستور.

---

## 8. الخلاصة — ما يعنيه «العمل الحقيقي» في هذا المستودع

«العمل الحقيقي» (`real work`) في سياق هذا المستودع لا يعني «كتابة مزيد من الكود». يعني:

1. **إنتاج دليل مُسجَّل (`recorded evidence`)**: عقد (`signed contract`)، دفعة (`payment`)، تجديد (`renewal`)، نسبة إعادة استخدام (`reuse %`)، هامش ربح (`gross margin`).
2. **إغلاق الفجوات المُعلَنة (`declared gaps`)**: `content_items` (من ٣ إلى بنك حقيقي)، `steps_json` (من فارغ إلى خطوات مُحقَّقة)، `billing_service` (من غائب إلى عقد `Chargily` + دفتر حركات)، `calibration` (من غائب إلى عيّنة بشرية + معامل اتّفاق).
3. **اجتياز بوّابات التمويل (`financing gates`)**: `GATE_0` (15 مقابلة) → `GATE_1` (3 عملاء مدفوعون) → `GATE_2` (70% + تجديد) → `GATE_3` (10 متكرّرون + احتفاظ).
4. **احترام القفل الأمني (`D-187`)**: `M33` (`program_synthesis`) لا يُفتَح قبل `M1→M4`. الصندوق (`sandbox`) مبنيّ لكن المستخدمون قاصرون (`minors`). القدرة (`capability`) دون أمان (`safety`) ليست منتجاً — هي حادثة مؤجَّلة.
5. **منع الخلط بين المسارات (`L1`)**: المُتحقِّق (`NAAS`) لا يستعير أدلة المنصّة التعليمية، والمنصّة لا تُعير أدلة تعلّمها للمُتحقِّق. كل مسار يُثبت نفسه.

> **النتيجة من المستودع نفسه (`AGENT_ACTION_ASSURANCE_INVESTMENT_CASE.md` §11):**
> «الموعود القابل للاستثمار ليس اليقين (`certainty`). إنه طريقة منضبطة (`disciplined method`) لتحويل الاستقلالية الآلية المتنامية (`expanding machine autonomy`) إلى بنية ثقة قابلة للقياس (`measurable, independent trust infrastructure`)، مع إنفاق رأس المال (`capital`) فقط بعد أن يكسب كل طبقة دليلها (`each layer earns its evidence`).»

---

## 9. مراجع الملفّات المباشرة لكل بند

| الموضوع | الملفّ الدقيق |
|---|---|
| خريطة المراحل التربوية | `.memory/roadmap.md` (`§4` · `§5` · `§4.4`) |
| الحالة الصادقة للمحرّك التربوي | `.memory/roadmap.md` (`§4` — جدول `M0`→`M11`) |
| حالة التحقّق `NAAS` | `.memory/naas_verification_truth.md` (`§2.a` · `§2.b` · `§2.c`) |
| الدستور الجديد (`L1`→`L10`) | `.memory/naas_verification_constitution.md` (`§3` · `§4`) |
| حالة الإيراد الصادقة | `.memory/revenue_engine_truth.md` (`§2.a` · `§2.b`) |
| عقيدة القيمة (`D-210`) | `docs/VALUE_DOCTRINE.md` (`§01` · `§02` · `§03`) |
| مواصفة الإيراد (`D-211`→`D-223`) | `docs/REVENUE_ENGINE_SPEC.md` (`§D-211` → `§D-223`) |
| حالة الاستثمار والبوابات | `docs/commercial/AGENT_ACTION_ASSURANCE_INVESTMENT_CASE.md` (`§2` · `§6` · `§9` · `§10` · `§11`) |
| معمارية التحكم المستهدفة | `docs/architecture/AGENT_TRUST_CONTROL_PLANE.md` (`§2` · `§5` · `§6` · `§10`) |
| خريطة علوم الحاسوب (`CS-1`→`CS-8`) | `.memory/roadmap.md` (`§4.4` · `docs/architecture/CS_KNOWLEDGE_MAP.md`) |
| القفل الأمني (`D-187` · `M33`) | `.memory/roadmap.md` (`§4.5` · `§4.8`) · `docs/architecture/COGNITIVE_EXECUTION_ENGINE.md` |
| حدّ المصداقية (`D-227`) | `.memory/naas_verification_constitution.md` (`§4.1` · `§4.2`) · `.memory/roadmap.md` (`§4.9` · `§4.8`) |
