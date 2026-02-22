"""
خدمة التحكم بالوصول المبني على الأدوار (RBAC Service).

[DEPRECATED] This service logic has been migrated to the User Service Microservice.
This file now serves as a holder for shared constants.
"""

from __future__ import annotations

from typing import Final

STANDARD_ROLE: Final[str] = "STANDARD_USER"
ADMIN_ROLE: Final[str] = "ADMIN"

USERS_READ: Final[str] = "USERS_READ"
USERS_WRITE: Final[str] = "USERS_WRITE"
ROLES_WRITE: Final[str] = "ROLES_WRITE"
AUDIT_READ: Final[str] = "AUDIT_READ"
AI_CONFIG_READ: Final[str] = "AI_CONFIG_READ"
AI_CONFIG_WRITE: Final[str] = "AI_CONFIG_WRITE"
ACCOUNT_SELF: Final[str] = "ACCOUNT_SELF"
QA_SUBMIT: Final[str] = "QA_SUBMIT"

DEFAULT_ROLE_PERMISSIONS: Final[dict[str, set[str]]] = {
    STANDARD_ROLE: {QA_SUBMIT, ACCOUNT_SELF},
    ADMIN_ROLE: {
        USERS_READ,
        USERS_WRITE,
        ROLES_WRITE,
        AUDIT_READ,
        AI_CONFIG_READ,
        AI_CONFIG_WRITE,
        QA_SUBMIT,
        ACCOUNT_SELF,
    },
}


class RBACService:
    """
    [DEPRECATED] RBAC Logic is now in User Service.
    """

    def __init__(self, *args, **kwargs):
        pass

    async def ensure_seed(self) -> None:
        pass

    def __getattr__(self, name):
        raise DeprecationWarning(f"RBACService.{name} is deprecated. Use UserServiceClient.")
