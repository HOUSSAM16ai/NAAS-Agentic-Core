# الحالة الحيّة — دستور معايير التسليم (D-270)

> **القانون** في [`docs/architecture/DELIVERY_STANDARDS.md`](../docs/architecture/DELIVERY_STANDARDS.md).
> هذا الملفّ يحمل **الحالة** وحدها (فصلٌ إلزامي — D-188/D-209).
> ⚠️ الأعداد المتحرّكة **تُشتَقّ** من سجلّاتها ولا تُكتب هنا (D-192): سجلّ البراهين
> `docs/governance/NEGATIVE_PROOFS.json` · دَين التثبيت `SUPPLY_CHAIN.json` ·
> دَين الحرفيات `MAGIC_STRINGS.json`.

**آخر تحقّقٍ حيّ:** 2026-08-19 · `python3.12 scripts/run_fitness_gates.py` → كل البوّابات خضراء.

## حالة القوانين

| القانون | الحالة | الفارض | ما يبقى |
|---|---|---|---|
| L1 الدليل قبل الدمج | **ACTIVE** | `.github/scripts/validate_pr_description.py` | فحصُ وسم البلاغ يتطلّب `GITHUB_TOKEN`؛ محلياً يُبلَّغ ولا يُفشِل |
| L2 جاهزية البلاغ | **ABSENT (البلاغات مُعطَّلة)** | `.github/scripts/validate_issue_readiness.py` | ⚠️ **مقيس 2026-08-19**: البلاغات مُعطَّلة في المستودع (`410 Issues has been disabled`)، فلا `issue-readiness` يعمل ولا يجوز مطالبة أحدٍ بـ`Fixes #N`. القاعدة **مربوطة بالواقع**: `_issues_enabled` تُعطّلها وتعيدها تلقائياً لحظة تفعيل البلاغات — لا برأي. **شرط الترقية:** تفعيل Issues في إعدادات المستودع. |
| L3 عنوان الدفع عقد | **ACTIVE** | بندٌ في `validate_pr_description.py` | — |
| L4 البوّابة تُثبِت أنّها تحجب | **PARTIAL** | `scripts/fitness/check_gate_negative_proof.py` | دَينٌ مُعلَن يتقلّص — العدد في `NEGATIVE_PROOFS.json` |
| L5 الحرفية السحرية | **PARTIAL** | `scripts/fitness/check_no_magic_strings.py` | دَينٌ مُجمَّد يتقلّص — القائمة في `MAGIC_STRINGS.json` |
| L6 سلسلة التوريد | **PARTIAL** | `scripts/fitness/check_supply_chain.py` | التبريد والتوصيف ACTIVE؛ دَين التثبيت في `SUPPLY_CHAIN.json` |
| L7 الفارض المحلّي | **ACTIVE** | `check_governance_registry.py` · `local_enforcers` | دَينٌ محلّي فارغ |
| L8 حدّ المصداقية على المُشحَن | **ACTIVE** | `scripts/fitness/check_config_credibility.py` | توحيد القوائم الثلاث في مصدرٍ واحد يتطلّب ADR (التباين مُسجَّل في `CREDIBILITY_LIMIT.json`) |

## ما أُصلح بالقياس في دفعة الميلاد

- `.github/dependabot.yml`: مجلّدٌ غير موجود · مجموعات حزمٍ غير مستعملة · `frontend/`
  بلا تغطية · مفاتيح مُهمَلة · صفر تبريد → أُعيدت كتابته.
- `.pre-commit-config.yaml`: مُنسِّقٌ ثانٍ يناقض CI · مُرتِّب استيراداتٍ مُكرَّر ·
  خطّاف `mypy` يخرج بالرمز 2 قبل فحص سطر → صار مرآةً لـCI.
- `Makefile`: أعلن عن **خمس وثائق غير موجودة** → صُحِّح.
- `.trivy.yml` · `.semgrep.yml` · `.github/copilot-instructions.md` · `ci.yml`:
  ادّعاءات غير قابلة للتفنيد → أُزيلت.

## دَينٌ مُعلَن (لا يُقرأ نجاحاً)

- **البلاغات مُعطَّلة في المستودع** ⇒ L2 بلا مرمى فعلي، و`issue-readiness.yml` لا
  يُستدعى أبداً. أُبقي الفارض ولم يُحذَف لأنّ الحذف يعني فقدان القانون عند تفعيل
  البلاغات؛ والحالة **مُصرَّحة** هنا ولا تُقرأ نجاحاً (D-206 L11).

- **`tools/simplicity_validator.py` غير موجود** بينما `make simplicity-validate`
  يستدعيه → الهدف يفشل. لم يُحذَف الهدف في هذه الدفعة لأنّ حذف أهداف `Makefile`
  خارج نطاق L8؛ القرار (يُوصَل أم يُحذَف — D-173) مُعلَّق ومُسجَّل هنا.
- **توحيد قوائم العبارات غير القابلة للتفنيد** (ثلاث بوّابات) مؤجَّل بقرارٍ مكتوب:
  كلّ توسعةٍ في قائمةٍ قد تُفشِل وثيقةً قائمة، والتباين مُسجَّل ومحروسٌ بالتكافؤ.
