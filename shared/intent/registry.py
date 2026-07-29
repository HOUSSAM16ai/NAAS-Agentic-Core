"""سجلّ نيّة الطالب — المصدر القانوني الوحيد (D-186).

## لماذا هذا الملف موجود

ثلاث كوارث متتالية على الطالب الحقيقي كان جذرها **واحداً**: قوائم علامات متعدّدة لنفس
النيّة، كلٌّ في وحدة، تتفرّق بمرور الوقت.

- **ISS-128** — «هل هي 14 من 165؟» عُوملت سؤالاً لا إجابة (قائمتان تختلفان).
- **ISS-138** — «ماذا نقصد بحرف C» تُجوهِلت (`_detect_conceptual_question` فيها «معنى»
  ولا فيها «نقصد»).
- **ISS-139** — «ماذا **يقصد** بالحرف C» صُنِّفت `unknown` لأن ثلاث قوائم للنيّة التعريفية
  (23 و13 و27 علامة) **لا تتّفق أيّ اثنتين منها**. وفي الاتجاه المعاكس تماماً، «شنو يقصد»
  تعرفها قائمتان وتجهلها الثالثة.

كل مرّة كان العلاج «أضِف الكلمة الناقصة إلى القائمة التي أخطأت» — فيُصلَح العَرَض ويبقى
الصنف، وتعود الكارثة بصيغة أخرى. هذا الملف يُنهي الصنف: **مصدر واحد، وبوّابة CI تجعل
القائمة السادسة مستحيلة** (`scripts/fitness/check_intent_single_source.py`).

على سابقة `shared/notation` (D-185) و`shared/ai_models/model_chain` (D-174):
«تكافؤ محروس آلياً بدل حرّر النسخ يدوياً».

## قواعد دائمة

1. **العلامات هنا وحدها.** أي وحدة تحتاج علامات نيّة تستوردها من هنا — لا تُعرّف نسخة.
2. **الاتحاد لا التقاطع.** صيغة يعرفها كاشفٌ واحد تصير معروفة للجميع؛ فتفرّق الكاشفات
   هو العطب نفسه.
3. **بلا تبعيات.** stdlib فقط — كي تستهلكها الخدمات المصغّرة والمونوليث معاً.
4. **الحساب يُلغي التعريف.** «احسب C(11,3)» ليس سؤالاً تعريفياً؛ `classify` تحترم ذلك.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

_TATWEEL = "ـ"
_DIACRITICS_RE = re.compile(r"[ً-ْٰۖ-ۭ]")

#: توحيد الهمزات والألف المقصورة والتاء المربوطة — الطالب يكتبها بكل الصور.
_CHAR_FOLD = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ى": "ي",
        "ة": "ه",
        "ﻻ": "لا",
    }
)


def normalize(text: str) -> str:
    """يُطبِّع نصّ الطالب لمطابقة العلامات — تشكيل/تطويل/همزات + توحيد المسافات.

    مطابق دلالياً لـ`shared.notation.registry.normalize` (التي تزيد طيّ الرموز
    الرياضية لأنها تُطابق رموزاً لا كلمات). البوّابة `check_intent_single_source`
    تُثبت أنّ القائمتين لا تنجرفان.
    """
    if not text:
        return ""
    base = unicodedata.normalize("NFKC", text)
    base = _DIACRITICS_RE.sub("", base).replace(_TATWEEL, "")
    base = base.translate(_CHAR_FOLD)
    return re.sub(r"\s+", " ", base).strip().lower()


@dataclass(frozen=True)
class IntentEntry:
    """نيّة طالب واحدة: اسمها، وصفها، وكل الصيغ التي يكتبها بها فعلاً."""

    name: str
    description: str
    markers: tuple[str, ...] = field(default_factory=tuple)


# ─────────────────────────────────────────────────────────────────────────────
# السجلّ — اتحاد كل القوائم التي كانت مبعثرة، بلا فقدان صيغة واحدة
# ─────────────────────────────────────────────────────────────────────────────

#: نيّة التعريف — اتحاد `_DEFINITIONAL_MARKERS` (semantic_property، 23) و
#: `_DEFINITION_MARKERS` (student_state، 13) و`_DEFINITIONAL_INTENT` (notation، 27).
#: تفرّقُها هو ISS-139 حرفياً: «ماذا يقصد» كانت في واحدة فقط من الثلاث.
_DEFINITION: tuple[str, ...] = (
    # ── «نقصد / يقصد» — الصيغة التي أسقطت ISS-138 و ISS-139 ──
    "ماذا نقصد",
    "ما نقصد",
    "شنو نقصد",
    "ماذا يقصد",
    "شنو يقصد",
    "واش يقصد",
    "المقصود",
    "ما المقصود",
    # ── «معنى» ──
    "ما معنى",
    "ما معناه",
    "معنى",
    "ما هو معنى",
    "ماذا يعني",
    "ماذا تعني",
    "واش يعني",
    "واش تعني",
    "يعني ايه",
    # ── «ما هو / ما هي» ──
    "ما هو",
    "ما هي",
    "ماهو",
    "ماهي",
    "شنو هو",
    "شنو هي",
    "شنو هاذ",
    "واش راه",
    # ── تعريف صريح ──
    "تعريف",
    "ما تعريف",
    "عرف ",
    "عرّف ",
    # ── تسمية ──
    "ماذا نسمي",
    "ما نسمي",
    "ما اسم",
    "ما إسم",
    "ماذا يسمى",
    "ما يسمى",
    "ما تسمية",
    # ── فهم المعنى (لا الإجراء) ──
    "كيف افهم",
    "علاش قال",
    # ── فرنسية / إنجليزية ──
    "signifie",
    "veut dire",
    "c est quoi",
    "what is",
)

#: نيّة الحيرة — اتحاد خمس قوائم (semantic_property · student_state · policy ×2 ·
#: escape_hatch). لا تشمل طلبات الشرح الصريحة: تلك نيّة مستقلّة أدناه.
_CONFUSION: tuple[str, ...] = (
    "لم افهم",
    "لم أفهم",
    "لم استوعب",
    "ما فهمت",
    "مافهمت",
    "ما فهمتش",
    "مفهمتش",
    "لا افهم",
    "لا أفهم",
    "ما افهم",
    "لست افهم",
    "مش فاهم",
    "مازلت",
    "ما زلت",
    "مازلت لا",
    "ما زلت لا افهم",
    "صعب",
    "صعبة",
    "حاير",
    "محتار",
    "لا اعرف",
    "لا أعرف",
    "معرفتش",
    "ماعرفت",
    "ما عرفت",
    "je ne comprends pas",
    "i don't understand",
)

#: طلب شرح صريح — أوسع من الحيرة («أعد الشرح» ليست حيرة بل أمراً).
#: كانت مدمجة داخل `_PROBABILITY_CONFUSION_MARKERS` في `escape_hatch`.
_EXPLANATION_REQUEST: tuple[str, ...] = (
    "اشرح لي",
    "اشرحلي",
    "وضح لي",
    "وضحلي",
    "أين الشرح",
    "اين الشرح",
    "أعد الشرح",
    "اعد الشرح",
)

#: طلب مثال — من `_EXAMPLE_MARKERS` (student_state).
_EXAMPLE_REQUEST: tuple[str, ...] = (
    "اعطني مثال",
    "أعطني مثال",
    "اعطيني مثال",
    "اعطني مثل",
    "هات مثال",
    "مثالا",
    "مثالاً",
    "مثال على",
    "مثال عن",
    "example",
)

#: طلب إجراء — من `_PROCEDURE_MARKERS` (student_state).
_PROCEDURE: tuple[str, ...] = (
    "كيف نحسب",
    "كيف احسب",
    "كيف أحسب",
    "كيفاش نحسب",
    "كيف نوجد",
    "كيف نجد",
    "كيف نحل",
    "كيفاش نحل",
    "ما هي الخطوات",
    "ماهي الخطوات",
    "خطوات الحل",
    "طريقة الحساب",
)

#: طلب تلميح — من `_HINT_MARKERS` (student_state).
_HINT_REQUEST: tuple[str, ...] = (
    "تلميح",
    "اعطني تلميح",
    "ساعدني",
    "ساعديني",
    "دلني",
    "وجهني",
    "ارشدني",
    "hint",
)

#: مقارنة/علاقة — من `_COMPARISON_MARKERS` (student_state).
_COMPARISON: tuple[str, ...] = (
    "الفرق بين",
    "ما الفرق",
    "الفرق",
    "قارن",
    "العلاقة بين",
    "ما العلاقة",
    "الهدف من",
    "ما الهدف",
    "لماذا نستخدم",
    "vs",
)

#: نيّة حسابية — من `_COMPUTE_INTENT` (notation). تُلغي النيّة التعريفية:
#: «احسب C(11,3)» ليس سؤالاً عن معنى الرمز.
_COMPUTATION: tuple[str, ...] = (
    "احسب",
    "أحسب",
    "اوجد",
    "أوجد",
    "بين ان",
    "بيّن أن",
    "استنتج",
    "كم عدد",
    "كم هو",
    "احتمال الحادثه",
    "عين قانون",
)

INTENT_REGISTRY: tuple[IntentEntry, ...] = (
    IntentEntry("definition", "الطالب يسأل عن معنى مفهوم أو رمز", _DEFINITION),
    IntentEntry("confusion", "الطالب يعبّر عن عدم الفهم", _CONFUSION),
    IntentEntry("explanation_request", "الطالب يطلب شرحاً صريحاً", _EXPLANATION_REQUEST),
    IntentEntry("example_request", "الطالب يطلب مثالاً", _EXAMPLE_REQUEST),
    IntentEntry("procedure", "الطالب يسأل عن طريقة الحساب", _PROCEDURE),
    IntentEntry("hint_request", "الطالب يطلب تلميحاً", _HINT_REQUEST),
    IntentEntry("comparison", "الطالب يسأل عن فرق أو علاقة بين مفهومين", _COMPARISON),
    IntentEntry("computation", "الطالب يطلب حساباً صريحاً", _COMPUTATION),
)

_BY_NAME: dict[str, IntentEntry] = {entry.name: entry for entry in INTENT_REGISTRY}

#: علامات مُطبَّعة مُسبقاً — الطالب يكتب بالتشكيل والهمزات، والمقارنة على المُطبَّع.
_NORM_MARKERS: dict[str, tuple[str, ...]] = {
    entry.name: tuple(normalize(m) for m in entry.markers if m.strip()) for entry in INTENT_REGISTRY
}

#: ترتيب الحسم عند تطابق أكثر من نيّة — الأخصّ أولاً.
#: الحساب يسبق التعريف («احسب ما هو C» طلب حساب)، والمثال/التلميح يسبقان الحيرة العامة.
_PRECEDENCE: tuple[str, ...] = (
    "computation",
    "example_request",
    "hint_request",
    "comparison",
    "procedure",
    "definition",
    "explanation_request",
    "confusion",
)


def all_intents() -> tuple[str, ...]:
    """أسماء كل النيّات المُعرَّفة."""
    return tuple(entry.name for entry in INTENT_REGISTRY)


def markers_for(intent: str) -> tuple[str, ...]:
    """علامات نيّةٍ بعينها — نقطة الاستهلاك الوحيدة للوحدات."""
    entry = _BY_NAME.get(intent)
    if entry is None:
        raise KeyError(f"unknown intent: {intent!r} (known: {', '.join(all_intents())})")
    return entry.markers


def matches(text: str, intent: str) -> bool:
    """هل يحمل النصّ علامةً من علامات هذه النيّة؟ (مطابقة على النصّ المُطبَّع)."""
    if intent not in _BY_NAME:
        raise KeyError(f"unknown intent: {intent!r} (known: {', '.join(all_intents())})")
    norm = normalize(text)
    if not norm:
        return False
    return any(marker in norm for marker in _NORM_MARKERS[intent])


def classify(text: str) -> str | None:
    """النيّة الغالبة للنصّ، أو ``None`` إن لم تُطابَق أيّ نيّة.

    الحسم بترتيب `_PRECEDENCE` (الأخصّ أولاً) — لا «أول ما يُطابق في السجلّ»،
    كي لا يخطف ترتيبُ التصريح قرارَ النيّة.
    """
    norm = normalize(text)
    if not norm:
        return None
    for name in _PRECEDENCE:
        if any(marker in norm for marker in _NORM_MARKERS[name]):
            return name
    return None
