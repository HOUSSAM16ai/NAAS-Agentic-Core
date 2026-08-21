# الحقيقة الحية: دستور D-274 (المهارات الأربع الإلزامية)

## الحالة (2026-08-21)
- الدستور **ساري ومدموج** في `docs/AGENT_WORKFLOW_CONSTITUTION.md` (إضافة لا حذف —
  قانون L7).
- المهارات الأربع منسوخة حرفيًا من mattpocock/skills (حقوق محفوظة) في
  `.claude/skills/`:
  - `grill-me/` — SKILL.md + grilling.md (البوابة L1: الاستجواب قبل التخطيط)
  - `to-spec/` — SKILL.md (البوابة L2: المواصفة قبل الكود)
  - `triage/` — SKILL.md + AGENT-BRIEF.md + OUT-OF-SCOPE.md + REPO-LABEL-MAP.md
    (البوابة L3: الفرز بآلة الحالات، مكيَّف بلاصقات المستودع في
    `docs/governance/REPOSITORY_GOVERNANCE_MODEL.md`)
  - `improve-architecture/` — SKILL.md + HTML-REPORT.md + codebase-design.md
    (البوابة L4: القياس قبل التعميق)
- الفارض المحلي `scripts/fitness/check_pocock_gates.py` يعمل: يتحقق من وجود
  المهارات الأربع وترويساتها (name/description وفق AGENT_SKILLS.json — قرار
  D-271) وسلامة مسرد اللاصقات.
- المهارات مدموجة أيضًا كـ agent_skills وفق AGENT_SKILLS.json (نظامان متمايزان
  معلنان — D-271، لا سُلَّم خفي).

## الفارض
- `scripts/fitness/check_pocock_gates.py` — أُضيف في guardrails من ci.yml
  (بانتظار صلاحية workflows للتوكن حتى يُرفع التعديل).

## القرارات المرتبطة
- D-274: دستور تدفق عمل الوكيل (إضافة لا حذف) — البوابات الأربع.
- لا تعارض مع D-273: D-273 يقرر الاستراتيجية، D-274 يقرر منهجية الإنتاج.
