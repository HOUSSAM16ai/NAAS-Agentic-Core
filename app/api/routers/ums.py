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
from app.core.database import get_db
from app.core.domain.audit import AuditLog
from app.deps.auth import CurrentUser, get_auth_service, get_current_user, require_permissions
from app.middleware.rate_limiter_middleware import rate_limit
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

router = APIRouter(tags=["User Management"])


def _audit_context(request: Request) -> tuple[str | None, str | None]:
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    return client_ip, user_agent


def _get_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    return auth_header.split(" ")[1]


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

    # For password check, we need to verify against microservice via login
    # But current.user doesn't have password.
    # We must use client.login with provided password.
    if password:
        try:
            await auth_service.client.login(current.user.email, password)
            return
        except Exception:
            pass

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
    return TokenPair(**tokens)


@router.get("/users/me", response_model=UserOut)
async def get_me(
    current: CurrentUser = Depends(require_permissions(ACCOUNT_SELF)),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserOut:
    """إرجاع بيانات الحساب الحالية بما في ذلك الأدوار."""
    return UserOut(
        id=current.user.id,
        email=current.user.email,
        full_name=current.user.full_name,
        is_active=current.user.is_active,
        status=current.user.status,  # Assuming status matches UserStatus enum value or string
        roles=current.roles,
    )


@router.patch("/users/me", response_model=UserOut)
async def update_me(
    request: Request,
    payload: ProfileUpdateRequest,
    current: CurrentUser = Depends(require_permissions(ACCOUNT_SELF)),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserOut:
    """تحديث الاسم الكامل أو البريد الإلكتروني للمستخدم الحالي مع تدقيق التغيير."""
    token = _get_token(request)
    _client_ip, _user_agent = _audit_context(request)

    # Use client directly via auth_service
    updated_out = await auth_service.client.update_me(
        token=token, full_name=payload.full_name, email=payload.email
    )

    # Return UserOut directly from client response
    # Client UserOut matches schema UserOut mostly
    return UserOut(
        id=updated_out.id,
        email=updated_out.email,
        full_name=updated_out.full_name,
        is_active=updated_out.is_active,
        status=updated_out.status,
        roles=updated_out.roles,
    )


@router.post("/users/me/change-password")
async def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    current: CurrentUser = Depends(require_permissions(ACCOUNT_SELF)),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    """تغيير كلمة المرور وإبطال رموز التحديث القديمة."""
    token = _get_token(request)
    _client_ip, _user_agent = _audit_context(request)

    await auth_service.client.change_password(
        token=token, current_pass=payload.current_password, new_pass=payload.new_password
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

    _client_ip, _user_agent = _audit_context(request)
    token, expires_in = await auth_service.client.request_password_reset(email=payload.email)
    return PasswordResetResponse(reset_token=token, expires_in=expires_in)


@router.post("/auth/password/reset")
@rate_limit(max_requests=10, window_seconds=300, limiter_key="auth_password_reset")
async def reset_password(
    request: Request,
    payload: PasswordResetConfirmRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    """تطبيق إعادة تعيين كلمة المرور وإبطال جلسات التحديث القديمة."""

    _client_ip, _user_agent = _audit_context(request)
    await auth_service.client.reset_password(token=payload.token, new_password=payload.new_password)
    return {"status": "password_reset"}


@router.get("/admin/users", response_model=list[UserOut])
async def list_users(
    request: Request,
    _: CurrentUser = Depends(require_permissions(USERS_READ)),
    auth_service: AuthService = Depends(get_auth_service),
) -> list[UserOut]:
    token = _get_token(request)
    users_out = await auth_service.client.list_users(token)

    # Map Client UserOut to Schema UserOut (should match)
    return [
        UserOut(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            is_active=u.is_active,
            status=u.status,
            roles=u.roles,
        )
        for u in users_out
    ]


@router.post("/admin/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user_admin(
    request: Request,
    payload: AdminCreateUserRequest,
    current: CurrentUser = Depends(require_permissions(USERS_WRITE, ROLES_WRITE)),
    auth_service: AuthService = Depends(get_auth_service),
    db=Depends(get_db),  # Inject DB for AuditService
) -> UserOut:
    token = _get_token(request)
    client_ip, user_agent = _audit_context(request)

    if payload.is_admin:
        await _enforce_recent_auth(
            request=request,
            auth_service=auth_service,
            current=current,
            provided_token=None,
            provided_password=None,
        )

    # Use Client's create_user_admin
    new_user_out = await auth_service.client.create_user_admin(
        token=token,
        full_name=payload.full_name,
        email=payload.email,
        password=payload.password,
        is_admin=payload.is_admin,
    )

    audit = AuditService(db)
    await audit.record(
        actor_user_id=current.user.id,
        action="USER_CREATED",
        target_type="user",
        target_id=str(new_user_out.id),
        metadata={"is_admin": payload.is_admin},
        ip=client_ip,
        user_agent=user_agent,
    )

    return UserOut(
        id=new_user_out.id,
        email=new_user_out.email,
        full_name=new_user_out.full_name,
        is_active=new_user_out.is_active,
        status=new_user_out.status,
        roles=new_user_out.roles,
    )


@router.patch("/admin/users/{user_id}/status", response_model=UserOut)
async def update_user_status(
    request: Request,
    user_id: int,
    payload: StatusUpdateRequest,
    current: CurrentUser = Depends(require_permissions(USERS_WRITE)),
    auth_service: AuthService = Depends(get_auth_service),
    db=Depends(get_db),
) -> UserOut:
    token = _get_token(request)

    updated_out = await auth_service.client.update_user_status(
        token=token, user_id=user_id, status=payload.status.value
    )

    client_ip, user_agent = _audit_context(request)
    audit = AuditService(db)
    await audit.record(
        actor_user_id=current.user.id,
        action="USER_STATUS_UPDATED",
        target_type="user",
        target_id=str(user_id),
        metadata={"status": payload.status.value},
        ip=client_ip,
        user_agent=user_agent,
    )
    return UserOut(
        id=updated_out.id,
        email=updated_out.email,
        full_name=updated_out.full_name,
        is_active=updated_out.is_active,
        status=updated_out.status,
        roles=updated_out.roles,
    )


@router.post("/admin/users/{user_id}/roles", response_model=UserOut)
async def assign_role(
    request: Request,
    user_id: int,
    payload: RoleAssignmentRequest,
    current: CurrentUser = Depends(require_permissions(USERS_WRITE, ROLES_WRITE)),
    auth_service: AuthService = Depends(get_auth_service),
    db=Depends(get_db),
) -> UserOut:
    token = _get_token(request)

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

    # Use client assign_role (handles admin promotion if role is ADMIN internally? No, explicit role)
    # But promoting to ADMIN in client assigns ADMIN role.

    updated_out = await auth_service.client.assign_role(
        token=token,
        user_id=user_id,
        role_name=payload.role_name,
        justification=payload.justification,
    )

    client_ip, user_agent = _audit_context(request)
    audit = AuditService(db)
    await audit.record(
        actor_user_id=current.user.id,
        action="USER_ROLE_ASSIGNED",
        target_type="user",
        target_id=str(user_id),
        metadata={"role": payload.role_name, "justification": payload.justification},
        ip=client_ip,
        user_agent=user_agent,
    )
    return UserOut(
        id=updated_out.id,
        email=updated_out.email,
        full_name=updated_out.full_name,
        is_active=updated_out.is_active,
        status=updated_out.status,
        roles=updated_out.roles,
    )


@router.get("/admin/audit", response_model=list[dict])
async def list_audit(
    _: CurrentUser = Depends(require_permissions(AUDIT_READ)),
    db=Depends(get_db),  # Direct DB for Audit
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="limit out of range")
    if offset < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="offset out of range")

    # AuditLog is still in Monolith DB (local)
    result = await db.execute(
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
    db=Depends(get_db),
) -> dict[str, str]:
    policy = PolicyService()
    primary_role = ADMIN_ROLE if ADMIN_ROLE in current.roles else "STANDARD_USER"
    decision = policy.enforce_policy(user_role=primary_role, question=payload.question)
    client_ip, user_agent = _audit_context(request)

    if not decision.allowed:
        audit = AuditService(db)
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
