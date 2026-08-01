"""اختبارات رموز القسائم — D-198.

الرمز **سندٌ لحامله** يُطبَع على ورق ويُنسَخ يدوياً. لذلك يُختبَر شيئان: أنّه غير قابل
للتخمين، وأنّ الخطأ المطبعي يُكتشَف قبل أن يصل قاعدة البيانات فيُردّ «قسيمة مجهولة» على
رمزٍ صحيح.
"""

from __future__ import annotations

import pytest

from shared.voucher import (
    CODE_BODY_LENGTH,
    VoucherError,
    format_code,
    generate_voucher_code,
    is_well_formed,
    normalize_code,
    validate_code,
)
from shared.voucher.code import ALPHABET, PREFIX


def test_generated_codes_are_well_formed_and_prefixed() -> None:
    code = generate_voucher_code()
    assert code.startswith(f"{PREFIX}-")
    assert is_well_formed(code)
    assert len(normalize_code(code)) == CODE_BODY_LENGTH + 1


def test_codes_are_practically_unique() -> None:
    codes = {generate_voucher_code() for _ in range(3000)}
    assert len(codes) == 3000


def test_the_alphabet_excludes_ambiguous_glyphs() -> None:
    """الرمز يُنسَخ عن ورق — `0/O` و`1/I/L` تجعل ذلك لعبة حظّ."""
    assert not set(ALPHABET) & set("01OIL")
    for _ in range(50):
        assert not set(normalize_code(generate_voucher_code())) & set("01OIL")


# ── التطبيع ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "mutate",
    [
        str.lower,
        lambda code: code.replace("-", " "),
        lambda code: code.replace("-", ""),
        lambda code: f"   {code}   ",
        lambda code: code.replace("-", "  -- "),
    ],
)
def test_user_typed_variations_still_validate(mutate) -> None:
    """الوليّ يكتب الرمز يدوياً: المسافات والشرطات وحالة الأحرف ليست أخطاء."""
    code = generate_voucher_code()
    assert is_well_formed(mutate(code))


def test_normalize_strips_the_prefix() -> None:
    code = generate_voucher_code()
    assert not normalize_code(code).startswith(PREFIX)


def test_normalize_handles_empty_input() -> None:
    assert normalize_code("") == ""


# ── كشف الخطأ المطبعي ───────────────────────────────────────────────────────────


def test_a_single_character_typo_is_detected() -> None:
    payload = normalize_code(generate_voucher_code())
    for index in range(len(payload) - 1):
        replacement = "A" if payload[index] != "A" else "B"
        broken = payload[:index] + replacement + payload[index + 1 :]
        assert not is_well_formed(format_code(broken)), f"typo at {index} slipped through"


def test_a_transposition_is_detected() -> None:
    """
    مجموعٌ بسيط لا يرى «AB» صارت «BA» — وهي من أشيع أخطاء النسخ.

    لذلك الترجيح بالموضع، لا الجمع المجرّد.
    """
    checked = 0
    for _ in range(60):
        payload = normalize_code(generate_voucher_code())
        for index in range(len(payload) - 2):
            if payload[index] == payload[index + 1]:
                continue
            swapped = payload[:index] + payload[index + 1] + payload[index] + payload[index + 2 :]
            assert not is_well_formed(format_code(swapped))
            checked += 1
    assert checked > 0


@pytest.mark.parametrize(
    "bad",
    ["", "CFRG", "CFRG-XXXX", "not-a-code", "CFRG-0000-0000-0000", "A" * 40],
)
def test_malformed_codes_are_rejected(bad: str) -> None:
    assert not is_well_formed(bad)
    with pytest.raises(VoucherError):
        validate_code(bad)


def test_validate_returns_the_normalized_payload() -> None:
    code = generate_voucher_code()
    assert validate_code(code.lower()) == normalize_code(code)


def test_checksum_failure_names_the_typo() -> None:
    """
    رسالةٌ صحيحة تُوجِّه المستخدم لتصحيح حرف؛ «قسيمة مجهولة» تدفعه لطلب استرداد.
    """
    payload = normalize_code(generate_voucher_code())
    wrong = payload[:-1] + ("A" if payload[-1] != "A" else "B")
    with pytest.raises(VoucherError, match="checksum"):
        validate_code(format_code(wrong))
