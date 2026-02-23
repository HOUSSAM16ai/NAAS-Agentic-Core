"""واجهة نماذج خدمة المستخدمين.

يوحّد هذا الملف تعريفات النماذج عبر إعادة تصدير نماذج النطاق الأساسية
بدلاً من إعادة تعريف نفس الجداول مرة أخرى داخل عملية الاختبارات.
هذا يمنع تضارب المعرّفات (Mapper Conflicts) عند تشغيل اختبارات المونوليث
واختبارات الخدمة المصغّرة في نفس جلسة Python.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import SQLModel

from app.core.domain.audit import AuditLog
from app.core.domain.user import (
    PasswordResetToken,
    Permission,
    RefreshToken,
    Role,
    RolePermission,
    User,
    UserRole,
    UserStatus,
)


def utc_now() -> datetime:
    """إرجاع الوقت الحالي بتوقيت UTC."""
    return datetime.now(UTC)


# Aliases for compatibility with existing imports
MicroUser = User
MicroRole = Role
MicroPermission = Permission
MicroUserRole = UserRole
MicroRolePermission = RolePermission
MicroRefreshToken = RefreshToken
MicroPasswordResetToken = PasswordResetToken
MicroAuditLog = AuditLog

__all__ = [
    "AuditLog",
    "MicroAuditLog",
    "MicroPasswordResetToken",
    "MicroPermission",
    "MicroRefreshToken",
    "MicroRole",
    "MicroRolePermission",
    "MicroUser",
    "MicroUserRole",
    "PasswordResetToken",
    "Permission",
    "RefreshToken",
    "Role",
    "RolePermission",
    "SQLModel",
    "User",
    "UserRole",
    "UserStatus",
    "utc_now",
]
