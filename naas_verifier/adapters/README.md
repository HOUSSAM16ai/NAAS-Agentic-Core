# عقد المُهايئ — كيف توجّه المُتحقِّق إلى حارسك أنت

> **من هذا الملفّ؟** مهندسٌ خارج هذا المستودع يريد قياس **نظامه هو** بهذا المُتحقِّق.
> `multilingual_probe.py` مُهايئُنا نحن لذخيرتنا نحن؛ وهذه الصفحة هي الواجهة الدنيا
> التي تكتبها لتصير الأداة تقيس نظامك بدل أن تعرض مستودعنا.

---

## 1. الفكرة في سطر

أنت تُترجم **تشغيلاً حقيقياً لنظامك** إلى `Trajectory`، وتُعلن ما **يجب** أن يصحّ
عنه في `ConstraintSet`. والمُتحقِّق يفعل الباقي.

```python
from naas_verifier.core.trajectory import Step, Trajectory
from naas_verifier.core.constraint import Constraint, ConstraintSet, Dimension, Outcome
from naas_verifier.core.verdict import verify

verdict = verify(my_trajectory, my_constraints)
print(verdict.outcome, verdict.violated_dimensions)
```

⛔ **مكتبة قياسية فقط.** الحزمة صفر-شبكة وصفر-تبعية بحكم بوّابة
`check_naas_verifier_boundary`. نظامُك يعمل عندك، وأنت تُدخِل **ما رصدتَه** — لا
يتّصل المُتحقِّق بشيء.

---

## 2. `Trajectory` — ما رصدتَه فعلاً، لا ما تظنّه

```python
Trajectory(
    trajectory_id="my-system/case-17",
    language="ar",              # إلزامي — مسارٌ بلا لغة لا يُقارَن بأساسٍ لغوي
    steps=[
        Step(
            index=0,
            action="operator registers a policy rule",
            state_before="policy_empty",
            state_after="policy_registered",
            tool="load_rules",              # None لخطوةٍ بلا أداة
            tool_args={"rules": ["..."]},
            output="accepted",              # المخرَج **المرصود**
        ),
        # …
    ],
    final_output="…",
    metadata={"build": "…"},
)
```

**القواعد التي يفرضها النوع نفسه** (ترفع `TrajectoryError`، ولا تمرّ صامتة):
`index ≥ 0` · `action` غير فارغ · `state_before`/`state_after` غير فارغين ·
`tool` إمّا `None` وإمّا اسمٌ حقيقي (⛔ لا سلسلة فارغة) · الخطوات مرتّبةٌ بـ`index`.

⚠️ **`state_before`/`state_after` ليسا زينة.** هما ما يجعل بُعد `state_transitions`
قابلاً للفحص أصلاً. سمِّ حالاتٍ حقيقيةً في نظامك، لا `"start"`/`"end"`.

---

## 3. `ConstraintSet` — والقاعدة التي تجعله مُتحقِّقاً لا مُصحِّحاً

الأبعاد **خمسة**، ولا مفرّ:

| البُعد | يجيب عن |
|---|---|
| `OBSERVABLE_OUTCOMES` | هل ما رُصد فعلاً سليم؟ |
| `INTERMEDIATE_CONSTRAINTS` | هل صحّ ما **يجب** أن يصحّ في الطريق؟ |
| `STATE_TRANSITIONS` | هل الانتقالات مشروعة؟ |
| `TOOL_USE` | هل استُعملت الأدوات الصحيحة بالترتيب الصحيح؟ |
| `FINAL_OUTCOME` | هل النتيجة النهائية صحيحة؟ |

⛔ **بُعدٌ لا تغطّيه يجب أن تُصرِّح بسببه** — وإلّا رفض `ConstraintSet` البناءَ من
أصله:

```python
ConstraintSet(
    constraints=(...),
    uncovered_reason={
        Dimension.TOOL_USE: "نظامي بلا أدوات — نداءُ دالّةٍ واحد",
    },
)
```

⚠️ **ولماذا هذا القيد بالذات:** مجموعةٌ تغطّي `FINAL_OUTCOME` وحده **لا تستطيع
بنيوياً** أن تُرجِع `HOLDS` — تُرجِع `INCONCLUSIVE`. فحصُ النتيجة وحدها **تصحيحٌ لا
تحقّق**، والعقيدة مُرمَّزةٌ في النوع لا موصوفةٌ في نثر (D-267 L3). والخانة الفارغة
تُقرأ نجاحاً، فالسبب **منطوقٌ إجبارياً** (D-206 L11).

---

## 4. `Constraint` — والسبب في أنّها تُرجِع `Outcome` لا `bool`

```python
def _rule_is_enforceable(trajectory: Trajectory) -> Outcome:
    registered = any(step.output == "accepted" for step in trajectory.steps)
    fired = any(step.output == "fired" for step in trajectory.steps)
    if not registered:
        return Outcome.INCONCLUSIVE     # لم يُسجَّل شيء ⇒ لا أعرف
    return Outcome.HOLDS if fired else Outcome.VIOLATED

Constraint(
    constraint_id="intermediate/rule-enforceable",
    dimension=Dimension.INTERMEDIATE_CONSTRAINTS,
    description="a rule the system accepted must actually be enforceable",
    predicate=_rule_is_enforceable,
)
```

⛔ **`bool` ممنوع عمداً.** القيد الذي لا يستطيع الحكم يجب أن **يقول ذلك**: `False`
تُقرأ انتهاكاً و`True` تُقرأ سلامة، وكلتاهما كذبٌ حين تكون الحقيقة «لا أعرف»
(D-215).

⚠️ وأيّ استثناءٍ غير متوقّع داخل `predicate` يصير `INCONCLUSIVE` **لا** `HOLDS` —
بوّابةٌ تشهد بما لم تقرأ هي بالضبط ما حرّمه D-208.

---

## 5. قاعدة الحسم

انتهاكٌ واحد في أيّ بُعد ⇒ `VIOLATED`. ولا انتهاك لكن بقي بُعدٌ غير حاسم ⇒
`INCONCLUSIVE`. ⛔ **ولا يُرقّى `INCONCLUSIVE` إلى نجاحٍ أبداً.**

والأبعاد تُقيَّم **كلّها** دائماً — لا «أوّل يفوز»: كل بُعدٍ يُسجَّل حتى لو سبقه
انتهاك، وإلّا فقد قارئُ التقرير نصفَ ما يحتاجه للتشخيص.

---

## 6. مثالٌ عامل تقرؤه كاملاً

`scripts/research/probe_external_guard.py` يفعل بالضبط ما تصفه هذه الصفحة على حارسٍ
**خارجيّ مفتوح المصدر**: يرصد سلوكه الحقيقي، يبني `Trajectory`، يُعلن الأبعاد الخمسة،
ويُخرِج `Verdict`. اقرأه كقالب.

---

## 7. ⛔ حدودٌ تُقال قبل أن تُكتشَف

- **المُتحقِّق لا يولّد الهجوم.** يقيس مساراً أعطيتَه إيّاه. توليدُ المُدخَلات مسؤوليتك
  (أو مسؤولية بيئة `envs/`).
- **جودةُ قيودك سقفُ جودة الحكم.** قيدٌ ضعيف يُعطي `HOLDS` رخيصة — والأداة لا تستطيع
  أن تعرف أنّك لم تفحص ما يهمّ. لا فارضَ آليّ لهذا، ويُقال صراحةً.
- **ذخيرتنا ليست ذخيرتك.** الأصناف في `corpus/` مُشتَقّة من أرشيف حوادثنا نحن، وبعضها
  محجوبٌ عن النشر ما دام مصدرُه مفتوحاً.
