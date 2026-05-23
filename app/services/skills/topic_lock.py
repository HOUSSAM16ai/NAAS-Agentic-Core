"""
TopicLock — V46.0: قفل الموضوع وحماية نقاء السياق.

## المبدأ المعماري (Protocol V46.0 §4)

يجب أن يبقى النظام مُقيَّداً بالنطاق التعليمي النشط.

إذا كان التمرين الحالي في الاحتمالات:
- لا يُذكر التفاضل
- لا يُذكر المشتقات
- لا تتسرب تشبيهات من مجالات أخرى
- لا يتسرب سياق قديم

الشرح يبقى داخل النطاق النشط حتى ينتقل الطالب صراحةً إلى موضوع آخر.

## آلية العمل

1. **الكشف**: يُحدِّد الموضوع النشط من سياق المحادثة.
2. **الفحص**: يتحقق من أن الإجابة لا تتجاوز النطاق.
3. **التحذير**: يُسجِّل الانتهاكات دون كسر المسار.
4. **القياس**: Prometheus counters لكل انتهاك.

D-086 (2026-05-23): إنشاء TopicLock كـ Skill رسمي — V46.0.
"""

from __future__ import annotations

import logging
import re
from typing import ClassVar

from pydantic import Field

from app.core.schemas import RobustBaseModel

logger = logging.getLogger(__name__)

# ── Prometheus metrics — استيراد دفاعي ────────────────────────────────────────
try:
    from prometheus_client import Counter

    _TOPIC_VIOLATIONS = Counter(
        "cogniforge_topic_lock_violations_total",
        "عدد انتهاكات قفل الموضوع",
        ["active_topic", "leaked_topic"],
    )
    _TOPIC_CHECKS = Counter(
        "cogniforge_topic_lock_checks_total",
        "عدد فحوصات قفل الموضوع",
        ["result"],
    )
    _METRICS_AVAILABLE = True
except ImportError:
    _METRICS_AVAILABLE = False


def _record_violation(active: str, leaked: str) -> None:
    if _METRICS_AVAILABLE:
        _TOPIC_VIOLATIONS.labels(active_topic=active, leaked_topic=leaked).inc()


def _record_check(result: str) -> None:
    if _METRICS_AVAILABLE:
        _TOPIC_CHECKS.labels(result=result).inc()


# ── خريطة المواضيع والكلمات المفتاحية ────────────────────────────────────────

# كل موضوع له: كلمات تُعرِّفه + كلمات مواضيع أخرى يجب ألا تظهر في إجابته
_TOPIC_DEFINITIONS: dict[str, dict[str, list[str]]] = {
    "probability": {
        "keywords": [
            "احتمال",
            "احتمالات",
            "حدث",
            "فضاء العينة",
            "تجربة عشوائية",
            "سحب",
            "كرة",
            "بطاقة",
            "قرعة",
            "توزيع",
            "متغير عشوائي",
            "probability",
            "random",
            "event",
            "sample space",
        ],
        "forbidden_from_other_topics": [
            # من التفاضل والتكامل
            "مشتقة",
            "تكامل",
            "نهاية",
            "دالة قابلة للاشتقاق",
            "قاعدة السلسلة",
            "قاعدة الضرب",
            "تفاضل",
            "derivative",
            "integral",
            "limit",
            "differentiation",
        ],
    },
    "calculus": {
        "keywords": [
            "مشتقة",
            "تكامل",
            "نهاية",
            "دالة",
            "اشتقاق",
            "تفاضل",
            "تكامل محدود",
            "تكامل غير محدود",
            "قاعدة السلسلة",
            "derivative",
            "integral",
            "limit",
            "differentiation",
            "calculus",
        ],
        "forbidden_from_other_topics": [
            # من الاحتمالات
            "فضاء العينة",
            "تجربة عشوائية",
            "سحب بدون إرجاع",
            "sample space",
            "random experiment",
        ],
    },
    "algebra": {
        "keywords": [
            "معادلة",
            "مجهول",
            "حل المعادلة",
            "نظام معادلات",
            "مصفوفة",
            "محدد",
            "قيمة ذاتية",
            "متجه",
            "equation",
            "matrix",
            "determinant",
            "eigenvalue",
        ],
        "forbidden_from_other_topics": [],
    },
    "geometry": {
        "keywords": [
            "مثلث",
            "دائرة",
            "مستطيل",
            "مربع",
            "متوازي أضلاع",
            "زاوية",
            "محيط",
            "مساحة",
            "حجم",
            "إحداثيات",
            "triangle",
            "circle",
            "rectangle",
            "angle",
            "area",
            "volume",
        ],
        "forbidden_from_other_topics": [],
    },
    "physics": {
        "keywords": [
            "قوة",
            "طاقة",
            "سرعة",
            "تسارع",
            "كتلة",
            "شغل",
            "كهرباء",
            "مقاومة",
            "تيار",
            "جهد",
            "موجة",
            "تردد",
            "force",
            "energy",
            "velocity",
            "acceleration",
            "mass",
        ],
        "forbidden_from_other_topics": [],
    },
    "chemistry": {
        "keywords": [
            "تفاعل كيميائي",
            "معادلة كيميائية",
            "مول",
            "تركيز",
            "حمض",
            "قاعدة",
            "أكسدة",
            "اختزال",
            "عنصر",
            "مركب",
            "reaction",
            "molecule",
            "acid",
            "base",
            "oxidation",
        ],
        "forbidden_from_other_topics": [],
    },
}

# أنماط الانتقال الصريح للموضوع (تُلغي القفل)
_TOPIC_TRANSITION_PATTERNS = [
    re.compile(r"انتقل إلى|دعنا ننتقل|الآن سنتحدث عن|موضوع جديد|سؤال آخر", re.IGNORECASE),
    re.compile(r"let's move to|now let's talk about|new topic|different subject", re.IGNORECASE),
    re.compile(r"اشرح لي|علمني|ما هو|ما هي", re.IGNORECASE),
]


def _detect_active_topic(history: list[dict[str, str]]) -> str | None:
    """
    يُحدِّد الموضوع النشط من آخر 5 رسائل في تاريخ المحادثة.

    يُعيد None إذا لم يُحدَّد موضوع واضح.
    """
    if not history:
        return None

    # فحص آخر 5 رسائل فقط (نافذة السياق القريب)
    recent = history[-5:]
    combined_text = " ".join(
        msg.get("content", "") for msg in recent if msg.get("role") == "user"
    ).lower()

    if not combined_text:
        return None

    # حساب نقاط كل موضوع
    topic_scores: dict[str, int] = {}
    for topic, definition in _TOPIC_DEFINITIONS.items():
        score = sum(1 for kw in definition["keywords"] if kw.lower() in combined_text)
        if score > 0:
            topic_scores[topic] = score

    if not topic_scores:
        return None

    # الموضوع الأعلى نقاطاً
    return max(topic_scores, key=lambda t: topic_scores[t])


def _check_topic_purity(
    response: str,
    active_topic: str,
) -> list[str]:
    """
    يتحقق من أن الإجابة لا تتجاوز نطاق الموضوع النشط.

    يُعيد قائمة بالمواضيع المتسربة (فارغة = نظيف).
    """
    if active_topic not in _TOPIC_DEFINITIONS:
        return []

    forbidden = _TOPIC_DEFINITIONS[active_topic].get("forbidden_from_other_topics", [])
    if not forbidden:
        return []

    response_lower = response.lower()
    leaked_topics: list[str] = []

    for forbidden_term in forbidden:
        if forbidden_term.lower() in response_lower:
            # تحديد الموضوع المتسرب
            for other_topic, definition in _TOPIC_DEFINITIONS.items():
                if other_topic == active_topic:
                    continue
                if (
                    forbidden_term.lower() in [kw.lower() for kw in definition["keywords"]]
                    and other_topic not in leaked_topics
                ):
                    leaked_topics.append(other_topic)

    return leaked_topics


# ── Pydantic Contracts ────────────────────────────────────────────────────────


class TopicLockInput(RobustBaseModel):
    """مدخلات فحص قفل الموضوع."""

    response: str = Field(..., description="إجابة النظام المراد فحصها")
    question: str = Field("", description="سؤال الطالب الحالي")
    history: list[dict[str, str]] = Field(
        default_factory=list,
        description="تاريخ المحادثة",
    )
    active_topic_override: str | None = Field(
        None,
        description="تجاوز الكشف التلقائي للموضوع",
    )


class TopicLockOutput(RobustBaseModel):
    """نتيجة فحص قفل الموضوع."""

    passed: bool = Field(..., description="هل الإجابة ضمن النطاق")
    active_topic: str | None = Field(None, description="الموضوع النشط المُكتشَف")
    leaked_topics: list[str] = Field(
        default_factory=list,
        description="المواضيع المتسربة",
    )
    is_topic_transition: bool = Field(
        False,
        description="هل الطالب ينتقل صراحةً لموضوع جديد",
    )


# ── TopicLock Skill ───────────────────────────────────────────────────────────


class TopicLock:
    """
    Skill قفل الموضوع وحماية نقاء السياق — V46.0.

    يضمن أن الإجابة تبقى داخل النطاق التعليمي النشط
    ولا تتسرب مفاهيم من مواضيع أخرى.

    هذا الـ Skill تحذيري فقط — لا يرفض الإجابات، يُسجِّل الانتهاكات
    ويُعيد تقريراً للمُستدعي ليتخذ القرار.
    """

    VERSION: ClassVar[str] = "1.0.0"
    SKILL_NAME: ClassVar[str] = "topic_lock"

    def check(self, inp: TopicLockInput) -> TopicLockOutput:
        """
        يفحص نقاء الموضوع في الإجابة.

        لا يكسر المسار أبداً — أي فشل يُعيد passed=True (fail open).
        """
        try:
            return self._check_impl(inp)
        except Exception as exc:
            logger.debug("topic_lock.check_failed (non-fatal): %s", exc)
            return TopicLockOutput(passed=True, active_topic=None)

    def _check_impl(self, inp: TopicLockInput) -> TopicLockOutput:
        # 1. تحقق من انتقال صريح للموضوع
        combined_input = f"{inp.question} {inp.response}"
        is_transition = any(p.search(combined_input) for p in _TOPIC_TRANSITION_PATTERNS)
        if is_transition:
            _record_check("transition")
            return TopicLockOutput(
                passed=True,
                active_topic=None,
                is_topic_transition=True,
            )

        # 2. تحديد الموضوع النشط
        active_topic = inp.active_topic_override or _detect_active_topic(inp.history)
        if not active_topic:
            _record_check("no_topic")
            return TopicLockOutput(passed=True, active_topic=None)

        # 3. فحص نقاء الإجابة
        leaked = _check_topic_purity(inp.response, active_topic)

        if leaked:
            for leaked_topic in leaked:
                _record_violation(active_topic, leaked_topic)
            _record_check("violation")
            logger.warning(
                "topic_lock.violation active=%s leaked=%s response_preview=%.80s",
                active_topic,
                leaked,
                inp.response,
            )
            return TopicLockOutput(
                passed=False,
                active_topic=active_topic,
                leaked_topics=leaked,
            )

        _record_check("clean")
        return TopicLockOutput(passed=True, active_topic=active_topic)


# ── Singleton ─────────────────────────────────────────────────────────────────
_topic_lock: TopicLock | None = None


def get_topic_lock() -> TopicLock:
    """يُعيد singleton من TopicLock."""
    global _topic_lock
    if _topic_lock is None:
        _topic_lock = TopicLock()
    return _topic_lock


__all__ = [
    "TopicLock",
    "TopicLockInput",
    "TopicLockOutput",
    "get_topic_lock",
]
