"""طبقة القسائم المدفوعة مسبقاً — توليد وتحقّق حتميّان (D-198)."""

from __future__ import annotations

from .code import (
    CODE_BODY_LENGTH,
    CODE_GROUPS,
    VoucherError,
    format_code,
    generate_voucher_code,
    is_well_formed,
    normalize_code,
    validate_code,
)

__all__ = [
    "CODE_BODY_LENGTH",
    "CODE_GROUPS",
    "VoucherError",
    "format_code",
    "generate_voucher_code",
    "is_well_formed",
    "normalize_code",
    "validate_code",
]
