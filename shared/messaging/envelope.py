"""ظرف الحدث القانوني — المصدر الوحيد لما يعبر ناقل الرسائل (D-201).

لماذا ظرفٌ لا `dict`
--------------------
حمولةٌ حرّة على ناقل رسائل تصير غير قابلة للاستهلاك خلال أسابيع: مُنتِجٌ يُرسِل
`{"user": 5}` وآخر `{"user_id": "5"}`، والمستهلك يحرس نفسه بـ`try/except` فيبتلع
الخطأ صامتاً — وهذا **بالضبط** ما يمنعه §0 («لا فشل صامت»). الظرف يجعل الشكل الخاطئ
غير قابل للنشر أصلاً بدل أن يُكتشَف عند المستهلك بعد أسبوع.

ثلاثة حقول تحمل كلّ الانضباط
----------------------------
* `event_id` — **مفتاح المُعالَجة-مرّة-واحدة**. بلا مُعرَّفٍ ثابت من المُنتِج لا وجود
  لـ«مرّة واحدة» إطلاقاً: إعادةُ التسليم (وهي الوضع الطبيعي في Kafka، لا الاستثناء)
  تصير معالجةً ثانية. يُولَّد من المُنتِج مرّةً ويُحفَظ في outbox، فإعادة النشر تحمل
  **نفس** المُعرَّف.
* `correlation_id` — يُمَدّ ولا يُخترَع (D-189). مُعرَّفٌ جديد لكل قفزة يقطع السلسلة
  بدل أن يمدّها؛ ترويسةٌ موجودة بلا قيمة أسوأ من غيابها.
* `schema_version` — المستهلك يعرف ما إذا كان يفهم الرسالة **قبل** أن يقرأها. بلا
  ذلك تصير كلّ هجرة مخطط انقطاعاً.

عقد الموقع
----------
stdlib فقط. لا استيراد من `app/` ولا من أيّ خدمة (قانون الحدود §6.7.و). هذه الطبقة
لا تعرف Kafka ولا Redis — الناقل تفصيلٌ، والظرف عقد.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Final

__all__ = [
    "SCHEMA_VERSION",
    "EventEnvelope",
    "MessagingError",
    "new_event_id",
]


class MessagingError(ValueError):
    """خرقٌ لعقد الرسائل — ظرفٌ ناقص أو حمولة غير قابلة للتسلسل."""


#: نسخة المخطط الحالية. رفعها يتطلّب مستهلكاً يفهم النسختين خلال فترة الهجرة.
SCHEMA_VERSION: Final = 1

#: سقف الحمولة. Kafka الافتراضي عند 1MiB؛ السقف هنا أضيق **عمداً** فيفشل النشر عند
#: المُنتِج برسالة واضحة بدل أن يُرفَض عند الوسيط بخطأ غامض في الإنتاج.
MAX_PAYLOAD_BYTES: Final = 256 * 1024


def new_event_id() -> str:
    """مُعرَّف حدثٍ جديد. يُستدعى **مرّةً واحدة** عند إنشاء الحدث لا عند كل نشر."""
    return str(uuid.uuid4())


@dataclass(frozen=True)
class EventEnvelope:
    """
    ظرفٌ ثابت (immutable) حول حمولة حدث.

    الثبات مقصود: ظرفٌ يُعدَّل بعد إنشائه يمكن أن يُنشَر بمُعرَّفٍ ثمّ يُعاد نشره
    بآخر، فينهار عقد «مرّة واحدة» بلا أن يُخطئ أحد صراحةً.
    """

    event_id: str
    event_name: str
    topic: str
    payload: dict[str, object]
    occurred_at: datetime
    #: مفتاح التقسيم — يضمن ترتيب الأحداث **لنفس الكيان** (طالبٌ واحد مثلاً).
    #: بلا مفتاح تتوزّع أحداث الطالب على أقسام فتصل بترتيبٍ غير ترتيب وقوعها.
    partition_key: str | None = None
    correlation_id: str | None = None
    schema_version: int = SCHEMA_VERSION
    #: عدد مرّات التسليم. يزيده المستهلك عند إعادة المحاولة — أساس قرار DLQ.
    delivery_attempt: int = 1
    headers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_id:
            raise MessagingError("event_id is required — without it 'exactly once' is a fiction")
        if not self.event_name:
            raise MessagingError("event_name is required")
        if not self.topic:
            raise MessagingError("topic is required")
        if self.occurred_at.tzinfo is None:
            # وقتٌ بلا منطقة يُقرأ في كل خدمة بمنطقتها — نفس صنف عطب المواظبة (D-195).
            raise MessagingError("occurred_at must be timezone-aware")
        if self.schema_version < 1:
            raise MessagingError("schema_version must be >= 1")
        if self.delivery_attempt < 1:
            raise MessagingError("delivery_attempt must be >= 1")

    def to_json(self) -> str:
        """يُسلسِل الظرف. يرفع عند حمولةٍ غير قابلة للتسلسل بدل أن يُسقِطها صامتاً."""
        try:
            encoded = json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise MessagingError(f"payload is not JSON-serializable: {exc}") from exc
        size = len(encoded.encode("utf-8"))
        if size > MAX_PAYLOAD_BYTES:
            raise MessagingError(f"envelope of {size} bytes exceeds {MAX_PAYLOAD_BYTES}")
        return encoded

    def as_dict(self) -> dict[str, object]:
        """تمثيلٌ قاموسي — الشكل السلكي نفسه."""
        return {
            "event_id": self.event_id,
            "event_name": self.event_name,
            "topic": self.topic,
            "payload": self.payload,
            "occurred_at": self.occurred_at.astimezone(UTC).isoformat(),
            "partition_key": self.partition_key,
            "correlation_id": self.correlation_id,
            "schema_version": self.schema_version,
            "delivery_attempt": self.delivery_attempt,
            "headers": dict(self.headers),
        }

    def next_attempt(self) -> EventEnvelope:
        """ظرفٌ جديد بمحاولةٍ تالية — **نفس** `event_id` كي تبقى المُعالَجة مرّةً واحدة."""
        return EventEnvelope(
            event_id=self.event_id,
            event_name=self.event_name,
            topic=self.topic,
            payload=self.payload,
            occurred_at=self.occurred_at,
            partition_key=self.partition_key,
            correlation_id=self.correlation_id,
            schema_version=self.schema_version,
            delivery_attempt=self.delivery_attempt + 1,
            headers=dict(self.headers),
        )

    @classmethod
    def from_json(cls, raw: str) -> EventEnvelope:
        """
        يُفكِّك ظرفاً من السلك.

        رسالةٌ مشوَّهة ترفع `MessagingError` — وهذا ما يجعل الرسالة المسمومة تذهب إلى
        DLQ بقرارٍ صريح بدل أن تُعيد المحاولة إلى الأبد وتُجمِّد القسم.
        """
        try:
            data = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise MessagingError(f"malformed envelope: {exc}") from exc
        if not isinstance(data, dict):
            raise MessagingError("envelope must be a JSON object")
        return cls.from_mapping(data)

    @staticmethod
    def _optional_str(data: dict[str, object], key: str) -> str | None:
        """
        حقلٌ نصّي اختياري — **يُتحقَّق** ولا يُحوَّل.

        `str(value)` كان سيقبل `partition_key: 5` ويحوّله إلى `"5"` بصمت، فيبدو
        المفتاح سليماً وهو ليس ما أرسله المُنتِج. الرفض عند الحافة أصدق.
        """
        value = data.get(key)
        if value is None or isinstance(value, str):
            return value
        raise MessagingError(f"{key} must be a string when present, got {type(value).__name__}")

    @staticmethod
    def _required_int(data: dict[str, object], key: str, default: int) -> int:
        """
        عددٌ صحيح — مع رفض `bool` صراحةً.

        `isinstance(True, int)` صحيحة في بايثون، فبلا هذا الحارس تمرّ `true` كـ`1`.
        """
        value = data.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int):
            raise MessagingError(f"{key} must be an integer, got {type(value).__name__}")
        return value

    @classmethod
    def from_mapping(cls, data: dict[str, object]) -> EventEnvelope:
        """يبني ظرفاً من قاموس — مسار مشترك بين السلك والاختبارات."""
        occurred_raw = data.get("occurred_at")
        if not isinstance(occurred_raw, str):
            raise MessagingError("occurred_at is required")
        try:
            occurred_at = datetime.fromisoformat(occurred_raw)
        except ValueError as exc:
            raise MessagingError(f"occurred_at is not ISO-8601: {exc}") from exc

        payload = data.get("payload")
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            raise MessagingError("payload must be an object")

        headers = data.get("headers") or {}
        if not isinstance(headers, dict):
            raise MessagingError("headers must be an object")

        return cls(
            event_id=str(data.get("event_id") or ""),
            event_name=str(data.get("event_name") or ""),
            topic=str(data.get("topic") or ""),
            payload=payload,
            occurred_at=occurred_at,
            partition_key=cls._optional_str(data, "partition_key"),
            correlation_id=cls._optional_str(data, "correlation_id"),
            schema_version=cls._required_int(data, "schema_version", SCHEMA_VERSION),
            delivery_attempt=cls._required_int(data, "delivery_attempt", 1),
            headers={str(key): str(value) for key, value in headers.items()},
        )
