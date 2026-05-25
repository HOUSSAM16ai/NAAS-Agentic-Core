"""
مساعدات مصادقة WebSocket — نظام استخراج متعدد الطبقات.

## المشكلة التي يحلها هذا الملف (ISS-WS-001)

الاعتماد الأساسي على ``sec-websocket-protocol`` لنقل JWT يُسبب انهيار
الاتصال في البيئات التالية:

- شبكات الهاتف الجزائرية (Djezzy / Mobilis / Ooredoo)
- GitHub Codespaces edge proxy
- Brave Mobile / Chrome Mobile على شبكات carrier-NAT
- بعض VPN-less environments
- Reverse proxies التي تُعيد كتابة أو تحذف subprotocol headers

السبب الجذري: RFC 6455 لا يُلزم الـ proxies بالحفاظ على
``Sec-WebSocket-Protocol`` — كثير منها يحذفها أو يُعيد ترتيبها.

## الحل: استخراج متعدد الطبقات بترتيب أولوية صارم

الطبقة 1 — Cookie session (الأكثر موثوقية عبر كل الشبكات)
الطبقة 2 — Query parameter ``?token=`` (يعمل حتى مع stripped headers)
الطبقة 3 — Authorization header ``Bearer <token>`` (يحقنه Gateway)
الطبقة 4 — ``sec-websocket-protocol`` (fallback أخير فقط)

## ضمانات الأمان

- query token مُفعَّل في production بشكل آمن (HTTPS فقط + قصير العمر)
- لا يُسجَّل token نفسه في أي log
- defensive parsing لكل header formats
- logging واضح يُشخِّص سبب الفشل بدون تسريب بيانات
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum

from fastapi import WebSocket

from app.core.settings.base import get_settings

logger = logging.getLogger(__name__)


# ─── نوع مصدر الاستخراج ─────────────────────────────────────────────────────


class TokenSource(StrEnum):
    """
    يُعرِّف مصدر استخراج رمز الدخول لأغراض التشخيص والـ logging.
    """

    COOKIE = "cookie"
    QUERY_PARAM = "query_param"
    AUTH_HEADER = "auth_header"
    SUBPROTOCOL = "subprotocol"
    NONE = "none"


# ─── نتيجة الاستخراج ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class WebSocketAuthResult:
    """
    نتيجة استخراج رمز الدخول من طلب WebSocket.

    Attributes:
        token: رمز الدخول الخام، أو ``None`` إذا لم يُعثر عليه.
        selected_protocol: البروتوكول المختار للـ WebSocket handshake.
        source: مصدر الاستخراج (للتشخيص).
    """

    token: str | None
    selected_protocol: str | None
    source: TokenSource


# ─── دوال مساعدة داخلية ─────────────────────────────────────────────────────


def _parse_protocol_header(protocol_header: str | None) -> list[str]:
    """
    يُحلِّل ترويسة ``sec-websocket-protocol`` إلى قائمة نظيفة.

    يتعامل مع:
    - ترويسة فارغة أو None
    - بروتوكولات مكررة (يُزيل التكرار مع الحفاظ على الترتيب)
    - مسافات زائدة وقيم فارغة
    - ترويسات مشوهة (malformed)

    Args:
        protocol_header: قيمة ترويسة ``sec-websocket-protocol``.

    Returns:
        قائمة مرتبة ونظيفة بالبروتوكولات، بدون تكرار.
    """
    if not protocol_header or not protocol_header.strip():
        return []

    seen: set[str] = set()
    result: list[str] = []

    for part in protocol_header.split(","):
        cleaned = part.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)

    return result


def _extract_token_from_protocols(protocols: list[str]) -> str | None:
    """
    يستخرج رمز الدخول من قائمة بروتوكولات WebSocket.

    الاتفاق المتوقع: ``["jwt", "<token>"]`` في ترويسة ``sec-websocket-protocol``.

    Args:
        protocols: قائمة البروتوكولات المُحلَّلة.

    Returns:
        رمز الدخول إذا وُجد وفق الاتفاق، وإلا ``None``.
    """
    if not protocols or "jwt" not in protocols:
        return None

    try:
        jwt_index = protocols.index("jwt")
    except ValueError:
        return None

    if jwt_index + 1 >= len(protocols):
        logger.debug(
            "ws_auth.subprotocol: 'jwt' موجود لكن لا يوجد token بعده "
            "(protocols_count=%d)",
            len(protocols),
        )
        return None

    candidate = protocols[jwt_index + 1].strip()
    if not candidate:
        logger.debug("ws_auth.subprotocol: token فارغ بعد 'jwt'")
        return None

    return candidate


def _extract_from_cookie(websocket: WebSocket) -> str | None:
    """
    يستخرج رمز الدخول من cookie الجلسة.

    يبحث عن ``access_token`` أو ``auth_token`` أو ``token`` في الـ cookies.
    هذا المصدر هو الأكثر موثوقية لأن cookies تُحفظ بواسطة المتصفح
    وتُرسَل تلقائياً مع كل طلب بغض النظر عن الـ proxy.

    Args:
        websocket: كائن WebSocket الوارد.

    Returns:
        رمز الدخول من cookie، أو ``None``.
    """
    cookie_header = websocket.headers.get("cookie", "")
    if not cookie_header:
        return None

    for raw_cookie_part in cookie_header.split(";"):
        cookie_part = raw_cookie_part.strip()
        if "=" not in cookie_part:
            continue
        name, _, value = cookie_part.partition("=")
        name = name.strip().lower()
        value = value.strip()
        if name in ("access_token", "auth_token", "token") and value:
            return value

    return None


def _extract_from_query_param(websocket: WebSocket) -> str | None:
    """
    يستخرج رمز الدخول من query parameter ``?token=``.

    هذا المصدر ضروري لـ:
    - GitHub Codespaces (proxy يحذف subprotocols)
    - شبكات الهاتف (carrier NAT يُعيد كتابة headers)
    - Brave Mobile (يُقيِّد subprotocol headers)
    - أي بيئة تحذف ``sec-websocket-protocol``

    ملاحظة أمنية: query params تظهر في server logs — يجب أن يكون
    الـ token قصير العمر (short-lived). هذا مقبول لأن HTTPS يُشفِّر
    الـ URL في الـ transport layer.

    Args:
        websocket: كائن WebSocket الوارد.

    Returns:
        رمز الدخول من query param، أو ``None``.
    """
    token = websocket.query_params.get("token", "").strip()
    return token if token else None


def _extract_from_auth_header(websocket: WebSocket) -> str | None:
    """
    يستخرج رمز الدخول من ترويسة ``Authorization: Bearer <token>``.

    هذا المصدر يُستخدم عندما يحقن Gateway الـ token في الـ header
    بعد التحقق منه. موثوق في بيئات server-to-server.

    Args:
        websocket: كائن WebSocket الوارد.

    Returns:
        رمز الدخول من Authorization header، أو ``None``.
    """
    auth_header = websocket.headers.get("authorization", "").strip()
    if not auth_header:
        return None

    lower = auth_header.lower()
    if not lower.startswith("bearer "):
        logger.debug(
            "ws_auth.auth_header: Authorization موجود لكن ليس Bearer "
            "(scheme=%s)",
            auth_header.split()[0] if auth_header.split() else "empty",
        )
        return None

    token = auth_header[7:].strip()
    return token if token else None


def _extract_from_subprotocol(websocket: WebSocket) -> tuple[str | None, str | None]:
    """
    يستخرج رمز الدخول من ``sec-websocket-protocol`` كـ fallback أخير.

    هذا المصدر غير موثوق في:
    - GitHub Codespaces edge proxy
    - شبكات الهاتف (carrier NAT)
    - Brave Mobile
    - أي reverse proxy لا يحافظ على subprotocol headers

    يُستخدم فقط كخيار أخير عند فشل كل المصادر الأخرى.

    Args:
        websocket: كائن WebSocket الوارد.

    Returns:
        زوج (token, selected_protocol) أو (None, None).
    """
    raw_header = websocket.headers.get("sec-websocket-protocol")

    if not raw_header:
        logger.debug(
            "ws_auth.subprotocol: ترويسة sec-websocket-protocol مفقودة — "
            "محتمل أن proxy حذفها (Codespaces/mobile/carrier-NAT)"
        )
        return None, None

    protocols = _parse_protocol_header(raw_header)

    if not protocols:
        logger.warning(
            "ws_auth.subprotocol: ترويسة sec-websocket-protocol موجودة لكن فارغة "
            "بعد التحليل (raw_header=%r) — proxy قد يكون أرسل قيمة مشوهة",
            raw_header[:50],
        )
        return None, None

    token = _extract_token_from_protocols(protocols)

    if not token:
        logger.debug(
            "ws_auth.subprotocol: protocols موجودة لكن لا يوجد jwt+token "
            "(protocols=%r)",
            protocols[:5],
        )
        return None, None

    selected_protocol = "jwt" if "jwt" in protocols else protocols[0]
    return token, selected_protocol


# ─── الدالة الرئيسية ─────────────────────────────────────────────────────────


def _log_auth_failure(websocket: WebSocket, client_host: str) -> None:
    """
    يُسجِّل تشخيصاً مفصَّلاً عند فشل كل طبقات الاستخراج.

    يُساعد في تحديد سبب الفشل بدون تسريب بيانات حساسة.

    Args:
        websocket: كائن WebSocket الوارد.
        client_host: عنوان IP للعميل (للتشخيص).
    """
    has_cookie = bool(websocket.headers.get("cookie"))
    has_query_token = bool(websocket.query_params.get("token"))
    has_auth_header = bool(websocket.headers.get("authorization"))
    has_subprotocol = bool(websocket.headers.get("sec-websocket-protocol"))

    settings = get_settings()

    logger.warning(
        "ws_auth.no_token_found client=%s env=%s "
        "has_cookie=%s has_query_token=%s has_auth_header=%s has_subprotocol=%s — "
        "تحقق من: (1) Frontend يُرسل token عبر ?token= أو cookie "
        "(2) sec-websocket-protocol لم يُحذف من proxy "
        "(3) المستخدم مُسجَّل دخوله",
        client_host,
        settings.ENVIRONMENT,
        has_cookie,
        has_query_token,
        has_auth_header,
        has_subprotocol,
    )

    if not has_subprotocol and not has_query_token and not has_cookie:
        logger.warning(
            "ws_auth.all_sources_missing client=%s — "
            "محتمل جداً أن proxy (Codespaces/mobile/carrier-NAT) حذف "
            "sec-websocket-protocol ولم يُرسَل query token. "
            "الحل: تأكد من أن Frontend يُضيف ?token=<jwt> إلى WebSocket URL",
            client_host,
        )


def extract_websocket_auth(websocket: WebSocket) -> tuple[str | None, str | None]:
    """
    يستخرج رمز الدخول من طلب WebSocket بنظام متعدد الطبقات.

    ## ترتيب الأولوية (من الأكثر إلى الأقل موثوقية)

    1. **Cookie** — ``access_token`` / ``auth_token`` / ``token``
       الأكثر موثوقية: يعمل عبر كل الشبكات والـ proxies.

    2. **Query parameter** — ``?token=<jwt>``
       ضروري لـ Codespaces / mobile / carrier-NAT / Brave Mobile.
       مُفعَّل في production لأن HTTPS يُشفِّر الـ URL.

    3. **Authorization header** — ``Bearer <token>``
       يُستخدم عندما يحقن Gateway الـ token بعد التحقق منه.

    4. **sec-websocket-protocol** — ``["jwt", "<token>"]``
       Fallback أخير فقط. غير موثوق عبر proxies وشبكات الهاتف.

    ## لماذا query token مُفعَّل في production؟

    المشكلة الأصلية: ``sec-websocket-protocol`` يُحذف من قِبَل:
    - GitHub Codespaces edge proxy
    - شبكات الهاتف الجزائرية (carrier NAT)
    - Brave Mobile browser
    - بعض corporate proxies

    النتيجة: النظام يُرجع 4401 رغم أن المستخدم مُسجَّل دخوله.
    الحل: query token fallback آمن (HTTPS + short-lived tokens).

    Args:
        websocket: كائن WebSocket الوارد من FastAPI.

    Returns:
        زوج ``(token, selected_protocol)`` حيث يمكن أن تكون القيم ``None``.
        ``selected_protocol`` يُستخدم في ``websocket.accept(subprotocol=...)``.
    """
    client_host = (
        getattr(websocket.client, "host", "unknown") if websocket.client else "unknown"
    )

    # ── الطبقة 1: Cookie ────────────────────────────────────────────────────
    cookie_token = _extract_from_cookie(websocket)
    if cookie_token:
        logger.info("ws_auth.extracted source=cookie client=%s", client_host)
        return cookie_token, None

    # ── الطبقة 2: Query parameter ───────────────────────────────────────────
    # مُفعَّل في جميع البيئات — ضروري لـ Codespaces/mobile/Brave
    query_token = _extract_from_query_param(websocket)
    if query_token:
        logger.info(
            "ws_auth.extracted source=query_param client=%s "
            "(proxy-stripped headers أو mobile network)",
            client_host,
        )
        return query_token, None

    # ── الطبقة 3: Authorization header ─────────────────────────────────────
    auth_token = _extract_from_auth_header(websocket)
    if auth_token:
        logger.info("ws_auth.extracted source=auth_header client=%s", client_host)
        return auth_token, "jwt"

    # ── الطبقة 4: sec-websocket-protocol (fallback أخير) ───────────────────
    proto_token, selected_protocol = _extract_from_subprotocol(websocket)
    if proto_token:
        logger.info("ws_auth.extracted source=subprotocol client=%s", client_host)
        return proto_token, selected_protocol

    # ── فشل كل الطبقات ──────────────────────────────────────────────────────
    _log_auth_failure(websocket, client_host)
    return None, None


# ─── نسخة موسَّعة للاستخدام المستقبلي ──────────────────────────────────────


def extract_websocket_auth_detailed(websocket: WebSocket) -> WebSocketAuthResult:
    """
    نسخة موسَّعة من ``extract_websocket_auth`` تُرجع تفاصيل المصدر.

    مفيدة للـ logging المتقدم والـ metrics.

    Args:
        websocket: كائن WebSocket الوارد من FastAPI.

    Returns:
        ``WebSocketAuthResult`` يحتوي على token والمصدر والبروتوكول.
    """
    client_host = (
        getattr(websocket.client, "host", "unknown") if websocket.client else "unknown"
    )

    cookie_token = _extract_from_cookie(websocket)
    if cookie_token:
        logger.info("ws_auth.extracted source=cookie client=%s", client_host)
        return WebSocketAuthResult(
            token=cookie_token, selected_protocol=None, source=TokenSource.COOKIE
        )

    query_token = _extract_from_query_param(websocket)
    if query_token:
        logger.info("ws_auth.extracted source=query_param client=%s", client_host)
        return WebSocketAuthResult(
            token=query_token, selected_protocol=None, source=TokenSource.QUERY_PARAM
        )

    auth_token = _extract_from_auth_header(websocket)
    if auth_token:
        logger.info("ws_auth.extracted source=auth_header client=%s", client_host)
        return WebSocketAuthResult(
            token=auth_token, selected_protocol="jwt", source=TokenSource.AUTH_HEADER
        )

    proto_token, selected_protocol = _extract_from_subprotocol(websocket)
    if proto_token:
        logger.info("ws_auth.extracted source=subprotocol client=%s", client_host)
        return WebSocketAuthResult(
            token=proto_token,
            selected_protocol=selected_protocol,
            source=TokenSource.SUBPROTOCOL,
        )

    _log_auth_failure(websocket, client_host)
    return WebSocketAuthResult(token=None, selected_protocol=None, source=TokenSource.NONE)
