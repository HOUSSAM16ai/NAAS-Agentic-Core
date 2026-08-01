"""تطبيع نصّي حتمي مشترك — dep-free (stdlib فقط).

**لماذا هنا:** `shared/` ممنوع عليه استيراد `app/` أو أيّ خدمة (قانون الحدود)، فمُطبِّع
`app/services/capabilities/arabic_normalize.py` خارج متناوله. وكلّ سجلّ قانوني في
`shared/` يحتاج مطابقة علامات الطالب (فصحى · دارجة · فرنسية) يحتاج هذا المُطبِّع.

**ازدواجٌ واحد مقصود ومُبرَّر:** `shared/notation/registry.py` يحمل نسخته الخاصّة من
`normalize` لأنّ الملفّ **يُنسَخ حرفياً بايتاً ببايت** إلى
`microservices/notation_service/` وتفرض ذلك `check_notation_parity` — فاستيراده من هنا
يكسر النسخة المُوَرَّدة (لا `shared/` داخل الخدمة). أيّ وحدة `shared/` جديدة **غير**
مُوَرَّدة تستعمل هذه الوحدة ولا تكتب مُطبِّعاً ثالثاً.

**قرار التطبيع:** نستعمل NFKD ثمّ نحذف علامات التشكيل (فئة يونيكود `Mn`)، فيسقط بذلك
تشكيلُ العربية **وهمزاتُها** (أ → ا + همزة مُركِّبة) **ولكنات الفرنسية** (é → e) بخطوة
واحدة — بدل ثلاث جداول ترجمة تتقادم. يبقى صراحةً ما لا يتفكّك: ة · ى · ء · التطويل ·
الأرقام العربية-الهندية.
"""

from __future__ import annotations

import re
import unicodedata

__all__ = ["normalize", "strip_marks"]

_TATWEEL = "ـ"

#: ما لا يتفكّك تحت NFKD ويحتاج طيّاً صريحاً.
_EXPLICIT_FOLD = str.maketrans(
    {
        "ة": "ه",
        "ى": "ي",
        "ء": "",
        _TATWEEL: "",
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
        "۰": "0",
        "۱": "1",
        "۲": "2",
        "۳": "3",
        "۴": "4",
        "۵": "5",
        "۶": "6",
        "۷": "7",
        "۸": "8",
        "۹": "9",
    }
)

_WHITESPACE_RE = re.compile(r"\s+")


def strip_marks(text: str) -> str:
    """يحذف علامات التشكيل المُركِّبة (تشكيل العربية + لكنات اللاتينية) بعد تفكيك NFKD."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def normalize(text: str) -> str:
    """
    يُطبِّع نصّاً لمطابقة العلامات — حتمي، بلا فقدان للمعنى الرمزي.

    لا يحذف الحروف اللاتينية ولا الرموز الرياضية: كثير من العلامات القانونية لاتينية
    (`ln`, `derivee`) أو رمزية (`e^`, `z =`)، وحذفها يجعل المطابقة عمياء.
    """
    if not text:
        return ""
    folded = strip_marks(text).translate(_EXPLICIT_FOLD)
    return _WHITESPACE_RE.sub(" ", folded).strip().lower()
