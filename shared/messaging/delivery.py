"""انضباط التسليم: مُعالَجة-مرّة-واحدة وقرار الرسالة المسمومة (D-201).

لماذا هذا الملفّ هو **جوهر** تبنّي Kafka
----------------------------------------
Kafka يضمن «مرّة واحدة على الأقلّ»، لا «مرّة واحدة بالضبط». إعادةُ التسليم هي الوضع
**الطبيعي** لا الاستثناء: إعادة موازنة المستهلكين، انتهاء مهلة، إعادة تشغيل قبل
تثبيت الإزاحة — كلّها تُعيد رسائل عولجت فعلاً. من يتبنّى Kafka بلا هذه الطبقة يتبنّى
عدّاداً يُضاعِف نفسه ودفعاتٍ تُنفَّذ مرّتين.

والوجه الآخر: رسالةٌ **مسمومة** (حمولةٌ لا يفهمها المستهلك أبداً) تُعيد المحاولة إلى
الأبد فتُجمِّد قسمها كاملاً — لا يتقدّم أيّ حدثٍ خلفها. القرار هنا صريح: خطأٌ عابر
يُعاد، وخطأٌ دائم يذهب إلى DLQ **فوراً**، ولا شيء يُعاد بلا سقف.

القرارات كلّها **حتمية** ومختبَرة بلا وسيط. الوسيط تفصيلٌ لاحق.

عقد الموقع: stdlib فقط. لا استيراد من `app/` ولا من خدمة.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from .envelope import EventEnvelope, MessagingError

__all__ = [
    "DEFAULT_MAX_ATTEMPTS",
    "Disposition",
    "IdempotencyLedger",
    "RetryPolicy",
    "decide_disposition",
]

#: سقف المحاولات. بعده تذهب الرسالة إلى DLQ — بلا سقف يعني قسماً مُجمَّداً.
DEFAULT_MAX_ATTEMPTS: Final = 5


class Disposition(StrEnum):
    """ما يحدث للرسالة بعد فشل معالجتها."""

    RETRY = "retry"
    DEAD_LETTER = "dead_letter"


@dataclass(frozen=True)
class RetryPolicy:
    """سياسة إعادة محاولة حتمية بتراجع أُسّي مسقوف."""

    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise MessagingError("max_attempts must be >= 1")
        if self.base_delay_seconds <= 0:
            raise MessagingError("base_delay_seconds must be > 0")
        if self.max_delay_seconds < self.base_delay_seconds:
            raise MessagingError("max_delay_seconds must be >= base_delay_seconds")

    def delay_for(self, attempt: int) -> float:
        """
        تأخير المحاولة رقم `attempt` (١ = الأولى).

        بلا **سقف** يتحوّل التراجع الأُسّي إلى انتظارٍ بالساعات عند المحاولة العاشرة،
        فتبدو الخدمة معلّقة لا متأنّية.
        """
        if attempt < 1:
            raise MessagingError("attempt must be >= 1")
        delay = self.base_delay_seconds * (2 ** (attempt - 1))
        return min(delay, self.max_delay_seconds)


def decide_disposition(
    envelope: EventEnvelope,
    error: Exception,
    *,
    policy: RetryPolicy | None = None,
) -> Disposition:
    """
    يقرّر: إعادة محاولة أم رسالة ميتة؟

    القاعدة الحاسمة: **`MessagingError` خطأٌ دائم** — رسالةٌ لا تُفكَّك لن تُفكَّك بعد
    ثانية ولا بعد ساعة، وإعادتها تجميدٌ للقسم بلا أيّ احتمال نجاح. أمّا غيرُه فيُعامَل
    كعابر (قاعدة بيانات ساقطة، شبكة) حتى ينفد السقف.

    الافتراض في اتجاه إعادة المحاولة مقصود: إسقاطُ رسالةٍ صحيحة بسبب عطبٍ عابر خسارةُ
    بيانات، بينما تأخيرُ رسالةٍ فاسدة إلى أن ينفد سقفها كلفةٌ محدودة.
    """
    active = policy or RetryPolicy()
    if isinstance(error, MessagingError):
        return Disposition.DEAD_LETTER
    if envelope.delivery_attempt >= active.max_attempts:
        return Disposition.DEAD_LETTER
    return Disposition.RETRY


class IdempotencyLedger:
    """
    سجلٌّ مقيَّد بالحجم لما عولج فعلاً — مفتاحه `event_id`.

    **لماذا مقيَّد:** سجلٌّ غير محدود في عملية طويلة العمر تسريبُ ذاكرة مضمون، ويظهر
    بعد أسابيع كخدمةٍ تُقتَل بـOOM بلا سبب ظاهر. الإخلاء بـLRU يعني أنّ إعادة تسليمٍ
    **قديمة جداً** قد تمرّ — وهذا مقبولٌ ومُصرَّح به: النافذة تُضبَط أكبر من أيّ نافذة
    إعادة تسليم واقعية، والضمان القاطع يحتاج سجلّاً في قاعدة البيانات (مقعدٌ موثَّق).

    ليست خيطياً-آمنة عمداً: مستهلك Kafka واحد لكل قسم، فالقفل كلفةٌ بلا مقابل.
    """

    def __init__(self, capacity: int = 10_000) -> None:
        if capacity < 1:
            raise MessagingError("capacity must be >= 1")
        self._capacity = capacity
        self._seen: OrderedDict[str, None] = OrderedDict()

    def __len__(self) -> int:
        return len(self._seen)

    @property
    def capacity(self) -> int:
        return self._capacity

    def seen(self, event_id: str) -> bool:
        """هل عولج هذا الحدث؟ القراءة تُنعِش موقعه فلا يُخلى النشط."""
        if event_id in self._seen:
            self._seen.move_to_end(event_id)
            return True
        return False

    def remember(self, event_id: str) -> None:
        """يُسجِّل حدثاً كمُعالَج."""
        if not event_id:
            raise MessagingError("event_id is required")
        self._seen[event_id] = None
        self._seen.move_to_end(event_id)
        while len(self._seen) > self._capacity:
            self._seen.popitem(last=False)

    def claim(self, envelope: EventEnvelope) -> bool:
        """
        يُطالِب بمعالجة ظرف. يُرجِع `True` إن كانت هذه أوّل مرّة.

        هذه هي نقطة «مرّة واحدة» كاملةً: المستهلك يستدعيها أوّلاً، ويتخطّى بصمتٍ
        **مقصود** ما رآه — التخطّي هنا ليس فشلاً صامتاً بل هو العقد نفسه.
        """
        if self.seen(envelope.event_id):
            return False
        self.remember(envelope.event_id)
        return True
