"""هوية العميل — مصدر واحد لعنوانه الحقيقي (D-236 · ISS-152).

## العطب الذي وُلدت منه هذه الوحدة — **مقيسٌ لا مُفترَض**

`frontend/next.config.js` يُمرِّر `/api/:path*` إلى `http://127.0.0.1:8000`، و`grep`
لـ`X-Forwarded-For` في المستودع كلّه كان **صفراً**. فكان `request.client.host` يساوي
`127.0.0.1` **لكل طلاب المنصّة** في ثلاثين موضعاً — منها درع الدخول وحدّ المعدّل وسجلّ
التدقيق. والنتيجة الحيّة (المرحلة ٠، خادم حقيقي):

```text
19 محاولة فاشلة بعناوين بريد **مختلفة وغير موجودة** ⇒ المحاولة 20 = 429
ثمّ الضحيّة بكلمة سرّها **الصحيحة**              ⇒ 429
```

طالبٌ بريءٌ مُنِع لأن غرباء أخطأوا. وعلى منصّة تخدم ٨٠٠ ألف طالب هذا قفلٌ دائم.

## القواعد الدائمة

1. **قائمة سماح لا قائمة منع.** `X-Forwarded-For` تُصدَّق **فقط** إذا كان النظير
   المباشر وسيطاً موثوقاً مُعلَناً. الترويسة يزوّرها العميل بحرّية، فالثقة بها بلا
   شرطٍ تُحوِّل حدّ المعدّل إلى زينة: كل طلب بعنوان مختلف = حدٌّ لا يُبلَغ أبداً.
   نفس منطق D-187 (الأمان بأن يكون التزوير **غير مُمثَّل**، لا مُرشَّحاً).
2. **اليمين لا اليسار.** السلسلة `client, proxy1, proxy2` يكتبها العميل من اليسار،
   فأوّل قيمة هي **ما زعمه هو**. نمشي من اليمين متجاوزين الوسطاء الموثوقين، وأوّل
   عنوان غير موثوق هو العميل الحقيقي.
3. **الهوية قبل العنوان في قرارات القفل.** حتى بعنوانٍ صحيح، الشبكات الجزائرية خلف
   carrier-NAT تجعل آلافاً يتقاسمون عنواناً واحداً. فالقفل الأساسي على **الهوية**
   (البريد)، والعنوان إشارةٌ ثانوية بسقفٍ أعلى بكثير.
"""

from __future__ import annotations

import ipaddress
import logging
import os
from typing import Final

logger = logging.getLogger(__name__)

__all__ = [
    "UNKNOWN_CLIENT",
    "client_ip_or_unknown",
    "is_trusted_proxy",
    "resolve_client_ip",
    "trusted_proxy_networks",
]

UNKNOWN_CLIENT: Final[str] = "unknown"

_FORWARDED_FOR: Final[str] = "x-forwarded-for"
_REAL_IP: Final[str] = "x-real-ip"

# الوسطاء الموثوقون افتراضاً: الحلقة المحلّية فقط.
# هذا بالضبط ما يصف نشرَنا — Next.js على نفس المضيف يُمرِّر إلى uvicorn عبر
# 127.0.0.1. أي وسيط آخر (موازن تحميل سحابي) يُعلَن صراحةً عبر TRUSTED_PROXY_IPS.
# ⛔ الافتراض لا يشمل الشبكات الخاصّة (10/8 · 172.16/12 · 192.168/16): وسيطٌ غير
# مقصود داخلها يصير قادراً على انتحال أي عنوان.
_DEFAULT_TRUSTED: Final[tuple[str, ...]] = ("127.0.0.0/8", "::1/128")

_ENV_VAR: Final[str] = "TRUSTED_PROXY_IPS"


def _parse_networks(raw: str) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    """يحوّل قائمة CIDR مفصولة بفواصل إلى شبكات، ويتجاهل المُشوَّه مع تحذير."""
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for chunk in raw.split(","):
        candidate = chunk.strip()
        if not candidate:
            continue
        try:
            networks.append(ipaddress.ip_network(candidate, strict=False))
        except ValueError:
            logger.warning(
                "client_identity: تجاهُل مُدخَل غير صالح في %s: %r", _ENV_VAR, candidate[:64]
            )
    return tuple(networks)


def trusted_proxy_networks() -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    """يعيد شبكات الوسطاء الموثوقين.

    تُقرأ من البيئة عند كل نداء عمداً: الاختبارات تحتاج تغييرها، والكلفة نداء
    ``os.environ`` واحد — أرخص بكثير من ذاكرة مؤقّتة تُخفي إعداداً خاطئاً.
    """
    raw = (os.environ.get(_ENV_VAR) or "").strip()
    if not raw:
        return _parse_networks(",".join(_DEFAULT_TRUSTED))
    return _parse_networks(raw)


def is_trusted_proxy(candidate: str | None) -> bool:
    """هل العنوان المُعطى وسيطٌ موثوق مُعلَن؟"""
    if not candidate:
        return False
    try:
        address = ipaddress.ip_address(candidate.strip())
    except ValueError:
        return False
    return any(address in network for network in trusted_proxy_networks())


def _split_forwarded_chain(raw_header: str) -> list[str]:
    """يفكّ سلسلة ``X-Forwarded-For`` إلى عناوين نظيفة."""
    chain: list[str] = []
    for part in raw_header.split(","):
        candidate = part.strip()
        if not candidate:
            continue
        # IPv6 داخل أقواس مربّعة، وقد يلحقه منفذ: [::1]:443
        if candidate.startswith("["):
            candidate = candidate[1:].split("]", 1)[0]
        elif candidate.count(":") == 1 and "." in candidate:
            # IPv4:port — المنفذ ليس جزءاً من الهوية
            candidate = candidate.split(":", 1)[0]
        chain.append(candidate)
    return chain


def _valid_ip(candidate: str) -> str | None:
    """يعيد العنوان إن كان صالحاً، وإلّا ``None``."""
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def resolve_client_ip(request: object) -> str | None:
    """يعيد عنوان العميل الحقيقي، أو ``None`` إن تعذّر.

    Args:
        request: كائن ``Request`` أو ``WebSocket`` (أي كائن يملك ``client``
            و``headers``) — النوع مُتساهل عمداً كي تخدم الوحدة المسارين دون أن
            تستورد Starlette، فتبقى قابلة للاختبار بلا تطبيق.

    Returns:
        عنوان العميل، أو ``None`` حين لا يوجد نظير معروف.
    """
    client = getattr(request, "client", None)
    peer = getattr(client, "host", None) if client is not None else None

    headers = getattr(request, "headers", None)
    if headers is None:
        return peer

    # ⛔ الترويسة لا تُصدَّق إلّا من وسيطٍ موثوق. النظير المجهول يعني أننا لا نعرف
    # من سلّمنا الطلب — والغياب ليس تفويضاً.
    if not is_trusted_proxy(peer):
        return peer

    forwarded = (headers.get(_FORWARDED_FOR) or "").strip()
    if forwarded:
        chain = _split_forwarded_chain(forwarded)
        # من اليمين إلى اليسار: نتجاوز الوسطاء الموثوقين، وأوّل غير موثوق هو العميل.
        for candidate in reversed(chain):
            normalized = _valid_ip(candidate)
            if normalized is None:
                continue
            if not is_trusted_proxy(normalized):
                return normalized
        # كل السلسلة وسطاء موثوقون ⇒ أقصى اليسار أفضل تقدير متاح.
        for candidate in chain:
            normalized = _valid_ip(candidate)
            if normalized is not None:
                return normalized

    real_ip = (headers.get(_REAL_IP) or "").strip()
    if real_ip:
        normalized = _valid_ip(real_ip)
        if normalized is not None:
            return normalized

    return peer


def client_ip_or_unknown(request: object) -> str:
    """مثل :func:`resolve_client_ip` لكن يعيد ``"unknown"`` بدل ``None``.

    يخدم مواضع الاستدعاء التي تبني مفتاحاً نصّياً (حدّ المعدّل · الدرع · التدقيق)،
    فلا يتكرّر نمط ``... if request.client else "unknown"`` في ثلاثين موضعاً.
    """
    return resolve_client_ip(request) or UNKNOWN_CLIENT
