"""السجلّ القانوني لرموز الرياضيات — المصدر الوحيد للحقيقة (D-185).

لماذا هذا الملف موجود
---------------------
الطالب في الترانسكليبت الحيّ سأل **«ماذا نقصد بحرف C»** — أي عن رمز طبعه النظام نفسه على
الشاشة — فتُجوهِل سؤاله وأُعيد عليه الحلّ الذي لم يفهمه (ISS-138). الجذر: كل نقاط المطابقة
في المنصّة كانت مفتاحها **اسم المفهوم** («التوافيق»/«تأليفة»/`combinaison`) لا **الرمز**،
فصار الطالب مُطالَباً بمعرفة اسم المفهوم كي يسأل عن معناه — دائرة مغلقة، ومن لا يعرف الاسم
يسأل بالرمز الذي يراه.

القانون الذي يُرسيه هذا الملف: **النظام يجب أن يكون قادراً على تعريف كل رمز يطبعه.**
تفرضه بوّابة `scripts/fitness/check_notation_definable.py` (رمز يُبَثّ بلا إدخال هنا ⇒ CI أحمر).

عقد الموقع (dep-free)
---------------------
هذا الملف يعيش في `shared/` على سابقة `shared/ai_models/model_chain.py` (D-174): مصدر واحد
يقرأ منه **المونوليث** (`app/services/skills/notation_skill.py`) و**الخدمة المصغّرة**
(`microservices/notation_service/`) معاً، وتُثبت بوّابة `check_notation_parity.py` أنّه لا
توجد نسخة ثالثة. لذلك: **stdlib فقط** — لا استيراد من `app/` ولا من `microservices/`
(قانون الحدود)، ومن ثمّ فالتطبيع هنا نسخة مصغّرة مكتفية بذاتها من محرّك
`app/services/capabilities/arabic_normalize.py` تكفي لمطابقة العلامات لا أكثر.

عقد السقراطية (D-113 → D-155)
------------------------------
**التعريف ليس إجابة.** شرح معنى رمزٍ لا يكشف أي نتيجة يستطيع الطالب توليدها، ولذلك كل
`example` هنا **محايد** (`C(5,2)` مثلاً) ولا يستعمل أبداً أرقام التمرين الجاري — فلا تسريب
لـ«14» ولا «165» عبر هذا الباب.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

#: نسخة السجلّ — تُبَثّ في `/health` و`/metrics` فيُعرَف أي سجلّ يخدم الطلب.
REGISTRY_VERSION = "1.0.0"


# ─────────────────────────────────────────────────────────────────────────────
# التطبيع (نسخة مصغّرة مكتفية بذاتها — `shared/` يجب أن يبقى dep-free)
# ─────────────────────────────────────────────────────────────────────────────

_DIACRITICS_RE = re.compile(r"[ً-ْٰ]")
_TATWEEL = "ـ"

_CHAR_FOLD = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ؤ": "و",
        "ئ": "ي",
        "ء": "",
        "ة": "ه",
        "ى": "ي",
        "٠": "0",
        "١": "1",
        "٢": "2",
        "٣": "3",
        "٤": "4",
        "٥": "5",
        "٦": "6",
        "٧": "7",
        "٨": "8",
        "٩": "9",
    }
)

#: رموز رياضية تُحوَّل إلى صورة لاتينية قانونية قبل المطابقة.
_MATH_FOLD = str.maketrans({"×": "*", "−": "-", "٫": ".", "𝑋": "x", "𝐶": "c"})


def normalize(text: str) -> str:
    """يُطبِّع نصّ الطالب لمطابقة العلامات — تشكيل/تطويل/همزات/أرقام + توحيد المسافات.

    مقصود أن يكون **حتمياً وبسيطاً**: لا يحذف الحروف اللاتينية (فالرمز نفسه لاتيني غالباً)
    ولا يحذف الرموز الرياضية (`!`, `∩`, `Ω`) لأنها مفتاح المطابقة هنا.
    """
    if not text:
        return ""
    base = unicodedata.normalize("NFKC", text)
    base = _DIACRITICS_RE.sub("", base).replace(_TATWEEL, "")
    base = base.translate(_CHAR_FOLD).translate(_MATH_FOLD)
    return re.sub(r"\s+", " ", base).strip().lower()


# ─────────────────────────────────────────────────────────────────────────────
# نيّة السؤال + حارس الالتباس
# ─────────────────────────────────────────────────────────────────────────────

#: علامات النيّة التعريفية — تُطابق ما يكتبه الطالب فعلاً (فصحى + دارجة + فرنسية).
#: مُصانة بالتوازي مع `_DEFINITIONAL_MARKERS` في `app/services/skills/semantic_property_skill.py`
#: (تلك أوسع لأنها تخدم المفاهيم أيضاً؛ هذه تخدم الرموز حصراً).
#: **قاعدة الانتقاء:** ممنوع أي علامة قصيرة تظهر داخل كلمات أخرى («عرف» داخل «نعرف»)
#: — الاتّساع هنا يخطف أدواراً حسابية، وهو ما كسر النظام أصلاً.
_DEFINITIONAL_INTENT: tuple[str, ...] = (
    "ماذا نقصد",
    "ما نقصد",
    "شنو نقصد",
    "ماذا يقصد",
    "شنو يقصد",
    "المقصود",
    "ما معنى",
    "ما معناه",
    "معنى",
    "ماذا يعني",
    "ماذا تعني",
    "واش يعني",
    "واش تعني",
    "واش راه",
    "شنو هي",
    "شنو هو",
    "شنو هاذ",
    "ما هو",
    "ما هي",
    "ماهو",
    "ماهي",
    "تعريف",
    "ماذا نسمي",
    "ما اسم",
    "signifie",
    "veut dire",
    "c est quoi",
)

#: نيّة حسابية — تُلغي مسار التعريف. «احسب احتمال A» طلب حساب لا طلب معنى.
#: مرآة لـ`_compute` في `app/infrastructure/clients/orchestrator/turn_preempts_concept.py`.
_COMPUTE_INTENT: tuple[str, ...] = (
    "احسب",
    "اوجد",
    "بين ان",
    "استنتج",
    "كم عدد",
    "كم هو",
    "احتمال الحادثه",
    "عين قانون",
)

#: سياق «الحادثة» — في تمارين البكالوريا تُسمّى الحوادث A/B/C/D، فسؤال «ما هي الحادثة C»
#: يقصد **الحدث** لا **الحرف**. هذا الحارس يمنع الالتباس الكارثي بين المعنيَين.
_EVENT_CONTEXT: tuple[str, ...] = (
    "الحادثه",
    "حادثه",
    "الحدث",
    "evenement",
)

#: إشارة صريحة إلى «الرمز/الحرف» — تُلزَم للحروف المفردة المُلتبِسة (C, X, A, P).
_SYMBOL_CUE: tuple[str, ...] = (
    "حرف",
    "الحرف",
    "رمز",
    "الرمز",
    "ترميز",
    "اشاره",
    "symbole",
    "lettre",
)


# ─────────────────────────────────────────────────────────────────────────────
# عقد الإدخال
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class NotationEntry:
    """رمز رياضي واحد: كيف يُكتَب، كيف يسأل عنه الطالب، وماذا يعني — بمثال محايد."""

    symbol: str
    aliases: tuple[str, ...]
    markers: tuple[str, ...]
    title: str
    definition: str
    example: str
    concept_id: str | None = None
    property_id: str | None = None
    #: حرف مفرد مُلتبِس (قد يكون اسم حادثة) ⇒ يتطلّب إشارة «حرف/رمز» صريحة.
    ambiguous_letter: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# السجلّ — الرموز التي يبثّها المعلّم فعلاً في مسار الاحتمالات
# ─────────────────────────────────────────────────────────────────────────────

NOTATION_REGISTRY: tuple[NotationEntry, ...] = (
    NotationEntry(
        symbol="C(n,k)",
        aliases=("c", "c(n,k)", "c_n^k", "cnk", "c n k", "combinaison"),
        markers=("c(", "c_", "c^", "التوافيق", "توافيق", "تاليفه", "تاليفات", "combinaison"),
        title="الرمز $C$ — التوافيق",
        definition=(
            "الرمز $C_{n}^{k}$ (ويُكتب أيضاً $C(n,k)$) يعني: "
            "**عدد طرق اختيار $k$ عنصراً من بين $n$ عنصراً دون أن يهمّنا الترتيب**. "
            "نستعمله كلّما كان السحب «دفعة واحدة» — لأن السحب دفعةً واحدة لا ترتيب فيه. "
            "وقانونه: $C_{n}^{k} = \\dfrac{n!}{k!\\,(n-k)!}$."
        ),
        example=(
            "مثال محايد: اختيار كتابَين من بين 5 كتب هو $C_{5}^{2} = "
            "\\dfrac{5 \\times 4}{2 \\times 1} = 10$ — عشر طرق، "
            "لأن «الكتاب الأول ثم الثاني» و«الثاني ثم الأول» اختيار واحد لا اثنان."
        ),
        concept_id="combinations",
        property_id="combinations",
        ambiguous_letter=True,
    ),
    NotationEntry(
        symbol="A(n,k)",
        aliases=("a(n,k)", "a_n^k", "ank", "arrangement"),
        markers=("a(", "a_n", "a^", "الترتيبات", "ترتيبات", "التراتيب", "arrangement"),
        title="الرمز $A$ — الترتيبات",
        definition=(
            "الرمز $A_{n}^{k}$ يعني: **عدد طرق اختيار $k$ عنصراً من بين $n$ مع الاهتمام "
            "بالترتيب**. نستعمله حين يكون السحب «على التوالي» — لأن ترتيب الظهور يهمّ حينها. "
            "وقانونه: $A_{n}^{k} = \\dfrac{n!}{(n-k)!}$."
        ),
        example=(
            "مثال محايد: ترتيب كتابَين من 5 على رفّ هو $A_{5}^{2} = 5 \\times 4 = 20$ — "
            "ضِعف $C_{5}^{2}$ تماماً، لأن كل اختيار يُعدّ هنا مرّتين حسب ترتيبه."
        ),
        concept_id="combinations",
    ),
    NotationEntry(
        symbol="n!",
        aliases=("n!", "factorielle", "factorial"),
        markers=("n!", "عاملي", "العاملي", "مضروب", "factorielle"),
        title="الرمز $!$ — العاملي",
        definition=(
            "الرمز $n!$ (ويُقرأ «$n$ عاملي») يعني: **جداء كل الأعداد الصحيحة من 1 إلى $n$**. "
            "أي $n! = n \\times (n-1) \\times \\dots \\times 2 \\times 1$. "
            "وهو لَبِنة بناء التوافيق والترتيبات معاً. واصطلاحاً $0! = 1$."
        ),
        example="مثال محايد: $4! = 4 \\times 3 \\times 2 \\times 1 = 24$.",
        concept_id="combinations",
    ),
    NotationEntry(
        symbol="P(A)",
        aliases=("p", "p(a)", "proba"),
        markers=("p(", "probabilite", "معنى الاحتمال", "مفهوم الاحتمال"),
        title="الرمز $P$ — الاحتمال",
        definition=(
            "الرمز $P(A)$ يعني: **احتمال وقوع الحادثة $A$** — أي "
            "$\\dfrac{\\text{عدد الحالات الملائمة}}{\\text{عدد الحالات الممكنة}}$ "
            "في حالة تساوي الإمكانيات. وقيمته دائماً بين 0 و 1: "
            "$0$ تعني مستحيلة، و$1$ تعني أكيدة."
        ),
        example=(
            "مثال محايد: عند رمي حجر نرد سليم، احتمال ظهور رقم زوجي هو "
            "$P = \\dfrac{3}{6} = \\dfrac{1}{2}$."
        ),
        concept_id="event_meaning",
    ),
    NotationEntry(
        symbol="P_A(B)",
        aliases=("p_a(b)", "pa(b)", "p(b|a)", "p(b/a)"),
        markers=("p_a", "pa(", "p(b|", "p(b/", "الاحتمال الشرطي", "احتمال شرطي", "شرطي"),
        title="الرمز $P_{A}(B)$ — الاحتمال الشرطي",
        definition=(
            "الرمز $P_{A}(B)$ (ويُكتب أيضاً $P(B \\mid A)$) يعني: "
            "**احتمال وقوع $B$ بعد أن نكون قد علمنا أنّ $A$ قد وقعت**. "
            "أي أننا لم نعد ننظر إلى كل الإمكانيات، بل إلى إمكانيات $A$ وحدها. "
            "وقانونه: $P_{A}(B) = \\dfrac{P(A \\cap B)}{P(A)}$ بشرط $P(A) \\neq 0$."
        ),
        example=(
            "مثال محايد: نرمي حجر نرد ونعلم أنّ النتيجة زوجية؛ فاحتمال أن تكون 2 صار "
            "$\\dfrac{1}{3}$ لا $\\dfrac{1}{6}$ — لأن الإمكانيات ضاقت إلى $\\{2,4,6\\}$."
        ),
        concept_id="conditional_probability",
        property_id="conditional_probability",
    ),
    NotationEntry(
        symbol="X",
        aliases=("x", "variable aleatoire"),
        markers=("المتغير العشوائي", "متغير عشوائي", "variable aleatoire"),
        title="الرمز $X$ — المتغيّر العشوائي",
        definition=(
            "الرمز $X$ يعني: **دالة تُرفِق بكل نتيجة ممكنة للتجربة عدداً**. "
            "فبدل أن نتكلّم عن «الكرات المسحوبة» نتكلّم عن **عدد** يصفها، "
            "فيصير بإمكاننا حساب متوسّطها وتوزيعها."
        ),
        example=(
            "مثال محايد: عند رمي قطعة نقد ثلاث مرّات، إذا كان $X$ هو عدد مرّات ظهور "
            "«الوجه»، فإنّ $X$ يأخذ إحدى القيم $0, 1, 2, 3$."
        ),
        concept_id="random_variable",
        property_id="random_variable",
        ambiguous_letter=True,
    ),
    NotationEntry(
        symbol="E(X)",
        aliases=("e(x)", "esperance"),
        markers=("e(", "الامل الرياضي", "امل رياضي", "الامل", "esperance"),
        title="الرمز $E(X)$ — الأمل الرياضي",
        definition=(
            "الرمز $E(X)$ يعني: **القيمة المتوسّطة التي نتوقّعها للمتغيّر $X$ "
            "لو كرّرنا التجربة عدداً كبيراً جداً من المرّات**. "
            "ويُحسَب بضرب كل قيمة في احتمالها ثم الجمع: "
            "$E(X) = \\sum x_i \\times P(X = x_i)$."
        ),
        example=(
            "مثال محايد: عند رمي حجر نرد سليم، "
            "$E(X) = \\dfrac{1+2+3+4+5+6}{6} = 3.5$ — "
            "وهو ليس قيمة ممكنة للنرد، بل متوسّط طويل المدى."
        ),
        concept_id="expected_value",
        property_id="expected_value",
    ),
    NotationEntry(
        symbol="Ω",
        aliases=("omega", "ω", "univers"),
        markers=("Ω", "ω", "omega", "مجموعة الإمكانيات", "فضاء العينة", "univers"),
        title="الرمز $\\Omega$ — مجموعة الإمكانيات",
        definition=(
            "الرمز $\\Omega$ (أوميغا) يعني: **مجموعة كل النتائج الممكنة للتجربة**. "
            "وهو المقام في حساب الاحتمال: كل حادثة جزء منه، "
            "واحتمال $\\Omega$ نفسه يساوي 1 لأنه يشمل كل ما يمكن أن يحدث."
        ),
        example=("مثال محايد: عند رمي حجر نرد، $\\Omega = \\{1,2,3,4,5,6\\}$ وعدد عناصره 6."),
        concept_id="event_meaning",
    ),
    NotationEntry(
        symbol="∩",
        aliases=("∩", "inter", "cap"),
        markers=("∩", "التقاطع", "تقاطع", "و في نفس الوقت", "معا في نفس", "intersection"),
        title="الرمز $\\cap$ — التقاطع",
        definition=(
            "الرمز $A \\cap B$ يعني: **الحادثة التي تقع فيها $A$ و$B$ معاً في آنٍ واحد**. "
            "أي العناصر المشتركة بين الحادثتين. وتُقرأ «$A$ **و** $B$»."
        ),
        example=(
            "مثال محايد: عند رمي نرد، إذا كانت $A$ «عدد زوجي» و$B$ «أكبر من 3»، "
            "فإنّ $A \\cap B = \\{4, 6\\}$."
        ),
        concept_id="event_meaning",
    ),
    NotationEntry(
        symbol="∪",
        aliases=("∪", "union", "cup"),
        markers=("∪", "الاتحاد", "اتحاد", "union"),
        title="الرمز $\\cup$ — الاتحاد",
        definition=(
            "الرمز $A \\cup B$ يعني: **الحادثة التي تقع فيها $A$ أو $B$ أو كلتاهما**. "
            "وتُقرأ «$A$ **أو** $B$» — و«أو» هنا غير حصرية، أي تشمل وقوعهما معاً."
        ),
        example=(
            "مثال محايد: عند رمي نرد، إذا كانت $A$ «عدد زوجي» و$B$ «أكبر من 3»، "
            "فإنّ $A \\cup B = \\{2, 4, 5, 6\\}$."
        ),
        concept_id="event_meaning",
    ),
    NotationEntry(
        symbol="Ā",
        aliases=("a barre", "complementaire", "ā"),
        markers=("المتممه", "متممه", "الحادثه العكسيه", "المعاكسه", "complementaire", "barre"),
        title="الرمز $\\bar{A}$ — الحادثة المتمّمة",
        definition=(
            "الرمز $\\bar{A}$ يعني: **الحادثة العكسية لـ$A$** — أي «$A$ لم تقع». "
            "وهي مفيدة جداً لأن $P(\\bar{A}) = 1 - P(A)$، "
            "فكثيراً ما يكون حساب العكس أسهل بكثير من حساب الحادثة نفسها."
        ),
        example=(
            "مثال محايد: إذا كان احتمال نجاح تجربة $0.7$، فاحتمال عدم نجاحها هو $1 - 0.7 = 0.3$."
        ),
        concept_id="event_meaning",
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# واجهة الاستعلام (حتمية 100% — لا LLM، لا I/O)
# ─────────────────────────────────────────────────────────────────────────────


# العلامات تُطبَّع **مرّة واحدة** عند الاستيراد. تطبيع النصّ يطوي «ى»→«ي» و«ة»→«ه»، فمقارنة
# علامة خام («ما معنى») بنصّ مُطبَّع («ما معني») لا تتطابق أبداً — وهذا بالضبط صنف الخلل
# الصامت الذي جعل الطبقات الحتمية تُخفق فيسقط الدور إلى الـLLM ثم إلى إفراغ الحل.
_NORM_DEFINITIONAL: tuple[str, ...] = tuple(normalize(m) for m in _DEFINITIONAL_INTENT)
_NORM_COMPUTE: tuple[str, ...] = tuple(normalize(m) for m in _COMPUTE_INTENT)
_NORM_EVENT: tuple[str, ...] = tuple(normalize(m) for m in _EVENT_CONTEXT)
_NORM_CUE: tuple[str, ...] = tuple(normalize(m) for m in _SYMBOL_CUE)
_NORM_MARKERS: tuple[tuple[NotationEntry, tuple[str, ...]], ...] = tuple(
    (entry, tuple(normalize(m) for m in entry.markers if m)) for entry in NOTATION_REGISTRY
)


def all_symbols() -> tuple[str, ...]:
    """كل الرموز المُعرَّفة في السجلّ."""
    return tuple(entry.symbol for entry in NOTATION_REGISTRY)


def define(symbol: str) -> NotationEntry | None:
    """يُرجع إدخال رمزٍ بعينه (مطابقة على `symbol` أو أحد `aliases`). `None` عند عدم المعرفة."""
    needle = normalize(symbol)
    if not needle:
        return None
    for entry in NOTATION_REGISTRY:
        if needle == normalize(entry.symbol) or needle in {normalize(a) for a in entry.aliases}:
            return entry
    return None


def _has_definitional_intent(norm: str) -> bool:
    """هل النصّ سؤال عن **معنى** شيء؟ (لا نُعرِّف ما لم يُسأل عنه)."""
    return any(marker in norm for marker in _NORM_DEFINITIONAL)


def _has_compute_intent(norm: str) -> bool:
    """هل النصّ طلب **حساب**؟ التعريف لا يخطف دوراً حسابياً (يحمي المحرك الرمزي)."""
    return any(marker in norm for marker in _NORM_COMPUTE)


def _mentions_event_context(norm: str) -> bool:
    """هل يتكلّم النصّ عن **حادثة** التمرين (A/B/C/D) لا عن **الحرف** بذاته؟"""
    return any(marker in norm for marker in _NORM_EVENT)


def _has_symbol_cue(norm: str) -> bool:
    """هل أشار الطالب صراحةً إلى «حرف»/«رمز»؟ (شرط الحروف المفردة المُلتبِسة)."""
    return any(cue in norm for cue in _NORM_CUE)


def _letter_is_present(norm: str, letter: str) -> bool:
    """هل يظهر الحرف المفرد ككلمة قائمة بذاتها؟ (يمنع مطابقة حرفٍ داخل كلمة)."""
    return re.search(rf"(?<![a-z0-9]){re.escape(letter)}(?![a-z0-9])", norm) is not None


def _sole_isolated_letter(norm: str) -> str | None:
    """الحرف اللاتيني المفرد **الوحيد** في النصّ — أو ``None`` عند غيابه أو تعدّده.

    شرط الوحدانية مقصود: «شنو يقصد بـ C» فيها حرف واحد فالمقصود بيّن، أمّا «ما معنى
    P(A)» ففيها حرفان معزولان فالاختيار بينهما تخمين — تُترَك لمطابقة العلامات التي
    تملك دليلاً بنيوياً (`p(a`). لا نُخمّن على طالب.
    """
    letters = set(re.findall(r"(?<![a-z0-9])([a-z])(?![a-z0-9])", norm))
    return letters.pop() if len(letters) == 1 else None


def resolve(text: str) -> NotationEntry | None:
    """يُحوّل سؤال الطالب الحرّ إلى إدخال رمزٍ مُعرَّف — أو `None` إن لم يكن سؤالاً عن رمز.

    القاعدة: **نيّة تعريفية + دليل على الرمز، وبلا نيّة حسابية**. والحروف المفردة المُلتبِسة
    (C, X) تتطلّب إشارة صريحة («حرف»/«رمز») **ولا** يكون النصّ متكلّماً عن حادثة التمرين —
    وإلّا التبس «ماذا نقصد بحرف C» (التوافيق) بـ«ما هي الحادثة C» (حدث التمرين)، وهو
    التباس كارثي على طالب البكالوريا.

    عند تعدّد المطابقات تفوز **الأطول** (الأكثر تخصيصاً): «الاحتمال الشرطي» تسبق «الاحتمال»
    مهما كان ترتيب السجلّ — فالترتيب ليس عقداً خفيّاً.
    """
    norm = normalize(text)
    if not norm or not _has_definitional_intent(norm) or _has_compute_intent(norm):
        return None

    in_event_context = _mentions_event_context(norm)
    has_cue = _has_symbol_cue(norm)

    # (1) المسار الصريح: «حرف/رمز X» — أقوى إشارة، وتُقدَّم على مطابقة العلامات.
    if has_cue and not in_event_context:
        for entry in NOTATION_REGISTRY:
            head = normalize(entry.symbol)[:1]
            if head and _letter_is_present(norm, head):
                return entry

    # (2) مطابقة العلامات (أسماء المفاهيم + الرموز البنيوية) — الأطول يفوز.
    best: NotationEntry | None = None
    best_len = 0
    for entry, markers in _NORM_MARKERS:
        if entry.ambiguous_letter and in_event_context:
            continue
        for marker in markers:
            if marker in norm and len(marker) > best_len:
                best, best_len = entry, len(marker)
    if best is not None:
        return best

    # (3) D-186 (ISS-139): سؤال تعريفي عن حرفٍ مفردٍ **بلا** كلمة «حرف/رمز» —
    # «شنو يقصد بـ C». كان يُرجِع None فيسقط الدور إلى مسار عام يطبع أرقام التمرين
    # (تسريب 165/14 عبر باب سؤالٍ تعريفي). حارس الحادثة يبقى نافذاً، وشرط وحدانية
    # الحرف يمنع التخمين — فلا يُخطَف «ما هي الحادثة C» ولا يُخمَّن في «P(A)».
    if not in_event_context:
        letter = _sole_isolated_letter(norm)
        if letter:
            for entry in NOTATION_REGISTRY:
                if normalize(entry.symbol)[:1] == letter:
                    return entry
    return None
