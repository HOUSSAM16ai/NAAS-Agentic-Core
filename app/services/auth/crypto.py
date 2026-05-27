"""
وحدة التشفير والتعامل مع الرموز (Crypto/Token Logic).
"""

from __future__ import annotations

import os
import secrets
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Final

import jwt
from fastapi import HTTPException, status

from app.core.config import AppSettings
from app.core.domain.user import User

# ─────────────────────────────────────────────────────────────────────────────
# Token lifetime caps (D-WS-SESSION-001 — 2026-05-26)
# ─────────────────────────────────────────────────────────────────────────────
# Production cap: short-lived tokens reduce blast radius if leaked. 30 min.
# Development cap: long-lived tokens prevent kick-to-login mid-test cycles.
#   The user reported a catastrophic "kicked to login then returns" pattern
#   caused by 30-minute tokens expiring during testing sessions. In dev, an
#   8-hour cap matches typical work sessions without forcing relogin.
#
# Selection: ENVIRONMENT in {"development", "dev"} OR ALLOW_LONG_LIVED_TOKENS=1
#   → 480 minutes (8 hours).
# Otherwise:
#   → 30 minutes (production-safe).
#
# This is a SECURITY-RELEVANT setting. The cap is computed once at module
# import. Do not bypass via runtime environment manipulation in production.
# ─────────────────────────────────────────────────────────────────────────────
_ENV = (os.environ.get("ENVIRONMENT") or "").strip().lower()
_ALLOW_LONG = (os.environ.get("ALLOW_LONG_LIVED_TOKENS") or "").strip() in ("1", "true", "yes")
_IS_DEV_LIKE = _ENV in ("development", "dev", "local") or _ALLOW_LONG

ACCESS_EXPIRE_MINUTES: Final[int] = 480 if _IS_DEV_LIKE else 30
REAUTH_EXPIRE_MINUTES: Final[int] = 60 if _IS_DEV_LIKE else 10


class AuthCrypto:
    """
    مسؤول عن العمليات الحسابية والتشفيرية البحتة:
    - توليد الرموز (JWT)
    - تجزئة المعرفات (Hashing)
    - تقسيم رموز التحديث
    """

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def hash_identifier(self, value: str) -> str:
        """توليد بصمة نصية لحماية الهوية في سجلات التدقيق."""
        digest = sha256(value.encode()).hexdigest()
        return digest[:16]

    def encode_access_token(self, user: User, roles: list[str], permissions: set[str]) -> str:
        """تشفير رمز الوصول (Access Token) باستخدام إعدادات التطبيق."""
        expires_delta = timedelta(
            minutes=min(self.settings.ACCESS_TOKEN_EXPIRE_MINUTES, ACCESS_EXPIRE_MINUTES)
        )
        payload = {
            "sub": str(user.id),
            "roles": roles,
            "permissions": sorted(permissions),
            "jti": secrets.token_urlsafe(8),
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + expires_delta,
        }
        return jwt.encode(payload, self.settings.SECRET_KEY, algorithm="HS256")

    def encode_reauth_token(self, user: User) -> tuple[str, int]:
        """تشفير رمز إعادة المصادقة (Re-auth Token)."""
        expires_delta = timedelta(
            minutes=min(self.settings.REAUTH_TOKEN_EXPIRE_MINUTES, REAUTH_EXPIRE_MINUTES)
        )
        payload = {
            "sub": str(user.id),
            "purpose": "reauth",
            "jti": secrets.token_urlsafe(8),
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + expires_delta,
        }
        token = jwt.encode(payload, self.settings.SECRET_KEY, algorithm="HS256")
        return token, int(expires_delta.total_seconds())

    def split_refresh_token(self, token: str) -> tuple[str, str]:
        """فصل معرف الرمز عن السر الخاص به."""
        try:
            token_id_part, secret_part = token.split(":", maxsplit=1)
            return token_id_part, secret_part
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token format"
            ) from exc

    def verify_jwt(self, token: str) -> dict[str, object]:
        """التحقق من صحة توقيع JWT."""
        try:
            # Note: The original code casts the result of jwt.decode (which is object) to dict.
            return jwt.decode(token, self.settings.SECRET_KEY, algorithms=["HS256"])
        except jwt.PyJWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            ) from exc
