"""
موجه واجهة نظام إدارة المستخدمين مع حراسة RBAC وبوابة السياسات.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import desc, select

from app.api.schemas.ums import (
    AdminCreateUserRequest,
    ChangePasswordRequest,
    LoginRequest,
    LogoutRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    PasswordResetResponse,
    ProfileUpdateRequest,
    QuestionRequest,
    ReauthRequest,
    ReauthResponse,
    RefreshRequest,
    RegisterRequest,
    RoleAssignmentRequest,
    StatusUpdateRequest,
    TokenPair,
    UserOut,
)
from app.core.domain.audit import AuditLog
from app.core.domain.user import Role, User, UserRole, UserStatus
from app.deps.auth import CurrentUser, get_auth_service, get_current_user, require_permissions
from app.middleware.rate_limiter_middleware import rate_limit
from app.services.analytics.product_events import record_product_event
from app.services.audit import AuditService
from app.services.auth import AuthService
from app.services.policy import PolicyService
from app.services.rbac import (
    ACCOUNT_SELF,
    ADMIN_ROLE,
    AI_CONFIG_READ,
    AI_CONFIG_WRITE,
    AUDIT_READ,
    QA_SUBMIT,
    ROLES_WRITE,
    USERS_READ,
    USERS_WRITE,
)
from shared.analytics import EventName

router = APIRouter(tags=["User Management"])


def _audit_context(request: Request) -> tuple[str | None, str | None]:
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    return client_ip, user_agent


async def _enforce_recent_auth(
    *,
    request: Request,
    auth_service: AuthService,
    current: CurrentUser,
    provided_token: str | None,
    provided_password: str | None,
) -> None:
    """يتحقق من وجود دليل مصادقة حديث قبل تنفيذ عمليات حساسة."""

    client_ip, user_agent = _audit_context(request)
    token = provided_token or request.headers.get("X-Reauth-Token")
    password = provided_password or request.headers.get("X-Reauth-Password")

    if token:
        await auth_service.verify_reauth_proof(
            token,
            user=current.user,
            ip=client_ip,
            user_agent=user_agent,
        )
        return

    if password and current.user.check_password(password):
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Re-authentication required"
    )


@router.post("/auth/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
@rate_limit(max_requests=10, window_seconds=300, limiter_key="auth_register")
async def register_user(
    request: Request,
    payload: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenPair:
    client_ip, user_agent = _audit_context(request)
    user = await auth_service.register_user(
        full_name=payload.full_name,
        email=payload.email,
        password=payload.password,
        ip=client_ip,
        user_agent=user_agent,
    )
    tokens = await auth_service.issue_tokens(user, ip=client_ip, user_agent=user_agent)
    # D-197: أوّل نقطة في كلّ فوج احتفاظ. الكتابة معزولة ولا ترفع.
    await record_product_event(event_name=EventName.USER_SIGNED_UP, user_id=user.id)
    return TokenPair(**tokens)


@router.get("/users/me", response_model=UserOut)
async def get_me(
    current: CurrentUser = Depends(require_permissions(ACCOUNT_SELF)),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserOut:
    """إرجاع بيانات الحساب الحالية بما في ذلك الأدوار."""

    roles = await auth_service.rbac.user_roles(current.user.id)
    return UserOut(
        id=current.user.id,
        email=current.user.email,
        full_name=current.user.full_name,
        is_active=current.user.is_active,
        status=current.user.status,
        roles=roles,
    )


@router.patch("/users/me", response_model=UserOut)
async def update_me(
    request: Request,
    payload: ProfileUpdateRequest,
    current: CurrentUser = Depends(require_permissions(ACCOUNT_SELF)),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserOut:
    """تحديث الاسم الكامل أو البريد الإلكتروني للمستخدم الحالي مع تدقيق التغيير."""

    client_ip, user_agent = _audit_context(request)
    updated = await auth_service.update_profile(
        user=current.user,
        full_name=payload.full_name,
        email=payload.email,
        ip=client_ip,
        user_agent=user_agent,
    )
    roles = await auth_service.rbac.user_roles(updated.id)
    return UserOut(
        id=updated.id,
        email=updated.email,
        full_name=updated.full_name,
        is_active=updated.is_active,
        status=updated.status,
        roles=roles,
    )


@router.post("/users/me/change-password")
async def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    current: CurrentUser = Depends(require_permissions(ACCOUNT_SELF)),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    """تغيير كلمة المرور وإبطال رموز التحديث القديمة."""

    client_ip, user_agent = _audit_context(request)
    await auth_service.change_password(
        user=current.user,
        current_password=payload.current_password,
        new_password=payload.new_password,
        ip=client_ip,
        user_agent=user_agent,
    )
    return {"status": "password_changed"}


@router.post("/auth/login", response_model=TokenPair)
@rate_limit(max_requests=5, window_seconds=60, limiter_key="auth_login")
async def login(
    request: Request,
    payload: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenPair:
    client_ip, user_agent = _audit_context(request)
    user = await auth_service.authenticate(
        email=payload.email,
        password=payload.password,
        ip=client_ip,
        user_agent=user_agent,
    )
    tokens = await auth_service.issue_tokens(user, ip=client_ip, user_agent=user_agent)
    await record_product_event(event_name=EventName.USER_SIGNED_IN, user_id=user.id)
    return TokenPair(**tokens)


@router.post("/auth/reauth", response_model=ReauthResponse)
async def reauth(
    request: Request,
    payload: ReauthRequest,
    current: CurrentUser = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> ReauthResponse:
    client_ip, user_agent = _audit_context(request)
    token, expires_in = await auth_service.issue_reauth_proof(
        user=current.user, password=payload.password, ip=client_ip, user_agent=user_agent
    )
    return ReauthResponse(reauth_token=token, expires_in=expires_in)


@router.post("/auth/refresh", response_model=TokenPair)
@rate_limit(max_requests=20, window_seconds=60, limiter_key="auth_refresh")
async def refresh_token(
    request: Request,
    payload: RefreshRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenPair:
    client_ip, user_agent = _audit_context(request)
    tokens = await auth_service.refresh_session(
        refresh_token=payload.refresh_token,
        ip=client_ip,
        user_agent=user_agent,
    )
    return TokenPair(**tokens)


@router.post("/auth/logout")
async def logout(
    request: Request,
    payload: LogoutRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    client_ip, user_agent = _audit_context(request)
    await auth_service.logout(
        refresh_token=payload.refresh_token, ip=client_ip, user_agent=user_agent
    )
    return {"status": "logged_out"}


@router.post("/auth/password/forgot", response_model=PasswordResetResponse)
@rate_limit(max_requests=5, window_seconds=900, limiter_key="auth_password_forgot")
async def request_password_reset(
    request: Request,
    payload: PasswordResetRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> PasswordResetResponse:
    """طلب إعادة تعيين كلمة المرور دون كشف وجود الحساب."""

    client_ip, user_agent = _audit_context(request)
    token, expires_in = await auth_service.request_password_reset(
        email=payload.email, ip=client_ip, user_agent=user_agent
    )
    return PasswordResetResponse(reset_token=token, expires_in=expires_in)


@router.post("/auth/password/reset")
@rate_limit(max_requests=10, window_seconds=300, limiter_key="auth_password_reset")
async def reset_password(
    request: Request,
    payload: PasswordResetConfirmRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    """تطبيق إعادة تعيين كلمة المرور وإبطال جلسات التحديث القديمة."""

    client_ip, user_agent = _audit_context(request)
    await auth_service.reset_password(
        token=payload.token,
        new_password=payload.new_password,
        ip=client_ip,
        user_agent=user_agent,
    )
    return {"status": "password_reset"}


@router.get("/admin/users", response_model=list[UserOut])
async def list_users(
    _: CurrentUser = Depends(require_permissions(USERS_READ)),
    auth_service: AuthService = Depends(get_auth_service),
) -> list[UserOut]:
    result = await auth_service.session.execute(
        select(User, Role.name)
        .select_from(User)
        .join(UserRole, UserRole.user_id == User.id, isouter=True)
        .join(Role, Role.id == UserRole.role_id, isouter=True)
    )
    rows = result.all()
    users: dict[int, User] = {}
    roles_map: dict[int, list[str]] = {}
    for user, role_name in rows:
        if user.id is None:
            continue
        users[user.id] = user
        if role_name:
            roles_map.setdefault(user.id, []).append(role_name)
        else:
            roles_map.setdefault(user.id, [])

    output: list[UserOut] = []
    for user_id, user in users.items():
        output.append(
            UserOut(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                is_active=user.is_active,
                status=user.status,
                roles=sorted(set(roles_map.get(user_id, []))),
            )
        )
    return output


@router.post("/admin/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user_admin(
    request: Request,
    payload: AdminCreateUserRequest,
    current: CurrentUser = Depends(require_permissions(USERS_WRITE, ROLES_WRITE)),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserOut:
    client_ip, user_agent = _audit_context(request)
    if payload.is_admin:
        await _enforce_recent_auth(
            request=request,
            auth_service=auth_service,
            current=current,
            provided_token=None,
            provided_password=None,
        )

    user = await auth_service.register_user(
        full_name=payload.full_name,
        email=payload.email,
        password=payload.password,
    )
    if payload.is_admin:
        await auth_service.promote_to_admin(user=user)
    roles = await auth_service.rbac.user_roles(user.id)
    audit = AuditService(auth_service.session)
    await audit.record(
        actor_user_id=current.user.id,
        action="USER_CREATED",
        target_type="user",
        target_id=str(user.id),
        metadata={"is_admin": payload.is_admin},
        ip=client_ip,
        user_agent=user_agent,
    )
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        status=user.status,
        roles=roles,
    )


@router.patch("/admin/users/{user_id}/status", response_model=UserOut)
async def update_user_status(
    request: Request,
    user_id: int,
    payload: StatusUpdateRequest,
    current: CurrentUser = Depends(require_permissions(USERS_WRITE)),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserOut:
    user = await auth_service.session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.status = payload.status
    user.is_active = payload.status == UserStatus.ACTIVE
    await auth_service.session.commit()
    roles = await auth_service.rbac.user_roles(user.id)
    client_ip, user_agent = _audit_context(request)
    audit = AuditService(auth_service.session)
    await audit.record(
        actor_user_id=current.user.id,
        action="USER_STATUS_UPDATED",
        target_type="user",
        target_id=str(user.id),
        metadata={"status": payload.status.value},
        ip=client_ip,
        user_agent=user_agent,
    )
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        status=user.status,
        roles=roles,
    )


@router.post("/admin/users/{user_id}/roles", response_model=UserOut)
async def assign_role(
    request: Request,
    user_id: int,
    payload: RoleAssignmentRequest,
    current: CurrentUser = Depends(require_permissions(USERS_WRITE, ROLES_WRITE)),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserOut:
    target = await auth_service.session.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.role_name == ADMIN_ROLE:
        await _enforce_recent_auth(
            request=request,
            auth_service=auth_service,
            current=current,
            provided_token=payload.reauth_token,
            provided_password=payload.reauth_password,
        )
        if not payload.justification or len(payload.justification.strip()) < 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Justification required for admin assignment",
            )
        await auth_service.promote_to_admin(user=target)
    else:
        await auth_service.rbac.assign_role(target, payload.role_name)

    roles = await auth_service.rbac.user_roles(target.id)
    client_ip, user_agent = _audit_context(request)
    audit = AuditService(auth_service.session)
    await audit.record(
        actor_user_id=current.user.id,
        action="USER_ROLE_ASSIGNED",
        target_type="user",
        target_id=str(target.id),
        metadata={"role": payload.role_name, "justification": payload.justification},
        ip=client_ip,
        user_agent=user_agent,
    )
    return UserOut(
        id=target.id,
        email=target.email,
        full_name=target.full_name,
        is_active=target.is_active,
        status=target.status,
        roles=roles,
    )


@router.get("/admin/audit", response_model=list[dict])
async def list_audit(
    _: CurrentUser = Depends(require_permissions(AUDIT_READ)),
    auth_service: AuthService = Depends(get_auth_service),
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="limit out of range")
    if offset < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="offset out of range")
    result = await auth_service.session.execute(
        select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit).offset(offset)
    )
    rows = result.scalars().all()
    return [row.model_dump() for row in rows]


@router.get("/admin/ai-config")
async def get_ai_config(
    _: CurrentUser = Depends(require_permissions(AI_CONFIG_READ)),
) -> dict[str, str]:
    return {"status": "ok", "message": "AI config readable"}


@router.put("/admin/ai-config")
async def update_ai_config(
    _: CurrentUser = Depends(require_permissions(AI_CONFIG_WRITE)),
) -> dict[str, str]:
    return {"status": "ok", "message": "AI config updated"}


@router.post("/qa/question")
async def ask_question(
    request: Request,
    payload: QuestionRequest,
    current: CurrentUser = Depends(require_permissions(QA_SUBMIT)),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    policy = PolicyService()
    primary_role = ADMIN_ROLE if ADMIN_ROLE in current.roles else "STANDARD_USER"
    decision = policy.enforce_policy(user_role=primary_role, question=payload.question)
    client_ip, user_agent = _audit_context(request)

    if not decision.allowed:
        audit = AuditService(auth_service.session)
        await audit.record(
            actor_user_id=current.user.id,
            action="POLICY_BLOCK",
            target_type="question",
            target_id=str(decision.redaction_hash),
            metadata={"reason": decision.reason, "classification": decision.classification},
            ip=client_ip,
            user_agent=user_agent,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=decision.reason)

    return {
        "status": "accepted",
        "classification": decision.classification,
        "message": "question accepted",
    }
