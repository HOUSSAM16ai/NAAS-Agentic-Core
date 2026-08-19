# الحالة الحيّة — دستور معايير الوكلاء المفتوحة (D-271)

> **القانون** في [`docs/architecture/OPEN_AGENT_STANDARDS.md`](../docs/architecture/OPEN_AGENT_STANDARDS.md).
> ⚠️ حالة كلّ مصدرٍ خارجي **تُشتَقّ** من
> [`EXTERNAL_STANDARDS_REGISTRY.json`](../docs/governance/EXTERNAL_STANDARDS_REGISTRY.json)،
> وحالة تقييم المهارات من
> [`AGENT_SKILLS.json`](../docs/governance/AGENT_SKILLS.json) — لا تُنسَخ هنا (D-192).

**آخر تحقّقٍ حيّ:** 2026-08-19 · وجود المستودعات الأحد عشر مُثبَتٌ بـ`git ls-remote`.

## حالة القوانين

| القانون | الحالة | الفارض | الفجوة |
|---|---|---|---|
| L9 المعيار المفتوح | **ACTIVE** | `check_agent_skills_spec.py` | لا مهارة تحمل `license` بعد؛ الحقل مسموحٌ لا إلزامي |
| L10 كلمةٌ بمعنيين مُعلَنين | **ACTIVE** | نفس البوّابة + `AGENT_SKILLS.json:glossary_ar` | — |
| L11 الساق السادسة | **PARTIAL** | نفس البوّابة | **لا مهارة مُقيَّمة بعد** — كلّها مُصنَّفة `unevaluated` بسببٍ منطوق. هذا صدقٌ لا إنجاز: القانون يمنع ادّعاء القياس، ولا يُنتج قياساً |
| L12 التبنّي بقرارٍ مكتوب | **ACTIVE** | `check_external_standards.py` | — |

## المصادر الخارجية — ما قُرئ فعلاً

| المصدر | قُرئ؟ | الحالة |
|---|---|---|
| `Houssam-lab/openhands` | **نعم** (نسخة سطحية كاملة) | ACTIVE — منه D-270 كلّه |
| `anthropics/skills` | **نعم** (spec · template · skill-creator) | ACTIVE — منه L9/L10/L11 |
| `google/adk-python` | **نعم** (وحدة evaluation) | SEAM بصفر كود |
| `deepseek-ai/deepseek-harness` | لا — وجودٌ مُتحقَّق فقط | SEAM (ADR-010 · قفل D-187) |
| `openai/openai-agents-python` | لا | ABSENT — تكافؤٌ مُعلَن |
| `xai-org/grok-build` | لا | ABSENT — قفل D-187 |
| `cursor/plugins` | لا | ABSENT — معلّقٌ على مصير `plugin_loader.py` |
| الكتب الأربعة (openai · claude · gemini · cursor) | لا | ABSENT — أمثلةٌ لا معايير |

## دَينٌ مُعلَن

- **صفر مهارة مُقيَّمة.** بناء حزمة تقييمٍ فعلية (على نمط `skill-creator`) عملٌ قائم
  بذاته؛ وحتى ذلك تبقى الحالة `unevaluated` مُصرَّحةً ولا يُدَّعى قياس.
- **`app/core/registry/plugin_loader.py` ZOMBIE** (موجودٌ بلا مستورِدٍ حيّ). قرار
  D-173 يقضي بالحذف أو التوصيل، ويحتاج ADR — وهو شرط ترقية صفّ `cursor/plugins`.
