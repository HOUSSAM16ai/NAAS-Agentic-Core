"""رموز القسائم المدفوعة مسبقاً — حتمية و dep-free (D-198).

لماذا القسيمة لا بوّابة دفع
---------------------------
شريحة كبيرة من أولياء الأمور في الجزائر لا تملك بطاقةً تعمل على الإنترنت، وبوّابة دفع
(SATIM/CIB) تتطلّب تعاقداً وامتثالاً واختباراتٍ لا تُنجَز في مستودعٍ برمجي. القسيمة
المدفوعة مسبقاً تُباع في مكتبةٍ أو عبر تحويل، ويستبدلها الطالب في ثانية — فتُفتَح
المنصّة تجارياً بلا انتظار طرفٍ ثالث. SATIM يبقى **مقعداً موثّقاً بلا كود**.

بنية الرمز
----------
`CFRG-XXXX-XXXX-XXXXC` حيث `C` محرف تحقّق. الشرطات للقراءة فقط وتُزال عند التطبيع.

**محرف التحقّق ليس أماناً — هو تجربة استعمال.** يمنع الخطأ المطبعي من أن يصل إلى قاعدة
البيانات فيُرَدّ «قسيمة مجهولة» على رمزٍ صحيح كُتب بحرفٍ خاطئ. الأمان الحقيقي في
**العشوائية التعموية** (`secrets`) وفي أنّ الاستبدال يتحقّق من الصفّ المُخزَّن.

الأبجدية بلا محارف مُلتبِسة (0/O · 1/I/L) لأنّ الرمز يُطبَع على ورق ويُنسَخ يدوياً.
"""

from __future__ import annotations

import re
import secrets
from typing import Final

__all__ = [
    "ALPHABET",
    "CODE_BODY_LENGTH",
    "CODE_GROUPS",
    "PREFIX",
    "VoucherError",
    "format_code",
    "generate_voucher_code",
    "is_well_formed",
    "normalize_code",
    "validate_code",
]


class VoucherError(ValueError):
    """رمز قسيمة مشوّه أو فاشل التحقّق."""


#: أبجدية بلا `0`/`O`/`1`/`I`/`L` — الرمز يُنسَخ يدوياً عن ورق.
ALPHABET: Final = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_ALPHABET_SIZE: Final = len(ALPHABET)

PREFIX: Final = "CFRG"
#: طول الجسم العشوائي (بلا محرف التحقّق). ١١ محرفاً من أبجدية ٣١ ⇒ ~٥٤ بت.
CODE_BODY_LENGTH: Final = 11
#: عدد المجموعات في الصيغة المقروءة.
CODE_GROUPS: Final = 4

_CLEAN_RE = re.compile(r"[^A-Z0-9]")


def _checksum(body: str) -> str:
    """محرف تحقّق مرجّح بالموضع — يكشف الحرف المُبدَّل **وتبديل حرفين متجاورين**.

    الترجيح بالموضع ضروري: مجموعٌ بسيط لا يرى «AB» صارت «BA»، وهي من أشيع أخطاء النسخ.
    """
    total = sum((index + 1) * ALPHABET.index(char) for index, char in enumerate(body))
    return ALPHABET[total % _ALPHABET_SIZE]


def normalize_code(raw: str) -> str:
    """يُطبِّع مُدخَل المستخدم: حالة الأحرف، المسافات، الشرطات، والبادئة."""
    if not raw:
        return ""
    cleaned = _CLEAN_RE.sub("", raw.upper())
    return cleaned.removeprefix(PREFIX)


def generate_voucher_code() -> str:
    """رمز قسيمة جديد بالصيغة المقروءة."""
    body = "".join(secrets.choice(ALPHABET) for _ in range(CODE_BODY_LENGTH))
    return format_code(body + _checksum(body))


def format_code(payload: str) -> str:
    """يُحوِّل الجسم+التحقّق إلى الصيغة المقروءة `CFRG-XXXX-...`."""
    groups = [payload[index : index + 4] for index in range(0, len(payload), 4)]
    return "-".join([PREFIX, *groups])


def is_well_formed(raw: str) -> bool:
    """هل الرمز صحيح البنية والتحقّق؟ لا يمسّ قاعدة بيانات."""
    payload = normalize_code(raw)
    if len(payload) != CODE_BODY_LENGTH + 1:
        return False
    if any(char not in ALPHABET for char in payload):
        return False
    return _checksum(payload[:-1]) == payload[-1]


def validate_code(raw: str) -> str:
    """
    يُرجِع الرمز المُطبَّع (جسم+تحقّق) أو يرفع.

    الفحص البنيوي يسبق أيّ استعلام: خطأٌ مطبعي يُردّ فوراً برسالةٍ صحيحة بدل أن يُقرأ
    «قسيمة مجهولة» — وهي رسالةٌ تدفع المستخدم لطلب استرداد بدل تصحيح حرف.
    """
    payload = normalize_code(raw)
    if len(payload) != CODE_BODY_LENGTH + 1 or any(char not in ALPHABET for char in payload):
        raise VoucherError("malformed voucher code")
    if _checksum(payload[:-1]) != payload[-1]:
        raise VoucherError("voucher code failed its checksum — check for a typo")
    return payload
