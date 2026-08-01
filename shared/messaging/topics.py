"""سجلّ المواضيع القانوني — قائمة مغلقة تُرفَض خارجها عند النشر (D-201).

نفس درس D-197 في أسماء الأحداث، مطبَّقاً على المواضيع: موضوعٌ يُنشأ بالكتابة (وهو
سلوك Kafka الافتراضي عند `auto.create.topics.enable`) يعني أنّ خطأً مطبعياً واحداً
يُنشئ موضوعاً جديداً يستقبل رسائل **لا مستهلك لها**، بلا خطأٍ واحد في السجلّات. تبقى
الرسائل هناك حتى تنتهي فترة الاحتفاظ ثمّ تختفي — أسوأ صنف فشلٍ صامت.

القاعدة: الموضوع يُعلَن هنا مع **مستهلكه**. موضوعٌ بلا مستهلك مُعلَن هو ZOMBIE بتعريف
§6.6، فلا يُقبَل إعلانه.

عقد الموقع: stdlib فقط. لا استيراد من `app/` ولا من خدمة.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

__all__ = [
    "TOPIC_SPECS",
    "Topic",
    "TopicSpec",
    "UnknownTopicError",
    "spec_for",
    "validate_topic",
]


class UnknownTopicError(ValueError):
    """موضوعٌ خارج السجلّ القانوني."""


class Topic(StrEnum):
    """كلّ موضوعٍ يكتبه النظام أو يقرؤه."""

    #: أحداث المنتج (D-197) — الاستهلاك يكتب في `product_events`.
    PRODUCT_EVENTS = "cogniforge.product.events.v1"
    #: نتيجة تقييم BKT ⇒ جدولة FSRS (D-194). المفتاح هو الطالب فيبقى الترتيب لكل طالب.
    LEARNING_EVALUATED = "cogniforge.learning.evaluated.v1"
    #: طلبات الإشعار (D-195) — الناقل الحيّ اليوم هو صندوق الصادر في قاعدة البيانات.
    NOTIFICATIONS_REQUESTED = "cogniforge.notifications.requested.v1"
    #: رسائلُ استُنفدت محاولاتها أو تعذّر تفكيكها. **لا يُستهلَك آلياً** — يُفحَص بشرياً.
    DEAD_LETTER = "cogniforge.dead-letter.v1"


@dataclass(frozen=True)
class TopicSpec:
    """عقد موضوعٍ واحد: من يكتبه، من يقرؤه، وكيف يُقسَّم."""

    topic: Topic
    #: مَن يستهلكه. الفراغ ممنوع — موضوعٌ بلا مستهلك ZOMBIE (§6.6).
    consumer_group: str
    partitions: int
    #: احتفاظٌ بالأيام. أطول ممّا يلزم يعني تخزيناً بلا فائدة، وأقصر يعني فقدان
    #: القدرة على إعادة التشغيل بعد عطبٍ في المستهلك.
    retention_days: int
    description: str
    #: هل الرسالة تحمل مفتاحاً إلزامياً؟ الترتيب لكل كيان يتطلّبه.
    requires_key: bool = True


TOPIC_SPECS: Final[dict[Topic, TopicSpec]] = {
    Topic.PRODUCT_EVENTS: TopicSpec(
        topic=Topic.PRODUCT_EVENTS,
        consumer_group="cogniforge-analytics-ingest",
        partitions=3,
        retention_days=30,
        description="أحداث المنتج القانونية — تُكتَب في product_events (D-197).",
    ),
    Topic.LEARNING_EVALUATED: TopicSpec(
        topic=Topic.LEARNING_EVALUATED,
        consumer_group="cogniforge-review-scheduler",
        partitions=3,
        retention_days=14,
        description="نتيجة تقييم BKT ⇒ جدولة مراجعة FSRS (D-194).",
    ),
    Topic.NOTIFICATIONS_REQUESTED: TopicSpec(
        topic=Topic.NOTIFICATIONS_REQUESTED,
        consumer_group="cogniforge-notification-dispatch",
        partitions=1,
        retention_days=7,
        description="طلبات إشعار — الناقل الحيّ هو notification_outbox (D-195).",
    ),
    Topic.DEAD_LETTER: TopicSpec(
        topic=Topic.DEAD_LETTER,
        # مجموعةٌ للفحص البشري لا للاستهلاك الآلي: إعادة تشغيل DLQ آلياً تُعيد نفس
        # الرسالة المسمومة إلى نفس المستهلك الذي عجز عنها.
        consumer_group="cogniforge-dlq-inspector",
        partitions=1,
        retention_days=90,
        description="رسائلُ استُنفدت محاولاتها أو تعذّر تفكيكها — تُفحَص بشرياً.",
        requires_key=False,
    ),
}


def validate_topic(topic: str) -> Topic:
    """يتحقّق أنّ الموضوع مُسجَّل. يرفع `UnknownTopicError` وإلّا."""
    try:
        return Topic(topic)
    except ValueError as exc:
        known = ", ".join(sorted(item.value for item in Topic))
        raise UnknownTopicError(f"unknown topic {topic!r}; registered: {known}") from exc


def spec_for(topic: str | Topic) -> TopicSpec:
    """عقد الموضوع. يرفع إن لم يكن مُسجَّلاً."""
    return TOPIC_SPECS[validate_topic(str(topic))]
