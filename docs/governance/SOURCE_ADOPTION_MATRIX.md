# Source Adoption Matrix

> This matrix enrolls every unique GitHub repository URL found in the project. It does not pretend that every URL is adopted. It makes uncertainty visible and blocks pending sources from becoming silent authority or runtime coupling.

**Total sources:** 62

| Status | Count | Rule |
|---|---:|---|
| `EXTERNAL_ABSENT` | 7 | Explicitly absent or rejected; cannot enter silently. |
| `EXTERNAL_ACTIVE` | 2 | Existing external-standard record marked ACTIVE; still governed by its registry. |
| `EXTERNAL_SEAM` | 2 | Explicit seam with no uncontrolled runtime adoption. |
| `MANDATORY_REFERENCE` | 15 | Pinned reference backbone; must be respected and locally traced. |
| `PENDING_CLASSIFICATION` | 36 | Existing URL requiring primary-source understanding before any new use. |

## Sources

| Source | Status | Purpose / current boundary | Local evidence |
|---|---|---|---|
| [https://github.com/ByteByteGoHq/system-design-101](https://github.com/ByteByteGoHq/system-design-101) | `MANDATORY_REFERENCE` | مرجع بصري مساعد لتدفقات الأنظمة والبروتوكولات | `docs/architecture`, `docs/contracts` |
| [https://github.com/CharlesQ9/Self-Evolving-Agents](https://github.com/CharlesQ9/Self-Evolving-Agents) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills) | `MANDATORY_REFERENCE` | فهرس مقارن لمهارات الوكلاء | `.claude/skills`, `docs/governance/AGENT_SKILLS.json`, `scripts/fitness/check_agent_skills_spec.py` |
| [https://github.com/EbookFoundation/free-programming-books](https://github.com/EbookFoundation/free-programming-books) | `MANDATORY_REFERENCE` | مكتبة تعلم وقراءة متعددة اللغات | `docs/guides`, `docs/research` |
| [https://github.com/Gatjuat-Wicteat-Riek/clean-code-book](https://github.com/Gatjuat-Wicteat-Riek/clean-code-book) | `MANDATORY_REFERENCE` | مرجع قراءة مساند للحرفية البرمجية | `docs/quality/standards.md` |
| [https://github.com/GoogleCloudPlatform/agent-starter-pack](https://github.com/GoogleCloudPlatform/agent-starter-pack) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/HOUSSAM16ai/NAAS-Agentic-Core](https://github.com/HOUSSAM16ai/NAAS-Agentic-Core) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/HOUSSAM16ai/my_ai_project](https://github.com/HOUSSAM16ai/my_ai_project) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/Houssam-lab/NAAS-Agentic-Core](https://github.com/Houssam-lab/NAAS-Agentic-Core) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/Houssam-lab/deepseek-harness](https://github.com/Houssam-lab/deepseek-harness) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/Houssam-lab/openhands](https://github.com/Houssam-lab/openhands) | `EXTERNAL_ACTIVE` | المصدر مسجل في سجل المعايير الخارجية؛ ارجع إلى `read_ar` و`adopted_ar` و`rejected_ar` قبل أي استعارة. | `.github/scripts`, `scripts/fitness/check_supply_chain.py` |
| [https://github.com/PyCQA/bandit](https://github.com/PyCQA/bandit) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/TheAlgorithms/Python](https://github.com/TheAlgorithms/Python) | `MANDATORY_REFERENCE` | أمثلة تنفيذية قابلة للفحص للخوارزميات وهياكل البيانات | `app/core/foundations`, `tests` |
| [https://github.com/ai-for-solution-labs/my_ai_project](https://github.com/ai-for-solution-labs/my_ai_project) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/anthropics/claude-cookbooks](https://github.com/anthropics/claude-cookbooks) | `EXTERNAL_ABSENT` | المصدر مسجل في سجل المعايير الخارجية؛ ارجع إلى `read_ar` و`adopted_ar` و`rejected_ar` قبل أي استعارة. | — |
| [https://github.com/anthropics/skills](https://github.com/anthropics/skills) | `EXTERNAL_ACTIVE` | المصدر مسجل في سجل المعايير الخارجية؛ ارجع إلى `read_ar` و`adopted_ar` و`rejected_ar` قبل أي استعارة. | `.claude/skills`, `docs/governance/AGENT_SKILLS.json` |
| [https://github.com/argoproj/argo-rollouts](https://github.com/argoproj/argo-rollouts) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/astral-sh/ruff-pre-commit](https://github.com/astral-sh/ruff-pre-commit) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/bakabala27-svg/NAAS-Agentic-Core](https://github.com/bakabala27-svg/NAAS-Agentic-Core) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/browser-use/browser-use](https://github.com/browser-use/browser-use) | `MANDATORY_REFERENCE` | مرجع بحثي لتفاعل الوكلاء مع المتصفح | `SECURITY.md`, `docs/architecture/AGENTIC_ORCHESTRATION_DOCTRINE.md` |
| [https://github.com/cert-manager/cert-manager](https://github.com/cert-manager/cert-manager) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/chalk/ansi-regex](https://github.com/chalk/ansi-regex) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/chalk/ansi-styles](https://github.com/chalk/ansi-styles) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/chalk/chalk](https://github.com/chalk/chalk) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/chalk/strip-ansi](https://github.com/chalk/strip-ansi) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/chalk/wrap-ansi](https://github.com/chalk/wrap-ansi) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/cncf/trailmap](https://github.com/cncf/trailmap) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/codecrafters-io/build-your-own-x](https://github.com/codecrafters-io/build-your-own-x) | `MANDATORY_REFERENCE` | التعلم عبر بناء المكونات من الصفر وفك الصناديق السوداء | `docs/research/authoritative-foundations.md`, `docs/architecture/EXTENSION_SEAMS.md` |
| [https://github.com/cogniforge/api-examples](https://github.com/cogniforge/api-examples) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/cordiverse/cordis](https://github.com/cordiverse/cordis) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/cursor/cookbook](https://github.com/cursor/cookbook) | `EXTERNAL_ABSENT` | المصدر مسجل في سجل المعايير الخارجية؛ ارجع إلى `read_ar` و`adopted_ar` و`rejected_ar` قبل أي استعارة. | — |
| [https://github.com/cursor/plugins](https://github.com/cursor/plugins) | `EXTERNAL_ABSENT` | المصدر مسجل في سجل المعايير الخارجية؛ ارجع إلى `read_ar` و`adopted_ar` و`rejected_ar` قبل أي استعارة. | — |
| [https://github.com/deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness) | `EXTERNAL_SEAM` | المصدر مسجل في سجل المعايير الخارجية؛ ارجع إلى `read_ar` و`adopted_ar` و`rejected_ar` قبل أي استعارة. | — |
| [https://github.com/donnemartin/system-design-primer](https://github.com/donnemartin/system-design-primer) | `MANDATORY_REFERENCE` | مرجع تصميم الأنظمة الموزعة والمقايضات المعمارية | `docs/architecture`, `docs/contracts` |
| [https://github.com/fb55/entities](https://github.com/fb55/entities) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/freeCodeCamp/freeCodeCamp](https://github.com/freeCodeCamp/freeCodeCamp) | `MANDATORY_REFERENCE` | مرجع تعليمي واسع لبناء المسارات الأساسية | `docs/guides`, `docs/START_HERE.md` |
| [https://github.com/github/github-mcp-server](https://github.com/github/github-mcp-server) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/google-gemini/cookbook](https://github.com/google-gemini/cookbook) | `EXTERNAL_ABSENT` | المصدر مسجل في سجل المعايير الخارجية؛ ارجع إلى `read_ar` و`adopted_ar` و`rejected_ar` قبل أي استعارة. | — |
| [https://github.com/google/A2UI](https://github.com/google/A2UI) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/google/adk-python](https://github.com/google/adk-python) | `EXTERNAL_SEAM` | المصدر مسجل في سجل المعايير الخارجية؛ ارجع إلى `read_ar` و`adopted_ar` و`rejected_ar` قبل أي استعارة. | — |
| [https://github.com/inikulin/parse5](https://github.com/inikulin/parse5) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/jwasham/coding-interview-university](https://github.com/jwasham/coding-interview-university) | `MANDATORY_REFERENCE` | تأسيس الخوارزميات وهياكل البيانات والتفكير التحليلي | `app/core/foundations`, `tests` |
| [https://github.com/kamranahmedse/developer-roadmap](https://github.com/kamranahmedse/developer-roadmap) | `MANDATORY_REFERENCE` | بوصلة المسار المعرفي وتحديد التخصصات والتبعيات | `docs/architecture/CS_KNOWLEDGE_MAP.md`, `docs/START_HERE.md` |
| [https://github.com/kserve/kserve](https://github.com/kserve/kserve) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/mattpocock/skills](https://github.com/mattpocock/skills) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/microsoft/api-guidelines](https://github.com/microsoft/api-guidelines) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/mozilla/diversity](https://github.com/mozilla/diversity) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/openai/openai-agents-python](https://github.com/openai/openai-agents-python) | `EXTERNAL_ABSENT` | المصدر مسجل في سجل المعايير الخارجية؛ ارجع إلى `read_ar` و`adopted_ar` و`rejected_ar` قبل أي استعارة. | — |
| [https://github.com/openai/openai-cookbook](https://github.com/openai/openai-cookbook) | `EXTERNAL_ABSENT` | المصدر مسجل في سجل المعايير الخارجية؛ ارجع إلى `read_ar` و`adopted_ar` و`rejected_ar` قبل أي استعارة. | — |
| [https://github.com/pgvector/pgvector](https://github.com/pgvector/pgvector) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/pre-commit/mirrors-mypy](https://github.com/pre-commit/mirrors-mypy) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/pre-commit/pre-commit-hooks](https://github.com/pre-commit/pre-commit-hooks) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/privatenumber/get-tsconfig](https://github.com/privatenumber/get-tsconfig) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/privatenumber/resolve-pkg-maps](https://github.com/privatenumber/resolve-pkg-maps) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/prometheus/prometheus](https://github.com/prometheus/prometheus) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/psf/black](https://github.com/psf/black) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
| [https://github.com/public-apis/public-apis](https://github.com/public-apis/public-apis) | `MANDATORY_REFERENCE` | كتالوج اكتشاف للتكاملات الخارجية | `docs/commercial/OFFER_CATALOG.json`, `docs/contracts` |
| [https://github.com/rasbt/LLMs-from-scratch](https://github.com/rasbt/LLMs-from-scratch) | `MANDATORY_REFERENCE` | مرجع فهم النماذج اللغوية ومكوّناتها | `shared/ai_models/model_chain.py`, `docs/architecture/AGENTIC_DESIGN_PRINCIPLES.md` |
| [https://github.com/ryanmcdermott/clean-code-javascript](https://github.com/ryanmcdermott/clean-code-javascript) | `MANDATORY_REFERENCE` | مرجع جودة الكود وقابلية القراءة في الواجهة | `frontend`, `.pre-commit-config.yaml` |
| [https://github.com/sindresorhus/awesome](https://github.com/sindresorhus/awesome) | `MANDATORY_REFERENCE` | فهرس اكتشاف المصادر والأدوات | `docs/research/authoritative-foundations.md`, `docs/commercial/OFFER_CATALOG.json` |
| [https://github.com/xai-org/grok-build](https://github.com/xai-org/grok-build) | `EXTERNAL_ABSENT` | المصدر مسجل في سجل المعايير الخارجية؛ ارجع إلى `read_ar` و`adopted_ar` و`rejected_ar` قبل أي استعارة. | — |
| [https://github.com/yaml/pyyaml](https://github.com/yaml/pyyaml) | `PENDING_CLASSIFICATION` | لم يُستخرج الغرض بعد من مصدر أولي؛ لا يجوز للوكيل افتراضه من اسم الرابط أو موضعه فقط. | — |
