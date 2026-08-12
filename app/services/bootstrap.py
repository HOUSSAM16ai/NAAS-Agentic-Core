"""
خدمة التهيئة الجذرية لحسابات النظام الحساسة.

تضمن هذه الوحدة وجود حساب مسؤول فعال بكامل صلاحيات RBAC مع تطبيع
البيانات وتعزيز الأمان التشغيلي لمنع فقدان الوصول في بيئات Codespaces
وغيرها. تعتمد على بيانات الاعتماد المخزنة في المتغيرات السرية وتعيد
المزامنة في كل تشغيل لضمان إمكانية الدخول دائماً.
"""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppSettings, get_settings
from app.core.domain.user import User, UserStatus
from app.services.audit import AuditService
from app.services.rbac import ADMIN_ROLE, RBACService


async def bootstrap_admin_account(
    session: AsyncSession, *, settings: AppSettings | None = None
) -> User:
    """
    يؤمّن حساب المشرف الجذري باستخدام متغيرات البيئة السرية.

    يقوم هذا الإجراء بالمهام التالية:
    1. تهيئة صلاحيات وأدوار RBAC قبل أي تعديل.
    2. إنشاء أو تحديث حساب المسؤول باستخدام البريد وكلمة المرور
       الواردة من الإعدادات (أو المتغيرات السرية في Codespaces).
    3. فرض حالة حساب نشطة مع منح دور ADMIN وضمان عدم إبطال الوصول.
    4. تسجيل حدث تدقيقي لشفافية التغييرات دون تسريب كلمات المرور.
    """

    cfg = settings or get_settings()
    rbac = RBACService(session)
    audit = AuditService(session)

    await rbac.ensure_seed()

    admin_email = cfg.ADMIN_EMAIL.lower().strip()
    admin_password = cfg.ADMIN_PASSWORD
    admin_name = cfg.ADMIN_NAME or "Root Administrator"

    if not admin_email or not admin_password:
        raise ValueError("Admin credentials are not configured; cannot bootstrap root access")

    result = await session.execute(select(User).where(User.email == admin_email))
    admin = result.scalar_one_or_none()

    changes: list[str] = []
    created = False

    # ⛔ سياسة أمان حاسمة (K-001): يجب ألا يكتب هذا الإجراء كلمة مرور الحساب
    # الجذري إلا إذا صرّح المُشغِّل بذلك صراحةً (ADMIN_FORCE_PASSWORD_SYNC=1 في
    # البيئة). إعادة الكتابة الصامتة عند كل تشغيل تدمّر كلمة المرور التي حدّدها
    # مالك النظام (سواءً ضبطها عبر الواجهة أو عبر متغير البيئة) وتفتح باب
    # استعادة وصولٍ غير مصرّحٍ به لكل من يتحكم بإعدادات النشر — وهو عطبٌ
    # كارثيّ في بيئات النشر المشتركة.
    force_password_sync = False
    if getattr(cfg, "ADMIN_FORCE_PASSWORD_SYNC", None):
        force_password_sync = str(cfg.ADMIN_FORCE_PASSWORD_SYNC).strip().lower() in (
            "1",
            "true",
            "yes",
        )

    if admin is None:
        admin = User(
            full_name=admin_name,
            email=admin_email,
            is_admin=True,
            is_active=True,
            status=UserStatus.ACTIVE,
        )
        admin.set_password(admin_password)
        session.add(admin)
        created = True
        changes.append("created")
    else:
        # حالة الحساب النشطة والأدوار تُصلَّح دائمًا (ضمان وصولٍ دائم)،
        # أما كلمة المرور فلا تُلمَس إلا بالتصريح الصريح أعلاه.
        if not admin.is_admin:
            admin.is_admin = True
            changes.append("is_admin_promoted")
        if not admin.is_active:
            admin.is_active = True
            changes.append("reactivated")
        if admin.status != UserStatus.ACTIVE:
            admin.status = UserStatus.ACTIVE
            changes.append("status_reset")
        if admin.full_name != admin_name:
            admin.full_name = admin_name
            changes.append("name_aligned")
        if force_password_sync and not admin.check_password(admin_password):
            admin.set_password(admin_password)
            changes.append("password_resynced")

    await session.commit()
    await session.refresh(admin)

    await rbac.assign_role(admin, ADMIN_ROLE)

    metadata: Mapping[str, object] = {
        "email_hash": sha256(admin.email.encode("utf-8")).hexdigest(),
        "changes": changes or ["noop"],
        "role": ADMIN_ROLE,
        "created": created,
    }

    await audit.record(
        actor_user_id=admin.id,
        action="ADMIN_BOOTSTRAPPED",
        target_type="user",
        target_id=str(admin.id),
        metadata=metadata,
        ip=None,
        user_agent=None,
    )

    return admin
