# 📚 خريطة التوثيق الموحَّدة — Unified Documentation Map (D-156)

> **قاعدة السلطة الواحدة:** الحقيقة التشغيلية تعيش في مكانين فقط —
> **`CLAUDE.md`** (الدستور التشغيلي) و **`.memory/`** (الذاكرة المؤسسية، فهرسها `.memory/README.md`).
> كل ما في `docs/` **مرجع مساند** أو **أرشيف مُجمَّد**. عند أي تضارب: CLAUDE.md + `.memory/runtime_truth.md` يحسمان.

---

## 0) هرم السلطة (من يحسم ماذا؟)

| المستوى | المصدر | الدور |
|---------|--------|------|
| 🏛️ الدستور | `CLAUDE.md` | القوانين التشغيلية الدائمة + سجلّ العقائد §6.x (D-001→**D-189**). **لا يحمل حالات ولا سرداً مؤرَّخاً** (D-188) |
| 📐 مواصفة البرنامج | [`../spec.md`](../spec.md) | برنامج التبسيط API-first (Phases 0→12) — **الهدف** المعماري لا الحقيقة الجارية. ليست دستوراً ثالثاً: §4 تُحيل إلى الدستور القائم |
| 🧠 الذاكرة | `.memory/` → [`README.md`](../.memory/README.md) | roadmap · decisions · issues · runtime_truth · pedagogical_os |
| ⚖️ الدستور المعماري | [`architecture/MICROSERVICES_CONSTITUTION.md`](architecture/MICROSERVICES_CONSTITUTION.md) + [`ARCH_MICROSERVICES_CONSTITUTION.md`](ARCH_MICROSERVICES_CONSTITUTION.md) | حدود الخدمات |
| 📖 قواعد الوكلاء | [`../AGENTS.md`](../AGENTS.md) | قواعد التطوير + مشغّلات `ai_skills/` |
| 📄 مراجع مساندة | `docs/` (هذا الفهرس) | أدلة، عقود، ADRs |
| 🗄️ أرشيف مُجمَّد | [`archive/`](archive/README.md) | تقارير منتهية — لا تُستشهد كحقيقة |

---

## 1) البداية

| ملف | الدور |
|-----|------|
| [`START_HERE.md`](START_HERE.md) | نقطة البداية للمطورين الجدد |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | نظرة معمارية مبسطة (التفصيل الحيّ: CLAUDE.md §3) |
| [`REPOSITORY_MAP.md`](REPOSITORY_MAP.md) | خريطة المستودع |
| [`guides/BEGINNER_GUIDE.md`](guides/BEGINNER_GUIDE.md) · [`guides/NEWCOMER_CODEBASE_MAP.md`](guides/NEWCOMER_CODEBASE_MAP.md) | أدلة المبتدئين |
| [`guides/CODESPACES_TEST_GUIDE.md`](guides/CODESPACES_TEST_GUIDE.md) | العمل على Codespaces |

## 2) المعمارية والعقود

| ملف | الدور |
|-----|------|
| [`architecture/MICROSERVICES_CONSTITUTION.md`](architecture/MICROSERVICES_CONSTITUTION.md) | ⚖️ الدستور المعماري (عربي) |
| [`architecture/PRINCIPLES.md`](architecture/PRINCIPLES.md) | المبادئ المعمارية |
| [`architecture/adr/`](architecture/adr/) + [`adr/`](adr/) + [`adrs/`](adrs/) | سجلّات ADR (القرارات الحيّة في `.memory/decisions.md`) |
| [`architecture/`](architecture/) (runbooks: `MASTER_CUTOVER_RUNBOOK` · `PR1..PR5` · `LEGACY_*`) | كتيّبات هجرة الـ strangler-fig |
| [`architecture/CS_KNOWLEDGE_MAP.md`](architecture/CS_KNOWLEDGE_MAP.md) | 🗺️ خريطة علوم الحاسوب ↔ المشروع — عشرون مجالاً بحالةٍ ودليلٍ ملفّي، تحرسها `check_cs_knowledge_map` (D-207) |
| [`API_FIRST_ARCHITECTURE.md`](API_FIRST_ARCHITECTURE.md) | عقيدة API-First |
| [`architecture/EXTENSION_SEAMS.md`](architecture/EXTENSION_SEAMS.md) | مقاعد التوسّع (Kafka/VectorDB/RAG/Skill-flags) + الرؤية الثورية (D-173) |
| [`architecture/adr/006_polyglot_language_adoption.md`](architecture/adr/006_polyglot_language_adoption.md) | قرار تبنّي اللغات متعدّدة — **الحدّ هو العقد لا اللغة**؛ TypeScript مُتبنّىً، والتسع الباقيات مقاعد بشرط تبنٍّ (D-185) |
| [`contracts/`](contracts/) | عقود الـ API وقواعد الإصدار |
| [`OVERMIND_ARCHITECTURE.md`](OVERMIND_ARCHITECTURE.md) · [`architecture_map.md`](architecture_map.md) | خرائط الـ orchestrator |
| [`TYPE_SYSTEM.md`](TYPE_SYSTEM.md) · [`config/SETTINGS_LAYER.md`](config/SETTINGS_LAYER.md) · [`db/SESSION_FACTORY.md`](db/SESSION_FACTORY.md) · [`core/DEPENDENCY_LAYER.md`](core/DEPENDENCY_LAYER.md) · [`gateways/AI_GATEWAY.md`](gateways/AI_GATEWAY.md) | مراجع الطبقات |

## 3) التشغيل والنشر

| ملف | الدور |
|-----|------|
| [`DEPLOYMENT_GUIDE.md`](DEPLOYMENT_GUIDE.md) · [`MICROSERVICES_DEPLOYMENT_GUIDE.md`](MICROSERVICES_DEPLOYMENT_GUIDE.md) · [`MICROSERVICES_PLATFORM.md`](MICROSERVICES_PLATFORM.md) | النشر والتشغيل |
| [`WEBSOCKET_INFRASTRUCTURE.md`](WEBSOCKET_INFRASTRUCTURE.md) | بنية WebSocket + Troubleshooting (سلسلة D-WS-*) |
| [`migration/`](migration/) | كتيّبات خطوات الهجرة |
| [`advanced_knowledge_ingestion.md`](advanced_knowledge_ingestion.md) | خط إدخال المعرفة (RAG) |
| `../.memory/runbooks/` | ✳️ runbooks الحيّة (E2E Codespaces · Realtime recovery) |

## 4) الأمن والهوية والجودة

| ملف | الدور |
|-----|------|
| [`iam_architecture.md`](iam_architecture.md) · [`permission_matrix.md`](permission_matrix.md) · [`policy_gate.md`](policy_gate.md) · [`roles_and_boundaries.md`](roles_and_boundaries.md) · [`audit_and_privacy.md`](audit_and_privacy.md) · [`customer_chat_access.md`](customer_chat_access.md) | الهوية والصلاحيات |
| [`quality/standards.md`](quality/standards.md) · [`quality/testing.md`](quality/testing.md) · [`guides/TESTING_GUIDE.md`](guides/TESTING_GUIDE.md) | الجودة والاختبار |
| [`governance/REPOSITORY_GOVERNANCE_MODEL.md`](governance/REPOSITORY_GOVERNANCE_MODEL.md) | حوكمة المستودع |
| [`diagnostics/CUTOVER_SCOREBOARD.md`](diagnostics/CUTOVER_SCOREBOARD.md) | 🤖 لوحة القطع (مولَّدة آلياً — لا تُحرَّر يدوياً) |

## 5) مهارات الوكلاء (AI Skills)

[`ai_skills/`](ai_skills/) — مشغّلاتها مُعرَّفة في [`../AGENTS.md`](../AGENTS.md):
`bac-exercise-explanation` · `langgraph-agent-patterns` · `microservices-live-verification` ·
`fastapi-templates` · `database-schema-designer` · `python-performance-optimization` ·
`vercel-react-best-practices` · `web-design-guidelines` · `crafting-effective-readmes`

## 6) خارج النطاق الهندسي

| مجلد | المحتوى |
|------|---------|
| [`grant-program/`](grant-program/README.md) | 🎓 مواد برنامج المنحة (Theory of Change، الأثر، القوالب، `application/`، `toolkit/`) |
| [`archive/`](archive/README.md) | 🗄️ الأرشيف التاريخي المُجمَّد (108+ تقرير مؤرَّخ — D-156) |

---

## قواعد الإضافة (ملزِمة — تحرسها بوّابة `doc-integrity`)

1. معلومة تشغيلية قصيرة ⇒ `.memory/*.md` — **لا ملف MD جديد في `docs/`**.
2. قرار معماري ⇒ `.memory/decisions.md` + قسم CLAUDE.md §6.x.
3. تقرير مؤرَّخ/تشخيص منتهٍ ⇒ `docs/archive/<فئة>/` (البوّابة تفشل على `PHASE_*`/`ULTRA_*` خارج الأرشيف).
4. أي ملف جديد هنا ⇒ سطر في هذا الفهرس في نفس الـ PR.
