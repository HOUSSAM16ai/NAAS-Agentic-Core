# 🗄️ الأرشيف التاريخي — Frozen History (D-156)

> **هذا المجلد سجلّ تاريخي مُجمَّد.** لا يُستشهد به كحقيقة تشغيلية، ولا يُحدَّث.
> الحقيقة الحيّة الوحيدة: **`CLAUDE.md`** (العقد التشغيلي) + **`.memory/`** (الذاكرة المؤسسية).

## لماذا يوجد هذا الأرشيف؟

سياسة توحيد التوثيق (CLAUDE.md §15 + D-156): كل معلومة تشغيلية تعيش في `.memory/*.md`؛
التقارير المؤرَّخة والتشخيصات المنتهية تُؤرشف هنا لتقليل الضجيج ومنع تضارب الحقائق —
دون فقدان أي معلومة (نُقلت بـ `git mv`، التاريخ الكامل محفوظ في git).

## الفهرس

| المجلد | المحتوى | البديل الحيّ |
|--------|---------|--------------|
| `diagnostics/` | تشخيصات جنائية مؤرَّخة (ULTRA_*, FORENSIC_*, …) | `.memory/issues.md` |
| `forensics/` | تقارير super-agent runtime الجنائية | `.memory/runtime_truth.md` |
| `reports/` | تقارير حالة/تسليم/تحليل قديمة | `.memory/progress.md` + `.memory/context.md` |
| `audits/` | تدقيقات API-First ومهام الوكلاء | `.memory/decisions.md` |
| `plans/` | خطط تنفيذ منتهية | `.memory/roadmap.md` |
| `phase-reports/` | تقارير المراحل 18/19 | `.memory/roadmap.md` §4 |
| `api-first/` | إثباتات/ملخصات API-First التاريخية | `docs/API_FIRST_ARCHITECTURE.md` |
| `cs-guides/` | أدلة CS51/CS61/CS73 التعليمية القديمة | `docs/guides/` |
| `solid/` | تدقيقات SOLID الأساسية | `docs/quality/standards.md` |
| `one-off/` | إصلاحات/تحليلات لمرة واحدة | `.memory/decisions.md` |
| `architecture-forensics/` | تشخيصات معمارية منتهية (Context-Blindness, …) | CLAUDE.md §6.x + `.memory/architecture.md` |
| `root-reports/` | ملفات جذر المستودع القديمة (Blueprint, ROADMAP القديم, …) | `.memory/roadmap.md` + CLAUDE.md |

## قاعدة ملزِمة

**ممنوع** إضافة توثيق جديد هنا مباشرةً — الأرشفة تمرّ عبر PR يُحدِّث
`docs/DOCUMENTATION_INDEX.md` ويحترم بوّابة `doc-integrity` (المُشدَّدة منذ D-156).
