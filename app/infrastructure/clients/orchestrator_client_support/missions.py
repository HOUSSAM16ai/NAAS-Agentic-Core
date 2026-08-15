"""Shard: Orchestration mission requests + internal service JWT (D-256).

**لماذا هذه الشريحة موجودة (CodeScene X-Ray — job 72):** كان `orchestrator_client.py`
يحمل ازدواجًا داخليًا موثقًا في `get_mission`/`get_mission_events` (نمط
`client + try/except + raise_for_status + 404-handling + json` متكرر حرفيًا لكل طلب)
و`_build_service_jwt` (بناء payload متكرر) — والقلب المشترك مبعثر عبر ثلاث دوال.
فُكِّك الازدواج إلى سلوكٍ نقية واحدة `_request_mission` تستدعيها القشرة بثلاثة مسارات
(`POST /missions` · `GET /missions/{id}` · `GET /missions/{id}/events`)، وصار payload
الـ JWT بياناتٍ معلنة عبر `ServiceJwtPayload` — **صفر تغيير سلوكي** (كل التوقيعات
العامة والخاصة السابقة قشور تفويض حرفية — قانون late-binding من D-252).
"""

from __future__ import annotations

import dataclasses
import time
from collections.abc import Awaitable, Callable
from typing import Literal

import httpx
import jwt as pyjwt


@dataclasses.dataclass(frozen=True)
class MissionRequestArgs:
    """وسائط إنشاء مهمة موحّدة (نمط D-249 — البيانات تحكم لا التوقيعات المتناثرة)."""

    objective: str
    context: dict[str, object]
    priority: int
    idempotency_key: str | None


@dataclasses.dataclass(frozen=True)
class ServiceJwtPayload:
    """حمولة JWT داخلية قصيرة العمر للمونوليث → orchestrator-service."""

    user_id: int
    is_admin: bool

    def as_dict(self, now: int | None = None) -> dict[str, object]:
        """يرسم المفاتيح الرسمية للحمولة (توحيد بناء الـ payload — نمط D-249)."""
        now = int(time.time()) if now is None else now
        payload: dict[str, object] = {
            "sub": str(self.user_id),
            "user_id": self.user_id,
            "iat": now,
            "exp": now + 300,  # 5 دقائق
            "iss": "cogniforge-monolith",
        }
        if self.is_admin:
            payload["is_admin"] = True
            payload["role"] = "admin"
        return payload

    def encode(self, secret_key: str, now: int | None = None) -> str:
        """يوقّع الحمولة HS256 (الفارق الوحيد بين هذه الشريحة والقشرة: secret_key)."""
        return pyjwt.encode(self.as_dict(now), secret_key, algorithm="HS256")


def build_service_jwt(
    payload: ServiceJwtPayload,
    secret_key: str,
    now: int | None = None,
) -> str:
    """يولّد JWT المصادقة الداخلي (نقية على الـ payload — القشرة تحقن settings)."""
    return payload.encode(secret_key, now)


# شظايا JSON الخام الداخلة/الخارجة من الـ orchestrator-service (dict/list/scalar)
_JSON_VALUE = dict[str, object] | list[object] | str | int | float | bool | None


async def _request_mission(
    get_client: Callable[[], Awaitable[httpx.AsyncClient]],
    base_url: str,
    method: str,
    path: str,
    *,
    json_body: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
    on_404: Literal["empty"] | None = None,
    empty_value: _JSON_VALUE,
    log_prefix: str,
    log_detail: str = "",
) -> _JSON_VALUE:
    """القلب الموحد لكل طلبات missions (يقتل ازدواج get_mission/get_mission_events/create_mission).

    العقد (مطابق حرفيًا للسلوك السابق — صفر تغيير سلوكي):
      * 404 ⇒ `empty_value` (قائمة فارغة/None حسب المسار).
      * غير 404 مع خطإ HTTP ⇒ `raise_for_status()` يرمي حُرفًا — لا لف ولا تسجيل
        هنا؛ القشرة تلتقط وتسجّل وتعيد الرمي (`logger.error + raise` في create/get).
      * أي استثناء آخر ⇒ يصل القشرة مباشرة (نفس سلوك القشرة القديم).
    """
    import logging

    logger = logging.getLogger("orchestrator-client.missions")
    url = f"{base_url}{path}"
    # D-256: القلب النقي بلا try — يرمي حُرفيًا حتى تبقى رسائل `raise_for_status`
    # الأصلية مطابقة للحرف؛ والالتقاط/التسجيل مسؤولية قشرة التفويض.
    client = await get_client()
    logger.info(f"{log_prefix}: {log_detail or path}")
    response = (
        await client.post(url, json=json_body, headers=headers)
        if method == "POST"
        else await client.get(url)
    )
    if response.status_code == 404:
        return empty_value  # مطابقة حرفية: 404 ⇒ None للمهمة / [] للأحداث
    response.raise_for_status()
    return response.json()
