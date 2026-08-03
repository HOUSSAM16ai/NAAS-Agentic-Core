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
from collections.abc import Callable
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
    # D-206: من `exercise_retrieval._EXPLANATION_INTENT_PATTERNS` عند تفكيكها.
    "ما مفهوم",
    "what are",
    "what does",
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
    # D-206: من `exercise_retrieval._EXPLANATION_INTENT_PATTERNS` عند تفكيكها (قاعدة
    # الاتحاد D-186#2 — صيغةٌ يعرفها كاشفٌ واحد تصير معروفةً للجميع).
    "help me",
    "help with",
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
    # ISS-149: كانت القائمة **أسماءً فقط** («الفرق»)، فسؤال الطالب الحرفي
    # «كيف **نفرق** بين البسط و المقام؟» لم يُعَدّ مقارنةً — والصيغة الفعلية هي
    # الأشيع في كلام الطلبة. حرفٌ واحد من الاشتقاق أسقط نيّةً كاملة.
    "نفرق",
    "نفرق بين",
    "نميز",
    "نميز بين",
    "التفريق",
    "نفصل بين",
    "الاختلاف",
    "وش الفرق",
)

#: ISS-149 — **ادّعاء الفهم**. «فهمت» إقرارٌ لفظي لا برهان (عقد D-138 يقولها
#: صراحةً: «آلية، لا فهمت»)، وليست سؤالاً ولا محاولةً يُعترَف بها (D-207·L1).
#: كانت غير مُمثَّلة في أيّ سجلّ، فاستنفدت الميزانيةَ السقراطية وأنتجت التسليم
#: الرمزي الكامل — أي أنّ قولَ «فهمت» كان **يشتري الحلّ**، وهو أسوأ ما يُدرَّب
#: عليه طالب. تُقاس «مجرّدةً» عند نقطة الاستهلاك (علامة + رسالة قصيرة)، على
#: سابقة `_is_bare_confusion`: «اها فهمت، تقلص الفضاء فنقسم على عدد اقل» برهانٌ
#: لا ادّعاء.
_ACKNOWLEDGEMENT: tuple[str, ...] = (
    "فهمت",
    "فهمتها",
    "فهمت الان",
    "واضح",
    "وضحت",
    "تمام",
    "حسنا",
    "استوعبت",
    "عرفت",
    "ok",
    "d'accord",
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
    IntentEntry(
        "part_selection",
        "الطالب يطلب جزءاً بعينه من التمرين («اعطني اول سؤال فقط»)",
        (),  # بلا علامات هنا عمداً — انظر `_PREDICATES` أدناه.
    ),
    IntentEntry("definition", "الطالب يسأل عن معنى مفهوم أو رمز", _DEFINITION),
    IntentEntry("confusion", "الطالب يعبّر عن عدم الفهم", _CONFUSION),
    IntentEntry("explanation_request", "الطالب يطلب شرحاً صريحاً", _EXPLANATION_REQUEST),
    IntentEntry("example_request", "الطالب يطلب مثالاً", _EXAMPLE_REQUEST),
    IntentEntry("procedure", "الطالب يسأل عن طريقة الحساب", _PROCEDURE),
    IntentEntry("hint_request", "الطالب يطلب تلميحاً", _HINT_REQUEST),
    IntentEntry("comparison", "الطالب يسأل عن فرق أو علاقة بين مفهومين", _COMPARISON),
    IntentEntry("computation", "الطالب يطلب حساباً صريحاً", _COMPUTATION),
    IntentEntry("acknowledgement", "الطالب يُقرّ بالفهم لفظاً دون برهان", _ACKNOWLEDGEMENT),
)

_BY_NAME: dict[str, IntentEntry] = {entry.name: entry for entry in INTENT_REGISTRY}

#: علامات مُطبَّعة مُسبقاً — الطالب يكتب بالتشكيل والهمزات، والمقارنة على المُطبَّع.
_NORM_MARKERS: dict[str, tuple[str, ...]] = {
    entry.name: tuple(normalize(m) for m in entry.markers if m.strip()) for entry in INTENT_REGISTRY
}


#: نيّات سلطتُها سجلٌّ آخر — تُحسَم بمُسنَدٍ لا بقائمة علامات هنا.
#:
#: **لماذا لا نُكرّر العلامات (D-206 · L6):** نيّة النطاق تحتاج تحليلاً بنيوياً (ترتيبيّ +
#: أداة تعريف + حدود كلمات + رقم عربي-هندي) لا مجرّد قائمة. نسخُ علاماتها هنا يخلق
#: **القائمة الثامنة** — وهي بالضبط الكارثة التي وُلد منها هذا الملفّ. فالسلطة تبقى في
#: `shared/exercise_scope` وهذا الملفّ يستشيرها. الاستيراد كسول لأنّ `shared.exercise_scope`
#: يستورد `shared.textnorm` لا `shared.intent` (فلا دورة)، والتأجيل يُبقي الاستيراد رخيصاً.
def _is_part_selection(text: str) -> bool:
    """هل يطلب الطالب جزءاً بعينه من التمرين؟ السلطة: `shared/exercise_scope`."""
    from shared.exercise_scope import resolve_scope

    return resolve_scope(text).explicit


_PREDICATES: dict[str, Callable[[str], bool]] = {
    "part_selection": _is_part_selection,
}

#: ترتيب الحسم عند تطابق أكثر من نيّة — الأخصّ أولاً.
#: الحساب يسبق التعريف («احسب ما هو C» طلب حساب)، والمثال/التلميح يسبقان الحيرة العامة.
#:
#: **`part_selection` تسبق `computation` (D-206):** الطالب يلصق نصّ التمرين — وهو مليء
#: بـ«احسب» و«بيّن أن» — ثمّ يكتب «اعطني اول سؤال فقط». بالترتيب المعاكس تخطف النيّةُ
#: الحسابيةُ طلبَ النطاق، وهو ما قِيس حيّاً: `classify` أعادت `'computation'` للدور الثاني.
_PRECEDENCE: tuple[str, ...] = (
    "part_selection",
    "computation",
    "example_request",
    "hint_request",
    "comparison",
    "procedure",
    "definition",
    "explanation_request",
    "confusion",
    # ISS-149: **آخر الترتيب عمداً.** «اها فهمت، لكن كيف نحسب المقام؟» سؤالٌ قبل
    # كل شيء؛ الإقرار لا يخطف نيّةً أخصّ منه أبداً. وهذا الموضع يضمن أن إضافتها
    # لا تُغيّر تصنيف أيّ نصٍّ كان يُصنَّف قبلها.
    "acknowledgement",
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
        predicate = _PREDICATES.get(name)
        if predicate is not None:
            if predicate(text):
                return name
            continue
        if any(marker in norm for marker in _NORM_MARKERS[name]):
            return name
    return None
