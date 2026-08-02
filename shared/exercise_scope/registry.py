"""سجلّ نطاق التمرين — المصدر القانوني الوحيد لِـ«أيّ جزءٍ طلب الطالب؟» (D-206).

## الكارثة التي يُغلقها هذا الملفّ (ISS-144)

طالب حقيقي طلب نطاقاً صريحاً **ثلاث مرّات** فلم يحصل عليه ولا مرّة:

1. «اعطني تمرين الاحتمالات 2024» ⇒ التمرين كاملاً ✅
2. التمرين ملصوقاً + «**اعطني اول سؤال من التمرين فقط**» ⇒ الجزء (1) **والجزء (2)** معاً
3. «**لقد طلبت السؤال الأول فقط**» ⇒ سؤال سقراطي عن الألوان — لا السؤال الأول

**الجذر (مُتحقَّق وقت التشغيل، لا استنتاجاً):** الترتيبيات في
``exercise_retrieval._ORDINAL_QUESTION_NUMBERS`` كانت **ستّ صيغ مُعرَّفة فقط**
(``"الأول"`` · ``"الاول"`` …) تُطابَق على ``text.strip().lower()`` — و``lower()`` لا
تفعل شيئاً بالعربية. فالطالب الذي كتب «**اول** سؤال» نكرةً لم يكن مُمثَّلاً أصلاً::

    _extract_question_number("اعطني اول سؤال من التمرين فقط")  → None
    _extract_question_number("عطيني لول سؤال")                  → None

وما جعل الدور الثاني يعمل بالصدفة أنّ **نصّ التمرين الملصوق** حوى «التمرين الأول»،
فالتُقط الرقم من التمرين لا من جملة الطالب. بلا ذلك اللصق كان يسقط إلى بثّ كلّ شيء.

## القواعد الدائمة التي يُرسيها (L4 · L6 · L1)

1. **العلامة تُطابَق مُطبَّعةً وبلا أداة تعريف** — صورةٌ واحدة تُغطّي «الأول» و«اول»
   و«الأولى» معاً، بدل ثلاث صيغ يدوية تتقادم. (نمط `shared/curriculum` المُثبَت —
   ISS-109/112/114 كان جذرها أداةَ التعريف نفسها.)
2. **على حدود الكلمات** — «اول» تختبئ داخل «تناول» و«الأولية»؛ المطابقة النصّية الساذجة
   تجعل «تناولنا الدرس» طلبَ نطاق.
3. **اتحاد لا تقاطع** — فصحى + دارجة («لول» · «تاني») + فرنسية + أرقام غربية وعربية-هندية.
   صيغةٌ يعرفها كاشفٌ واحد تصير معروفةً للجميع (قاعدة D-186#2).
4. **الغياب يُعبَّر عنه بالغياب** — ``question_number=None`` لا ``1`` افتراضاً. تخمينُ
   «الأول» حين لا يذكر الطالب رقماً يُعلّمه مسألةً غير مسألته (D-191).

⛔ **هذا الملفّ يُقرِّر النطاق ولا يقرأ محتوى التمرين إطلاقاً.** الاقتطاع من نصّ التمرين
مسؤولية الطبقة المستهلِكة؛ فصلُ «ما طلبه الطالب» عن «ما نملكه» هو ما يجعل L1 (الفشل
يُقصِّر ولا يُوسِّع) قابلاً للفرض أصلاً.

## بلا تبعيات

stdlib + ``shared/textnorm`` فقط — كي تستهلكه الخدمات المصغّرة والمونوليث معاً
(قانون الحدود: ``shared/`` لا يستورد ``app/`` ولا خدمةً شقيقة).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Final, Literal

from shared.textnorm import normalize

__all__ = [
    "EXPLANATION_CANCEL_MARKERS",
    "ORDINAL_FORMS",
    "PART_LABEL_MARKERS",
    "SCOPE_ONLY_MARKERS",
    "SCOPE_REQUEST_VERBS",
    "ExerciseScope",
    "ScopeSource",
    "extract_target",
    "ordinal_value",
    "resolve_scope",
    "strip_articles",
]

ScopeSource = Literal["text", "history", "none"]

#: أقصى رقم بندٍ معقول في تمرين بكالوريا — ما فوقه سنةٌ أو معطى لا رقم سؤال.
_MAX_QUESTION_NUMBER: Final[int] = 20


@lru_cache(maxsize=4096)
def strip_articles(text: str) -> str:
    """يحذف أداة التعريف «ال» من بداية كل كلمة (مرآة `shared/curriculum`).

    حدّ الطول ٤ يحمي الكلمات التي «ال» جزءٌ أصيل منها (الله · الان)، وهو نفس الحدّ
    المُستقرّ في `shared/curriculum/registry.py:_strip_articles` — لا رقم جديد.
    """
    return " ".join(
        token[2:] if token.startswith("ال") and len(token) > 4 else token
        for token in text.split(" ")
    )


# ─────────────────────────────────────────────────────────────────────────────
# المفردات القانونية — اتحاد كل ما كان مبعثراً، بلا فقدان صيغة
# ─────────────────────────────────────────────────────────────────────────────

#: صور الترتيبيات بعد التطبيع **وحذف أداة التعريف**. صورةٌ واحدة تُغطّي المُعرَّف
#: والنكرة معاً («الأول» ⇒ «اول» = «اول»)، وهو ما يقتل صنفَ ISS-144 لا عَرَضه.
ORDINAL_FORMS: Final[tuple[tuple[str, int], ...]] = (
    # ١ — «اول» هي الصيغة التي كسرت حرفياً؛ «اولي» = الأولى؛ «لول» دارجة.
    ("اول", 1),
    ("اولي", 1),
    ("لول", 1),
    ("premiere", 1),
    ("premier", 1),
    ("first", 1),
    # ٢ — «تاني» دارجة.
    ("ثاني", 2),
    ("ثانيه", 2),
    ("تاني", 2),
    ("deuxieme", 2),
    ("second", 2),
    # ٣ — «تالت» دارجة.
    ("ثالث", 3),
    ("ثالثه", 3),
    ("تالت", 3),
    ("troisieme", 3),
    ("third", 3),
    # ٤
    ("رابع", 4),
    ("رابعه", 4),
    ("quatrieme", 4),
    ("fourth", 4),
    # ٥
    ("خامس", 5),
    ("خامسه", 5),
    ("cinquieme", 5),
    ("fifth", 5),
    # ٦ · ٧
    ("سادس", 6),
    ("سادسه", 6),
    ("سابع", 7),
    ("سابعه", 7),
    # ٨ → ١٠ — من `context_composer._normalize_index_token` عند هجرتها (قاعدة الاتحاد
    # D-186#2). ذلك المُحلِّل كان يعرف النكرة («اول») التي جهلها كاشفُ الاسترجاع، وهذا
    # بالضبط ما يعنيه «كاشفان لنيّةٍ واحدة يتفرّقان»: كلٌّ يعرف ما يجهله الآخر.
    ("ثامن", 8),
    ("ثامنه", 8),
    ("تاسع", 9),
    ("تاسعه", 9),
    ("عاشر", 10),
    ("عاشره", 10),
)

#: علامات الحصر — «فقط» وأخواتها. وجودها يجعل الردّ الأوسع خرقاً صريحاً (L1).
SCOPE_ONLY_MARKERS: Final[tuple[str, ...]] = (
    "فقط",
    "بس",
    "only",
    "وحده",
    "لا غير",
    "دون غيره",
    "بدون حل",
    "بدون الحل",
    "بدون اجابه",
    "بدون الاجابه",
    "بدون تصحيح",
    "نص السؤال",
    "نص التمرين",
    "question only",
    "only the question",
    "without solution",
    "seulement",
)

#: أفعال الطلب — «أعطني» وأخواتها فصحى ودارجة وفرنسية.
SCOPE_REQUEST_VERBS: Final[tuple[str, ...]] = (
    "اعطني",
    "اعطيني",
    "عطيني",
    "عطني",
    "اريد",
    "بغيت",
    "نبغي",
    "هات",
    "هاتلي",
    "جيب",
    "جيبلي",
    "ورني",
    "وريني",
    "اكتب لي",
    "ابغي",
    "طلبت",
    "donne",
    "montre",
    "give me",
    "show me",
)

#: كلمات الجزء/البند — «الجزء الأول» · «part i» · «الفرع ب».
PART_LABEL_MARKERS: Final[tuple[str, ...]] = (
    "جزء",
    "فرع",
    "بند",
    "قسم",
    "part",
    "partie",
)

#: ما يُلغي نيّة النطاق: طلبُ شرحٍ ليس طلبَ اقتطاع (ISS-038 — الأولوية للشرح).
#: اتحادٌ يشمل `exercise_retrieval._EXPLANATION_INTENT_PATTERNS` دلالياً.
EXPLANATION_CANCEL_MARKERS: Final[tuple[str, ...]] = (
    "اشرح",
    "شرح",
    "اشرحلي",
    "وضح",
    "وضحلي",
    "فسر",
    "بين لي",
    "علمني",
    "explain",
    "describe",
    "لماذا",
    "علاش",
    "كيف",
    "كيفاش",
    "how",
    "why",
)

#: «السؤال 2» / «سؤال رقم ٣» — الرقم الصريح يسبق الترتيبي.
_EXPLICIT_NUMBER_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:السؤال|سؤال|سوال|question|exercice)\s*(?:رقم\s*)?(\d{1,2})"
)

#: «الجزء 2» / «part ii» — الجزء الروماني أو الرقمي.
_ROMAN_PART_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:الجزء|جزء|part|partie)\s*(iii|ii|i|[123])\b"
)

_ROMAN_BY_TOKEN: Final[dict[str, str]] = {
    "i": "I",
    "1": "I",
    "ii": "II",
    "2": "II",
    "iii": "III",
    "3": "III",
}

#: مؤشّرات أن الكلام عن **سؤال/بند** لا عن شيء آخر يحمل ترتيبيّاً («الفصل الأول»).
_QUESTION_NOUNS: Final[tuple[str, ...]] = (
    "سؤال",
    "سوال",
    "بند",
    "طلب",
    "question",
    "جزء",
    "فرع",
    "part",
    "partie",
)

#: الأسماء المُطبَّعة — تُستعمل بالاحتواء لا بالحدود: هي **قرينة سياق** («الكلام عن بند»)
#: لا علامةَ نيّة، وحذفُ الهمزة يجعل «الجزء» ⇒ «الجز» فتفشل حدودُ الكلمة بلا ذنب.
_NORM_NOUNS: Final[tuple[str, ...]] = tuple(
    dict.fromkeys(filter(None, (normalize(noun) for noun in _QUESTION_NOUNS)))
)


def _norm_all(markers: tuple[str, ...]) -> tuple[str, ...]:
    """يُطبِّع العلامات مرّةً واحدة وقت الاستيراد.

    **بندٌ غير قابل للتفاوض (L4):** العلامة تُقارَن بنصٍّ مُطبَّع، فيجب أن تكون مُطبَّعةً
    مثله. `shared/textnorm` يحذف الهمزة المفردة (ء) فتصير «جزء» ⇒ «جز» في النصّ؛ علامةٌ
    غير مُطبَّعة تبحث عن «جزء» في نصٍّ لم يعد يحويها — فتفشل صامتةً. هذا هو **نفس** صنف
    ISS-144 (مقارنة صيغةٍ بصيغةٍ أخرى) وقد وقعتُ فيه هنا أوّل مرّة.
    """
    return tuple(dict.fromkeys(filter(None, (normalize(m) for m in markers))))


def _matches_word(haystack_words: frozenset[str], marker: str) -> bool:
    """مطابقة على حدود الكلمات — «اول» لا تُطابِق «تناول» ولا «اولي»."""
    if " " in marker:
        return False
    return marker in haystack_words


def _boundary_pattern(markers: tuple[str, ...]) -> re.Pattern[str] | None:
    """تعبيرٌ واحد مُصرَّف لكل مجموعة علامات — بديلٌ عن تصريفٍ لكلّ علامة لكلّ نداء.

    **قياسٌ لا حدس:** النسخة الأولى بَنَت regex لكلّ علامة في كلّ نداء، فصارت
    `resolve_scope` 53µs و`classify` 68µs — وهي في مسارٍ ساخن يُستدعى كلّ دور،
    فتجاوزت `test-monolith` مهلتها في CI. الأطول أوّلاً كي لا تخطف علامةٌ قصيرة
    أطولَ منها داخل البديل (`اول` قبل `اولي` تُفسد الترتيب).
    """
    cleaned = sorted((m for m in markers if m), key=len, reverse=True)
    if not cleaned:
        return None
    joined = "|".join(re.escape(m) for m in cleaned)
    return re.compile(r"(?<!\w)(?:" + joined + r")(?!\w)")


def _contains_boundary(text: str, marker: str) -> bool:
    """وجود العلامة كوحدة مستقلّة (كلمة أو عبارة) لا كجزءٍ من كلمة أطول."""
    if not marker:
        return False
    pattern = _MARKER_RE_CACHE.get(marker)
    if pattern is None:
        pattern = re.compile(r"(?<!\w)" + re.escape(marker) + r"(?!\w)")
        _MARKER_RE_CACHE[marker] = pattern
    return pattern.search(text) is not None


#: تصريفٌ كسول لكل علامة مفردة (يُستعمل عند المطابقة الفردية).
_MARKER_RE_CACHE: dict[str, re.Pattern[str]] = {}


#: الصور المُطبَّعة، مرتّبةً بالأطول أوّلاً — الأخصّ يفوز **بالبناء** لا بترتيب الكتابة.
_NORM_ORDINALS: Final[tuple[tuple[str, int], ...]] = tuple(
    sorted(
        ((normalize(form), value) for form, value in ORDINAL_FORMS),
        key=lambda item: (-len(item[0]), item[0]),
    )
)
_NORM_ONLY: Final[tuple[str, ...]] = _norm_all(SCOPE_ONLY_MARKERS)
_NORM_VERBS: Final[tuple[str, ...]] = _norm_all(SCOPE_REQUEST_VERBS)
_NORM_PART_LABELS: Final[tuple[str, ...]] = _norm_all(PART_LABEL_MARKERS)
_NORM_CANCEL: Final[tuple[str, ...]] = _norm_all(EXPLANATION_CANCEL_MARKERS)
_CANCEL_RE: Final[re.Pattern[str] | None] = _boundary_pattern(_NORM_CANCEL)
_ORDINAL_RE_BY_VALUE: Final[tuple[tuple[re.Pattern[str], int], ...]] = tuple(
    (_boundary_pattern((form,)), value)  # type: ignore[misc]
    for form, value in _NORM_ORDINALS
)


def ordinal_value(text: str) -> int | None:
    """قيمة الترتيبي في النصّ، أو ``None``.

    **تُطبِّع وتحذف أداة التعريف بنفسها** (L4): العلامات هنا مُطبَّعة، فمقارنتها بنصٍّ
    خام تفشل على «الأول» بالهمزة — وهو نفس عطب ISS-144 لو أنّ المستدعي نسي التطبيع.
    الدالّة التي تملك العلامات المُطبَّعة تملك مسؤولية تطبيع مدخلها؛ تركُها للمستدعي
    يجعل كلّ نقطة استدعاء موضعَ كارثةٍ محتملة. التطبيع خاملٌ فتكراره آمن.

    الأطول أوّلاً كي لا تخطف «اول» صيغةَ «اولي» (نفس منطق `shared/curriculum`:
    الأخصّ يفوز بالبناء لا بترتيب الكتابة اليدوي).
    """
    haystack = strip_articles(normalize(text))
    for pattern, value in _ORDINAL_RE_BY_VALUE:
        if pattern is not None and pattern.search(haystack):
            return value
    return None


@dataclass(frozen=True)
class ExerciseScope:
    """النطاق الذي طلبه الطالب — قرارٌ صريح، لا تخمين.

    ``explicit`` تعني «الطالب طلب نطاقاً بوضوح»؛ وهي وحدها ما يُبرِّر استباق بقيّة
    مراحل الدور (L2). ``only`` تعني «وحصر الطلب» ⇒ الردّ الأوسع خرقٌ (L1).
    """

    question_number: int | None = None
    part: str | None = None
    only: bool = False
    explicit: bool = False
    source: ScopeSource = "none"
    reason: str = "no_scope_intent"

    @property
    def is_empty(self) -> bool:
        """لا رقم ولا جزء — نطاقٌ بلا هدف محدّد."""
        return self.question_number is None and self.part is None


_EMPTY: Final[ExerciseScope] = ExerciseScope()


@lru_cache(maxsize=2048)
def _scan(text: str) -> tuple[int | None, str | None]:
    """يستخرج (رقم السؤال، الجزء) من نصٍّ واحد — بلا تاريخ ولا سياق.

    **مُذاكِرة عمداً (لا تحسين مبكّر):** دالّة خالصة على نصٍّ قصير، وتُستدعى في مسارٍ
    ساخن — `shared.intent.classify` تستشيرها في **كل** دور. القياس: `classify` صارت
    68µs/نداء (منها 53µs هنا) بعد وصلها، فتجاوزت وظيفةُ `test-monolith` مهلتها
    (13م50ث من أصل 20 على `main` ⇒ >20م). الذاكرة تُعيدها إلى تكلفة البحث في قاموس.
    """
    norm = normalize(text)
    if not norm:
        return None, None
    stripped = strip_articles(norm)

    part: str | None = None
    roman = _ROMAN_PART_RE.search(norm) or _ROMAN_PART_RE.search(stripped)
    if roman:
        part = _ROMAN_BY_TOKEN.get(roman.group(1))

    number: int | None = None
    explicit = _EXPLICIT_NUMBER_RE.search(norm) or _EXPLICIT_NUMBER_RE.search(stripped)
    if explicit:
        candidate = int(explicit.group(1))
        if 1 <= candidate <= _MAX_QUESTION_NUMBER:
            number = candidate

    # الترتيبي يُحتسَب فقط بقرينة اسمٍ يدلّ على سؤال/جزء — «الفصل الأول» ليس بنداً.
    if number is None and any(noun in stripped or noun in norm for noun in _NORM_NOUNS):
        ordinal = ordinal_value(stripped)
        if ordinal is not None:
            # ترتيبيّ ملتصق بكلمة «جزء» يُعبّر عن الجزء لا عن رقم السؤال.
            if part is None and any(
                label in stripped or label in norm for label in _NORM_PART_LABELS
            ):
                part = _ROMAN_BY_TOKEN.get(str(ordinal))
            else:
                number = ordinal

    return number, part


def extract_target(text: str) -> tuple[int | None, str | None]:
    """(رقم البند، الجزء) من نصٍّ واحد — **استخراجٌ محض بلا شرط نيّة**.

    مقابل `resolve_scope` التي تشترط نيّةً صريحة (فعل طلب أو حصر). يحتاجها المستدعي
    الذي حسم النيّة سلفاً بطريقته ولا يريد إلّا الهدف — مثل قراءة «السؤال الثاني»
    من رسالةٍ سابقة في الحوار. فصلُ الاثنين يمنع إضعافَ عقد `resolve_scope` إرضاءً
    لمستدعٍ واحد (وهو خطأ كنتُ على وشك ارتكابه هنا).
    """
    return _scan(text)


def _scan_history(history: list[dict[str, str]] | None) -> tuple[int | None, str | None]:
    """آخر نطاقٍ ذكره **الطالب** في الحوار (D-102: رسائل `user` وحدها دليل)."""
    for message in reversed(list(history or [])[-8:]):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        number, part = _scan(str(message.get("content", "")))
        if number is not None or part is not None:
            return number, part
    return None, None


def resolve_scope(text: str, history: list[dict[str, str]] | None = None) -> ExerciseScope:
    """النطاق الذي يطلبه الطالب — حتمي، صفر LLM، صفر شبكة.

    الترتيب (وهو العقد):

    1. **نيّة الشرح تُلغي** — «اشرح السؤال الأول» طلبُ شرحٍ لا اقتطاع (ISS-038).
    2. **نيّة النطاق** = علامة حصر («فقط») **أو** فعل طلب، بقرينة اسمٍ يدلّ على بند.
    3. الهدف من نصّ الطالب الحاضر، ثمّ من رسائله السابقة (لا رسائل المساعد — D-102).
    4. لا هدف ⇒ ``question_number=None`` صراحةً؛ **ممنوع افتراض ١** (D-191).
    """
    if not text or not text.strip():
        return ExerciseScope(reason="empty_text")

    norm = normalize(text)
    stripped = strip_articles(norm)

    if _CANCEL_RE is not None and _CANCEL_RE.search(stripped):
        return ExerciseScope(reason="explanation_intent_wins")

    words = frozenset(stripped.split())
    has_only = any(_matches_word(words, m) if " " not in m else m in stripped for m in _NORM_ONLY)
    has_verb = any(_matches_word(words, m) if " " not in m else m in stripped for m in _NORM_VERBS)
    mentions_item = any(noun in stripped or noun in norm for noun in _NORM_NOUNS)

    if not mentions_item or not (has_only or has_verb):
        return ExerciseScope(only=has_only, reason="no_scope_intent")

    number, part = _scan(text)
    source: ScopeSource = "text"
    if number is None and part is None:
        number, part = _scan_history(history)
        source = "history" if (number is not None or part is not None) else "none"

    reason = (
        "scope_resolved" if (number is not None or part is not None) else "scope_target_unknown"
    )
    return ExerciseScope(
        question_number=number,
        part=part,
        only=has_only,
        explicit=True,
        source=source,
        reason=reason,
    )
