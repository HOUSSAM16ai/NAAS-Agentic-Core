"""طبقة الذاكرة المشتركة — تأليف الرسالة قبل تخزينها (D-229).

`shared/` لا يستورد `app` ولا خدمةً شقيقة (D-189). هذه الوحدة stdlib خالصة.
"""

from __future__ import annotations

from shared.memory.authorship import (
    SYSTEM_AUTHORED_MARKERS,
    MemoryAuthorshipError,
    assert_student_authored,
    is_system_authored,
    strip_system_markers,
)

__all__ = [
    "SYSTEM_AUTHORED_MARKERS",
    "MemoryAuthorshipError",
    "assert_student_authored",
    "is_system_authored",
    "strip_system_markers",
]
