# الحالة الحية — دستور التقنية العميقة والعملة الصعبة (D-273)

> **وثيقة حالة.** القانون في [`docs/DEEP_TECH_CONSTITUTION.md`](../docs/DEEP_TECH_CONSTITUTION.md).
> القاعدة (D-266): القانون لا يحمل حالة، والحالة لا تحمل قانونًا — كل سطر هنا قابل
> للتحقق من القرص والـCI، والفارض `check_deep_tech_constitution.py` يشهد على وجودها.

## جدول الحالة — الخطوط السبعة

| # | الخط | الحالة الحالية | الدليل على القرص |
|---|------|----------------|------------------|
| 1 | AI Red Teaming (عربي/فرنسي) | `PROPOSED` | لا كود ولا عقد — قرار المالك في هذه الوثيقة وحدها |
| 2 | Niche RLHF (فقه/قانون/طبي فرنسي) | `PROPOSED` | لا كود ولا عقد |
| 3 | On-Premise AI لقطاع الطاقة الخليجي | `PROPOSED` | لا كود ولا عقد |
| 4 | PINNs صناعي | `PROPOSED` | لا كود ولا عقد |
| 5 | Formal Verification لكود الذكاء الاصطناعي | `PROPOSED` | لا كود ولا عقد — لكن المستودع يملك بنية تحقّق (`docs/architecture/NAAS_VERIFICATION_LAYER.md`, D-267) يمكن البناء عليها |
| 6 | EU AI Act B2B SaaS | `PROPOSED` | لا كود ولا عقد — البنية التحتية للامتثال (`docs/governance/`) يمكن إعادة توجيهها لهذا الخط |
| 7 | High-RPM AI Affiliation | `PROPOSED` | لا كود ولا عقد |

⚠️ **لا يُعلَن أي خط `ACTIVE` دون دليلٍ حيّ** (عقد موقع/دفعة مستلمة/اشتراك مدفوع
موثق في هذا الملف بصيغته القابلة للتدقيق). إعلانٌ بلا دليل ⇒ CI أحمر عند تشغيل
`check_deep_tech_constitution.py`.

## الملاحظات التشغيلية

- القرار D-273 أُدرج في `.memory/decisions.md` بتاريخ 2026-08-21 بصيغة «إضافة لا
  حذف».
- السجل الدستوري `docs/governance/CONSTITUTION_REGISTRY.json` يحمل صف D-273 (قسم
  0.25) بعد دمج القرار.
- الفارض `scripts/fitness/check_deep_tech_constitution.py` سُلك في
  `.github/workflows/ci.yml` ضمن `guardrails`.
- خط السقف `CLAUDE_MD_MAX_LINES` لم يتغير (القسم §0.25 أُضيف بضغط ما يعادله داخل
  القسم نفسه حيث أمكن — انظر D-273 في `decisions.md`).
