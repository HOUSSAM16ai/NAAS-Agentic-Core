"""
خدمة فك ترميز رموز الدخول وإدارة المصادقة المباشرة.

تقدم هذه الوحدة أدوات واضحة لاستخراج رموز Bearer وفكها بأمان
للاستخدام عبر HTTP أو WebSocket مع التزام كامل بمعايير الأمان.
"""

from __future__ import annotations

import jwt
from fastapi import HTTPException

ALGORITHM = "HS256"


def extract_bearer_token(auth_header: str | None) -> str:
    """
    استخراج رمز Bearer من ترويسة Authorization.

    Args:
        auth_header: قيمة الترويسة الواردة من العميل.

    Returns:
        str: رمز الدخول الخام بدون بادئة Bearer.

    Raises:
        HTTPException: إذا كانت الترويسة مفقودة أو غير صالحة.
    """

    if not auth_header:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    parts = auth_header.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")

    return parts[1]


def decode_user_id(token: str, secret_key: str) -> int:
    """
    فك ترميز رمز JWT واستخراج معرف المستخدم.

    Args:
        token: رمز JWT الخام.
        secret_key: المفتاح السري المستخدم للفك.

    Returns:
        int: معرف المستخدم المستخلص من الحمولة.

    Raises:
        HTTPException: عند فشل التحقق أو غياب معرف المستخدم.
    """

    try:
        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")

        return int(user_id)

    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid user ID in token") from exc


def decode_token_payload(token: str, secret_key: str) -> dict[str, object]:
    """
    فك ترميز رمز JWT وإرجاع الحمولة كاملة (موقّعة ومُتحقَّق من صلاحيتها).

    تُستخدم عند اتصال WebSocket لاشتقاق الهوية (sub + is_admin) من الـ JWT
    مباشرةً دون أي استعلام لقاعدة البيانات (ISS-100 / D-WS-CONN-001) — فالاتصال
    لا يجب أن يعتمد على Supabase، وإلا فإن أي تعثّر في قاعدة البيانات يُسقط كل
    اتصالات الـ WebSocket عند الإنشاء.

    Raises:
        HTTPException(401): عند فشل التحقق من التوقيع أو انتهاء الصلاحية.
    """
    try:
        return jwt.decode(token, secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
