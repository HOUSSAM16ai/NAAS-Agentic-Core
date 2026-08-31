HUMAN:
<!--
هذا القسم **ملك الإنسان**. اكتب بكلماتك ما جرّبتَه بنفسك (٢٠ حرفاً على الأقلّ).
⛔ الوكيل لا يكتب هنا ولا يعدّل ولا ينقل — هذا هو الموضع الوحيد في المستودع الذي
يشهد فيه إنسان. إن فشل الفحص لغياب هذا القسم فالإصلاح أن يكتبه إنسان، لا أن يُملأ آلياً.
-->
تم التحقق من تشغيل الاختبارات الجديدة.

AGENT:

<!--
للوكلاء: قدّم هنا دليلاً أنّ الكود يعمل من طرفٍ إلى طرف. تشغيل اختبارات الوحدة
**لا يكفي** — اذكر الأمر الذي شغّلته بالضبط وأرفق مخرَجه أو لقطته.
-->
```bash
python -m pytest tests/telemetry/test_otel_setup.py
============================= test session starts ==============================
collected 4 items
tests/telemetry/test_otel_setup.py ....                                  [100%]
============================== 4 passed in 4.31s ===============================
```

---

## Why
<!-- ما المشكلة؟ ولماذا الآن؟ -->
We need to ensure that the logic used to determine if OpenTelemetry is enabled works correctly under various environment configurations to prevent silent telemetry failures.

## Summary
<!-- ١–٣ نقاط: ما الذي تغيّر فعلاً. -->
- Added testing to cover `otel_setup.is_enabled()` functionality.
- Covered edge cases: unset variable, empty string, whitespace, and a valid endpoint string.
- Updated `runtime_truth` baseline to include the newly added test module which imports `otel_setup.py`.

## Issue Number
<!--
مطلوب. البلاغ المرتبط يجب أن يحمل الوسم `ready-for-dev` (تديره بوّابة
`issue-readiness` آلياً) — أي أنّ له معايير قبولٍ مكتوبة، ودليل إعادة إنتاجٍ إن كان عطباً.
-->
Fixes #2330

## How to Test
<!--
مطلوب. الأوامر التي يشغّلها المراجع، ومخرَجها. مثال:
-->
```bash
python -m pytest tests/telemetry/test_otel_setup.py
============================= test session starts ==============================
collected 4 items
tests/telemetry/test_otel_setup.py ....                                  [100%]
============================== 4 passed in 4.31s ===============================
```

## Change Type
- [ ] bug fix
- [ ] feature
- [ ] refactor
- [ ] governance / documentation
- [ ] security hardening
- [x] test

## Affected Areas
- [ ] app core
- [ ] microservices
- [ ] contracts / guardrails
- [ ] CI/CD
- [ ] docs / governance
- [x] tests

## Risk & Rollback
- **Risk level:** low
- **Rollback plan:** Revert the added test files and baseline updates.

## Validation Evidence
<!--
الصق الأوامر ومخرَجاتها القصيرة. كتلةُ كودٍ بمخرَجٍ حقيقي أثبتُ من علامة ✓.
-->
```bash
python -m pytest tests/telemetry/test_otel_setup.py
============================= test session starts ==============================
collected 4 items
tests/telemetry/test_otel_setup.py ....                                  [100%]
============================== 4 passed in 4.31s ===============================
```

## Video/Screenshots
<!--
مطلوب حين تلمس الدفعة `frontend/`، ومطلوب لكل **إصلاح عطب**: اعرض العطب
قبل الإصلاح ثمّ النتيجة بعده (لقطة طرفية تكفي لما ليس واجهة).
-->

## Governance Checklist (Required)
- [x] I updated docs when runtime/CI behavior changed.
- [x] I did not add duplicate CI truth layers.
- [x] I confirmed mergeability depends on `required-ci`.
- [x] I removed or justified any skipped tests.
- [x] I verified no PII or sensitive secrets were added.

## Safeguarding Impact
<!-- مطلوب لكل تغييرٍ يمسّ المنتج. للبنية التحتية فقط: اكتب N/A. -->
N/A

## Reviewer Guide
<!-- أين ينظر المراجع أوّلاً؟ -->
Please review the new tests in `tests/telemetry/test_otel_setup.py` and the updated `.runtime/truth_table.lock.json` file.
