"""سلطة الموضوع — الحاسم الوحيد لسؤال «هل هذا السؤال من الاحتمالات؟» (D-266 · ISS-159).

## الكارثة التي وُلد منها هذا الملفّ

بلاغ المالك (ISS-159): «النظام يتعامل مع كل سؤال كأنه تمرين احتمالات، مع أنّنا نهدف
لإضافة الفيزياء وعلوم الطبيعة والرياضيات وSTEM ومليارات التمارين.»

والجذر لم يكن في الكشف — بل في **بنية الحارس نفسه**. الصيغة، حرفياً، في **ستّة** مواضع:

```python
_canonical = primary_canonical_topic(question)
if _canonical is not None and _canonical.canonical_id != "probability":
    return None          # ← لا يُنفَّذ أبداً لسؤال فيزياء
```

و`CANONICAL_TOPICS` (في `arabic_normalize.py`) تعرف **ثلاثة مواضيع رياضية فقط**:
`complex_numbers` · `probability` · `numerical_functions`. صفر فيزياء، صفر علوم. فسؤال
«اشرح لي قانون أوم» يُرجِع `None`، والشرط يسقط عند **ساقه الأولى**، فلا يعمل الحارس
أصلاً ويمضي السؤال إلى العقل الاحتمالي.

بينما `shared/curriculum` يحمل **٣٧** مفهوماً عبر ثلاث مواد (D-193) — **ولم يكن مسار
الدور يستورده إطلاقاً**. أي أنّ مكسب D-193 لم يصل الموجِّه أبداً.

## القانون الذي يُرسيه هذا الملفّ

> **غيابُ الموضوع من سجلّ الاسترجاع ليس إذناً بالاحتمالات. إشارةُ مادةٍ موجبة تجعل
> السؤال أجنبياً عن الاحتمالات بالبناء.**

وهو امتدادٌ مباشر لقاعدة D-191: «السقوط إلى التمرين المرجعي يتطلّب **إشارة احتمالية
موجبة**؛ غيابُ موضوعٍ آخر ليس دليلاً». هنا نفس المنطق معكوساً على الموضوع.

## عقد الموقع

- **حاسمٌ واحد**: `is_foreign_to_probability` هو المُسنَد الوحيد؛ نسخةٌ سابعة من الصيغة
  المكسورة تُفشِل `scripts/fitness/check_topic_authority_single_source.py`.
- **صفر LLM · حتمي**: قرارُ الموضوع لا يُسأل عنه نموذج (§0.5 — الحقيقة من المحرّكات).
- **fail-open**: أيّ عطبٍ في الاستيراد يُرجِع «غير أجنبي» فلا يُكسَر دور الطالب — الحارس
  يضيّق ولا يمنع.
"""

from __future__ import annotations

from dataclasses import dataclass

#: المُعرَّف القانوني لموضوع الاحتمالات في سجلّ الاسترجاع (`CANONICAL_TOPICS`).
PROBABILITY_CANONICAL_ID = "probability"

#: مفاهيم المنهاج (D-193) التي تنتمي إلى عائلة الاحتمالات. تُقرأ من `shared/curriculum`
#: ولا تُعاد كتابتها: هذه أسماءُ مفاهيم مُعلَنة هناك، والقائمة هنا **انتقاءٌ منها** لا
#: تعريفٌ ثانٍ لها (بوّابة `check_topic_authority_single_source` تتحقّق أنّ كلّ مُعرَّف
#: هنا موجودٌ في السجلّ القانوني).
PROBABILITY_CONCEPT_IDS: frozenset[str] = frozenset(
    {
        "probability",
        "conditional_probability",
        "combinations",
        "permutations",
        "random_variable",
        "statistics",
        "product_zero",
        "product_odd",
        "product_even",
    }
)


@dataclass(frozen=True)
class TurnTopic:
    """حكمُ الموضوع على نصّ دورٍ واحد — بمصدر الحكم، فلا يُقرأ اليقين حيث لا يقين."""

    #: `mathematics` · `physics` · `natural_sciences` · أو `None` إن لم يُتعرَّف.
    subject: str | None
    #: مُعرَّف مفهوم المنهاج (D-193) إن وُجد.
    concept_id: str | None
    #: مُعرَّف موضوع الاسترجاع (`CANONICAL_TOPICS`) إن وُجد.
    canonical_id: str | None
    #: من حسم: `"canonical"` · `"curriculum"` · `"subject_marker"` · `"none"`.
    source: str

    @property
    def is_probability(self) -> bool:
        """هل الموضوع احتمالاتٌ **بإشارة موجبة**؟ الغياب ليس إثباتاً."""
        if self.canonical_id == PROBABILITY_CANONICAL_ID:
            return True
        return self.concept_id in PROBABILITY_CONCEPT_IDS

    @property
    def is_identified(self) -> bool:
        return self.source != "none"


_UNKNOWN = TurnTopic(subject=None, concept_id=None, canonical_id=None, source="none")


def resolve_turn_topic(text: str) -> TurnTopic:
    """
    يحسم موضوع النصّ من **مصدرين مُرتَّبين**، ولا يخترع ثالثاً.

    ١. `CANONICAL_TOPICS` (سجلّ الاسترجاع) — الأخصّ عملياً: يقرّر أيّ تمرينٍ يُجلَب.
    ٢. `shared/curriculum` (السجلّ القانوني للمفاهيم والمواد، D-193) — يعرف الفيزياء
       والعلوم التي لا يعرفها الأوّل.

    الترتيب مقصود: حين يتّفقان لا فرق، وحين ينفرد الأوّل بالحكم فهو الأقرب إلى قرار
    الاسترجاع، وحين يصمت يتكلّم الثاني — وهذا هو **بالضبط** ما كان غائباً في ISS-159.
    """
    if not text or not text.strip():
        return _UNKNOWN

    canonical_id: str | None = None
    try:
        from app.services.capabilities.arabic_normalize import primary_canonical_topic

        canonical = primary_canonical_topic(text)
        canonical_id = getattr(canonical, "canonical_id", None)
    except Exception:  # pragma: no cover - fail-open: الموضوع لا يكسر الدور
        canonical_id = None

    concept_id: str | None = None
    subject: str | None = None
    try:
        from shared.curriculum import classify, classify_subject

        concept_id = classify(text)
        subject = classify_subject(text)
    except Exception:  # pragma: no cover - fail-open
        concept_id = None
        subject = None

    if canonical_id is not None:
        return TurnTopic(
            subject=subject or "mathematics",
            concept_id=concept_id,
            canonical_id=canonical_id,
            source="canonical",
        )
    if concept_id is not None:
        return TurnTopic(
            subject=subject, concept_id=concept_id, canonical_id=None, source="curriculum"
        )
    if subject is not None:
        return TurnTopic(
            subject=subject, concept_id=None, canonical_id=None, source="subject_marker"
        )
    return _UNKNOWN


def is_foreign_to_probability(text: str) -> bool:
    """
    هل هذا النصّ **أجنبيٌّ عن الاحتمالات بإشارةٍ موجبة**؟

    يُرجِع `True` فقط حين يُتعرَّف على موضوعٍ **ليس** من عائلة الاحتمالات. والصمت
    (`source == "none"`) يُرجِع `False` — لأنّ «لم أفهم» و«نعم» و«السلام عليكم» ليست
    تبديلَ موضوع، وأيُّ قراءةٍ أخرى تكسر استمرارية الدرس (D-184: البؤرة لاصقة).

    هذا هو المُسنَد الذي يستبدل الصيغة المكسورة في المواضع الستّة:

        # قبل — لا يعمل لسؤال فيزياء (canonical is None فيسقط الشرط):
        if _c is not None and _c.canonical_id != "probability": return None
        # بعد:
        if is_foreign_to_probability(question): return None
    """
    topic = resolve_turn_topic(text)
    if not topic.is_identified:
        return False
    return not topic.is_probability
