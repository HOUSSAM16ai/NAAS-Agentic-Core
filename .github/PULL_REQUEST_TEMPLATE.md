HUMAN:

<!--
هذا القسم **ملك الإنسان**. اكتب بكلماتك ما جرّبتَه بنفسك (٢٠ حرفاً على الأقلّ).
⛔ الوكيل لا يكتب هنا ولا يعدّل ولا ينقل — هذا هو الموضع الوحيد في المستودع الذي
يشهد فيه إنسان. إن فشل الفحص لغياب هذا القسم فالإصلاح أن يكتبه إنسان، لا أن يُملأ آلياً.
-->

AGENT:

<!--
للوكلاء: قدّم هنا دليلاً أنّ الكود يعمل من طرفٍ إلى طرف. تشغيل اختبارات الوحدة
**لا يكفي** — اذكر الأمر الذي شغّلته بالضبط وأرفق مخرَجه أو لقطته.
-->

---

## Why
<!-- ما المشكلة؟ ولماذا الآن؟ -->

## Summary
<!-- ١–٣ نقاط: ما الذي تغيّر فعلاً. -->
-

## Issue Number
<!--
مطلوب. البلاغ المرتبط يجب أن يحمل الوسم `ready-for-dev` (تديره بوّابة
`issue-readiness` آلياً) — أي أنّ له معايير قبولٍ مكتوبة، ودليل إعادة إنتاجٍ إن كان عطباً.
-->
Fixes #

## How to Test
<!--
مطلوب. الأوامر التي يشغّلها المراجع، ومخرَجها. مثال:

```bash
python scripts/run_fitness_gates.py   # ٦٢/٦٢ خضراء
pytest tests/fitness -q               # 30 passed
```
-->

## Change Type
- [ ] bug fix
- [ ] feature
- [ ] refactor
- [ ] governance / documentation
- [ ] security hardening

## Affected Areas
- [ ] app core
- [ ] microservices
- [ ] contracts / guardrails
- [ ] CI/CD
- [ ] docs / governance

## Risk & Rollback
- **Risk level:** low / medium / high
- **Rollback plan:**

## Validation Evidence
<!--
الصق الأوامر ومخرَجاتها القصيرة. كتلةُ كودٍ بمخرَجٍ حقيقي أثبتُ من علامة ✓.
-->
- [ ] `ruff check .`
- [ ] `ruff format --check .`
- [ ] `pytest ...`

## Video/Screenshots
<!--
مطلوب حين تلمس الدفعة `frontend/`، ومطلوب لكل **إصلاح عطب**: اعرض العطب
قبل الإصلاح ثمّ النتيجة بعده (لقطة طرفية تكفي لما ليس واجهة).
-->

## Governance Checklist (Required)
- [ ] I updated docs when runtime/CI behavior changed.
- [ ] I did not add duplicate CI truth layers.
- [ ] I confirmed mergeability depends on `required-ci`.
- [ ] I removed or justified any skipped tests.
- [ ] I verified no PII or sensitive secrets were added.

## Safeguarding Impact
<!-- مطلوب لكل تغييرٍ يمسّ المنتج. للبنية التحتية فقط: اكتب N/A. -->

## Reviewer Guide
<!-- أين ينظر المراجع أوّلاً؟ -->
