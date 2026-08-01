"""اشتقاق طلبات الإشعار من أحداث المنتج — حتمي ومغلق (D-201).

لماذا قواعد مغلقة لا شروطاً مبعثرة
----------------------------------
الإشعارات هي أسرع طريق لخسارة ثقة مستخدم: قاعدةٌ واحدة زائدة تعني رسالتين في اليوم
لثمانمئة ألف طالب. لذلك القواعد **قائمة مغلقة** في مكانٍ واحد يُقرأ في ثوانٍ، لا
شروطاً منثورة في مسار الأحداث تكتشفها بعد الشكوى.

القاعدة الدائمة: **حدثٌ واحد ⇒ إشعارٌ واحد على الأكثر.** ما ليس في القائمة لا يُشعِر،
والافتراض هو الصمت. الصمت الافتراضي قابل للإصلاح؛ الإزعاج الافتراضي يُفقِد المستخدم.

عقد الموقع: stdlib فقط. لا استيراد من `app/` ولا من خدمة.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

__all__ = [
    "NOTIFICATION_RULES",
    "NotificationRequest",
    "derive_notification",
]


@dataclass(frozen=True)
class NotificationRequest:
    """طلب إشعارٍ مُشتقّ — بلا نصٍّ نهائي، القالب يُترجَم عند التسليم."""

    template: str
    channel: str
    user_id: int | None
    payload: dict[str, object]


#: اسم الحدث ⇒ (القالب، القناة). الإضافة هنا قرارٌ يُراجَع، لا تفصيلٌ عابر.
NOTIFICATION_RULES: Final[dict[str, tuple[str, str]]] = {
    # الوليّ ارتبط فعلاً ⇒ يُعلَم الطالب أنّ حسابه صار مرئياً. هذا **حقّ الطالب** في
    # أن يعرف من يرى تقدّمه، لا رسالةً تسويقية (D-196: الربط برضاه بنيوياً).
    "guardian_link_accepted": ("guardian_linked", "in_app"),
}


def derive_notification(
    event_name: str, payload: dict[str, object] | None = None
) -> NotificationRequest | None:
    """
    يُشتقّ طلب إشعارٍ من حدثٍ، أو `None` إن لم تكن هناك قاعدة.

    `None` هو الافتراض السليم: حدثٌ بلا قاعدة يمرّ صامتاً بدل أن يُشعِر «احتياطاً».
    """
    rule = NOTIFICATION_RULES.get(event_name)
    if rule is None:
        return None
    template, channel = rule
    data = payload or {}
    raw_user = data.get("user_id")
    return NotificationRequest(
        template=template,
        channel=channel,
        user_id=int(raw_user)
        if isinstance(raw_user, int | str) and str(raw_user).isdigit()
        else None,
        payload=data,
    )
