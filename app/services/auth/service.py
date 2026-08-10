"""
خدمة المصادقة المركزية (Facade).

تجمع هذه الخدمة بين المكونات الفرعية (Crypto, TokenManager, PasswordManager)
لتوفير واجهة موحدة للتعامل مع المصادقة.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_service import BaseService
from app.core.config import AppSettings, get_settings
from app.core.domain.user import RefreshToken, User, UserStatus
from app.security.passwords import pwd_context
from app.services.audit import AuditService
from app.services.auth.crypto import ACCESS_TOKEN_TYPE, REAUTH_TOKEN_TYPE, AuthCrypto
from app.services.auth.password_manager import PasswordManager
from app.services.auth.registration import RegistrationManager
from app.services.auth.schema import TokenBundle
from app.services.auth.token_manager import TokenManager
from app.services.rbac import ADMIN_ROLE, RBACService


class AuthService(BaseService):
    """
    طبقة المصادقة التطبيقية مع واجهات تسجيل الدخول، التسجيل، وتدوير الرموز.
    """

    def __init__(self, session: AsyncSession, settings: AppSettings | None = None) -> None:
        super().__init__(service_name="AuthService")
        self.session = session
        self.settings = settings or get_settings()
        self.rbac = RBACService(session)
        self.audit = AuditService(session)

        # Initialize Sub-components
        self.crypto = AuthCrypto(self.settings)
        self.token_manager = TokenManager(session)
        self.password_manager = PasswordManager(session)
        self.registration_manager = RegistrationManager(session, self.rbac)

    async def register_user(
        self,
        *,
        full_name: str,
        email: str,
        password: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> User:
        """إنشاء مستخدم قياسي جديد."""
        self._log_info("Registering new user", email_hash=self.crypto.hash_identifier(email))
        try:
            user = await self.registration_manager.register_user(
                full_name=full_name, email=email, password=password
            )
            await self.audit.record(
                actor_user_id=user.id,
                action="USER_REGISTERED",
                target_type="user",
                target_id=str(user.id),
                metadata={"email_hash": self.crypto.hash_identifier(email.lower().strip())},
                ip=ip,
                user_agent=user_agent,
            )
            return user
        except Exception as e:
            self._log_error(
                "Failed to register user", exc=e, email_hash=self.crypto.hash_identifier(email)
            )
            raise

    async def authenticate(
        self,
        *,
        email: str,
        password: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> User:
        """مصادقة المستخدم والتحقق من حالة الحساب."""
        await self.rbac.ensure_seed()
        normalized_email = email.lower().strip()
        result = await self.session.execute(select(User).where(User.email == normalized_email))
        user = result.scalar_one_or_none()

        if not user or not user.password_hash or not user.check_password(password):
            self._log_warning(
                "Authentication failed", email_hash=self.crypto.hash_identifier(normalized_email)
            )
            await self.audit.record(
                actor_user_id=None,
                action="AUTH_FAILED",
                target_type="user",
                target_id=None,
                metadata={"email_hash": self.crypto.hash_identifier(normalized_email)},
                ip=ip,
                user_agent=user_agent,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )

        if not user.is_active or user.status in {UserStatus.SUSPENDED, UserStatus.DISABLED}:
            self._log_warning("Authentication rejected: Account disabled", user_id=str(user.id))
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

        await self.audit.record(
            actor_user_id=user.id,
            action="AUTH_SUCCEEDED",
            target_type="user",
            target_id=str(user.id),
            metadata={"status": user.status.value},
            ip=ip,
            user_agent=user_agent,
        )
        return user

    async def issue_tokens(
        self,
        user: User,
        *,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> TokenBundle:
        """إصدار رموز الوصول والتحديث."""
        roles = await self.rbac.user_roles(user.id)
        permissions = await self.rbac.user_permissions(user.id)
        access_token = self.crypto.encode_access_token(user, roles, permissions)
        refresh_value = await self.token_manager.create_refresh_token(
            user, ip=ip, user_agent=user_agent, family_id=None
        )
        return {
            "access_token": access_token,
            "refresh_token": refresh_value,
            "token_type": "Bearer",
        }

    def _split_refresh_token(self, refresh_token: str) -> tuple[str, str]:
        """يفصل رمز التحديث إلى معرّف وسر للتحقق الداخلي."""
        return self.crypto.split_refresh_token(refresh_token)

    async def _get_refresh_record(self, token_id: str) -> RefreshToken | None:
        """يجلب سجل رمز التحديث بالمعرّف من مدير الرموز."""
        return await self.token_manager.get_refresh_record(token_id)

    async def update_profile(
        self,
        *,
        user: User,
        full_name: str | None,
        email: str | None,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> User:
        """تحديث بيانات الحساب الذاتي."""
        await self.rbac.ensure_seed()
        changed_fields: list[str] = []

        if full_name and full_name.strip() and full_name != user.full_name:
            user.full_name = full_name.strip()
            changed_fields.append("full_name")

        if email:
            normalized_email = email.lower().strip()
            if normalized_email != user.email:
                conflict = await self.session.execute(
                    select(User).where(User.email == normalized_email, User.id != user.id)
                )
                if conflict.scalar_one_or_none():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST, detail="Email already in use"
                    )
                user.email = normalized_email
                changed_fields.append("email")

        if not changed_fields:
            return user

        await self.session.commit()
        await self.session.refresh(user)
        await self.audit.record(
            actor_user_id=user.id,
            action="PROFILE_UPDATED",
            target_type="user",
            target_id=str(user.id),
            metadata={"fields": changed_fields},
            ip=ip,
            user_agent=user_agent,
        )
        return user

    async def issue_reauth_proof(
        self,
        *,
        user: User,
        password: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, int]:
        """إصدار رمز إعادة مصادقة قصير العمر."""
        if not user.check_password(password):
            await self.audit.record(
                actor_user_id=user.id,
                action="REAUTH_REJECTED",
                target_type="user",
                target_id=str(user.id),
                metadata={"reason": "bad_password"},
                ip=ip,
                user_agent=user_agent,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Re-authentication required"
            )

        token, expires_in = self.crypto.encode_reauth_token(user)
        await self.audit.record(
            actor_user_id=user.id,
            action="REAUTH_SUCCEEDED",
            target_type="user",
            target_id=str(user.id),
            metadata={"expires_in": expires_in},
            ip=ip,
            user_agent=user_agent,
        )
        return token, expires_in

    async def verify_reauth_proof(
        self,
        token: str,
        *,
        user: User,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """التحقق من رمز إعادة المصادقة."""
        try:
            payload = self.crypto.verify_jwt(token, expected_type=REAUTH_TOKEN_TYPE)
        except HTTPException as exc:
            await self.audit.record(
                actor_user_id=user.id,
                action="REAUTH_REJECTED",
                target_type="user",
                target_id=str(user.id),
                metadata={"reason": "invalid_or_expired"},
                ip=ip,
                user_agent=user_agent,
            )
            raise exc

        if payload.get("purpose") != "reauth" or payload.get("sub") != str(user.id):
            await self.audit.record(
                actor_user_id=user.id,
                action="REAUTH_REJECTED",
                target_type="user",
                target_id=str(user.id),
                metadata={"reason": "subject_mismatch"},
                ip=ip,
                user_agent=user_agent,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Re-authentication required"
            )

    async def refresh_session(
        self,
        *,
        refresh_token: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> TokenBundle:
        """تدوير رمز الوصول باستخدام رمز التحديث."""
        token_id, secret = self.crypto.split_refresh_token(refresh_token)
        record = await self.token_manager.get_refresh_record(token_id)

        if record is None:
            self._log_warning("Refresh token rejected: Missing", token_id=token_id)
            await self.audit.record(
                actor_user_id=None,
                action="REFRESH_REJECTED",
                target_type="refresh_token",
                target_id=token_id,
                metadata={"reason": "missing"},
                ip=ip,
                user_agent=user_agent,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )

        if record.revoked_at is not None or record.replaced_by_token_id is not None:
            self._log_warning(
                "Refresh token replay detected", user_id=str(record.user_id), token_id=token_id
            )
            await self.token_manager.revoke_family(record.family_id)
            await self.audit.record(
                actor_user_id=record.user_id,
                action="REFRESH_REPLAY_DETECTED",
                target_type="refresh_token",
                target_id=token_id,
                metadata={"reason": "token_already_rotated"},
                ip=ip,
                user_agent=user_agent,
            )
            await self.audit.record(
                actor_user_id=record.user_id,
                action="REFRESH_REJECTED",
                target_type="refresh_token",
                target_id=token_id,
                metadata={"reason": "replay_reuse", "family_id": record.family_id},
                ip=ip,
                user_agent=user_agent,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )

        if not record.is_active():
            await self.token_manager.revoke_record(record)
            await self.audit.record(
                actor_user_id=record.user_id,
                action="REFRESH_REJECTED",
                target_type="refresh_token",
                target_id=token_id,
                metadata={"reason": "expired_or_inactive"},
                ip=ip,
                user_agent=user_agent,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )

        if not pwd_context.verify(secret, record.hashed_token):
            await self.token_manager.revoke_record(record)
            await self.audit.record(
                actor_user_id=record.user_id,
                action="REFRESH_REJECTED",
                target_type="refresh_token",
                target_id=token_id,
                metadata={"reason": "hash_mismatch"},
                ip=ip,
                user_agent=user_agent,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )

        user = await self.session.get(User, record.user_id)
        if user is None or not user.is_active:
            await self.token_manager.revoke_record(record)
            await self.audit.record(
                actor_user_id=None,
                action="REFRESH_REJECTED",
                target_type="refresh_token",
                target_id=token_id,
                metadata={"reason": "user_inactive"},
                ip=ip,
                user_agent=user_agent,
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

        new_refresh_value = await self.token_manager.create_refresh_token(
            user,
            family_id=record.family_id,
            ip=ip,
            user_agent=user_agent,
        )
        new_token_id, _ = self.crypto.split_refresh_token(new_refresh_value)
        await self.token_manager.revoke_record(record, replaced_by=new_token_id)

        roles = await self.rbac.user_roles(user.id)
        permissions = await self.rbac.user_permissions(user.id)
        access_token = self.crypto.encode_access_token(user, roles, permissions)

        refreshed: TokenBundle = {
            "access_token": access_token,
            "refresh_token": new_refresh_value,
            "token_type": "Bearer",
        }
        await self.audit.record(
            actor_user_id=user.id,
            action="REFRESH_ROTATED",
            target_type="refresh_token",
            target_id=token_id,
            metadata={"status": user.status.value, "family_id": record.family_id},
            ip=ip,
            user_agent=user_agent,
        )
        return refreshed

    async def change_password(
        self,
        *,
        user: User,
        current_password: str,
        new_password: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """تغيير كلمة المرور مع إبطال جلسات التحديث النشطة."""
        if not user.check_password(current_password):
            await self.audit.record(
                actor_user_id=user.id,
                action="PASSWORD_CHANGE_REJECTED",
                target_type="user",
                target_id=str(user.id),
                metadata={"reason": "bad_current_password"},
                ip=ip,
                user_agent=user_agent,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect"
            )

        user.set_password(new_password)
        await self.session.commit()
        revoked = await self.token_manager.revoke_user_tokens(user)
        await self.audit.record(
            actor_user_id=user.id,
            action="PASSWORD_CHANGED",
            target_type="user",
            target_id=str(user.id),
            metadata={"revoked_refresh_tokens": revoked},
            ip=ip,
            user_agent=user_agent,
        )

    async def request_password_reset(
        self,
        *,
        email: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str | None, int | None]:
        """إنشاء رمز إعادة تعيين قصير العمر."""
        normalized_email = email.lower().strip()
        result = await self.session.execute(select(User).where(User.email == normalized_email))
        user = result.scalar_one_or_none()

        if not user:
            # Note: We do not log error here to avoid user enumeration, but we can log debug
            self._log_debug(
                "Password reset requested for unknown email",
                email_hash=self.crypto.hash_identifier(normalized_email),
            )
            await self.audit.record(
                actor_user_id=None,
                action="PASSWORD_RESET_REQUESTED",
                target_type="user",
                target_id=None,
                metadata={
                    "email_hash": self.crypto.hash_identifier(normalized_email),
                    "status": "unknown_user",
                },
                ip=ip,
                user_agent=user_agent,
            )
            return None, None

        token_value, expires_in, record = await self.password_manager.create_reset_token(
            user, ip, user_agent
        )

        await self.audit.record(
            actor_user_id=user.id,
            action="PASSWORD_RESET_REQUESTED",
            target_type="user",
            target_id=str(user.id),
            metadata={"token_id": record.token_id, "expires_at": record.expires_at.isoformat()},
            ip=ip,
            user_agent=user_agent,
        )
        return token_value, expires_in

    async def reset_password(
        self,
        *,
        token: str,
        new_password: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """تفعيل إعادة التعيين باستخدام رمز لمرة واحدة."""
        try:
            user = await self.password_manager.verify_and_redeem_token(token)
        except HTTPException as exc:
            await self.audit.record(
                actor_user_id=None,
                action="PASSWORD_RESET_REJECTED",
                target_type="password_reset",
                target_id=None,
                metadata={"reason": "invalid_or_expired"},
                ip=ip,
                user_agent=user_agent,
            )
            raise exc

        user.set_password(new_password)
        await self.session.commit()
        revoked = await self.token_manager.revoke_user_tokens(user)

        await self.audit.record(
            actor_user_id=user.id,
            action="PASSWORD_RESET_COMPLETED",
            target_type="user",
            target_id=str(user.id),
            # Note: We don't have the token record here easily unless verify returns it,
            # but user info is sufficient.
            metadata={"revoked_refresh_tokens": revoked},
            ip=ip,
            user_agent=user_agent,
        )

    async def logout(
        self, *, refresh_token: str, ip: str | None = None, user_agent: str | None = None
    ) -> None:
        """تسجيل الخروج بإبطال عائلة رمز التحديث."""
        try:
            token_id, _ = self.crypto.split_refresh_token(refresh_token)
            record = await self.token_manager.get_refresh_record(token_id)
            if record:
                await self.token_manager.revoke_family(record.family_id)
                await self.audit.record(
                    actor_user_id=record.user_id,
                    action="LOGOUT",
                    target_type="refresh_token",
                    target_id=token_id,
                    metadata={"status": "family_revoked", "family_id": record.family_id},
                    ip=ip,
                    user_agent=user_agent,
                )
        except HTTPException:
            pass  # Fail silently on logout if token is invalid format

    async def promote_to_admin(self, *, user: User) -> None:
        """ترقية مستخدم إلى مشرف."""
        await self.rbac.ensure_seed()
        await self.rbac.assign_role(user, ADMIN_ROLE)
        if not user.is_admin:
            await self.session.execute(update(User).where(User.id == user.id).values(is_admin=True))
            await self.session.commit()

    # Proxy methods for backward compatibility or direct usage
    def _hash_identifier(self, value: str) -> str:
        return self.crypto.hash_identifier(value)

    def verify_access_token(self, token: str) -> dict[str, object]:
        """يتحقّق من رمز وصول — **توقيعاً ونوعاً** (D-236 · ISS-152).

        كان يمرّر أي رمز موقّع، فكان رمز إعادة المصادقة ورمز الخدمة الداخلي
        يُقبَلان هنا كوصولٍ كامل.
        """
        return self.crypto.verify_jwt(token, expected_type=ACCESS_TOKEN_TYPE)
