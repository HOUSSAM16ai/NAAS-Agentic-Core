"""
SocraticEvaluatorSkill — الطبقة 1 (الإصغاء النشط) من المعمارية الإدراكية العصبية-الرمزية
(D-130).

CLAUDE.md §0.5: «كل قدرة ذكاء اصطناعي يجب أن تكون Skill».

## المسؤولية الواحدة
تقييم **رد الطالب الحرّ** على سؤال سقراطي معلّق: هل فهم النقطة المستترة؟ تُرجِع
`(understood, encouragement, next_focus)` — لا تحسب الرياضيات (الأرقام من المحرك الرمزي،
الطبقة 3)، لا تطرح السؤال (الطبقة 4)، لا تشخّص المفهوم (الطبقة 1 الأخرى، D-127).

## الكارثة التي تحلّها (الخيانة البيداغوجية — transcript حي)
النظام سأل سؤالاً سقراطياً ممتازاً، فأجاب الطالب إجابة عبقرية («نفس اللون فقط، الحمراء
والخضراء — البيضاء مستحيلة»)، فأعاد النظام **طباعة التمرين كاملاً** بدل أن يكافئه ويُكمل.
السبب: النصف الثاني من الحوار السقراطي — **الإصغاء النشط** — كان غائباً. هذا الـ Skill هو
«الأذن الصاغية» المفقودة.

## المعمارية العصبية-الرمزية (D-130)
- **الطبقة 1 (LLM للفهم فقط)**: يقارن رد الطالب الحرّ بالهدف التربوي المستتر. لا أرقام.
- **الطبقة 3 (المحرك الرمزي)**: عند `understood=True` يكتب orchestrator الخطوة الناتجة
  (C(4,3)+C(5,3)=14) — حتمياً، لا الـ LLM.

## الحراسة (مطابقة D-128)
`_strip_garbage_markers` + `redact_final_answers(support_level=5)` + `is_probably_non_arabic`
+ `asyncio.wait_for`. أي فشل/شكّ ⇒ fallback حتمي (لا يعاقب الطالب، لا يكشف الجواب).

## الاستقلالية (§0.5)
- يستخدم `app.core.ai_gateway.get_ai_client` (core) + حُرّاس من Skills نزاهة/تطهير (طبقات
  دفاع قائمة، لا منطق Skill آخر). التقييم الحتمي fallback قابل للاختبار بـ pytest.

## القياس (Prometheus)
- `cogniforge_skill_socratic_evaluator_total{understood,source}` (counter)
- `cogniforge_skill_socratic_evaluator_duration_seconds` (histogram)
"""

from __future__ import annotations

import contextlib
import time

from pydantic import Field

from app.core.schemas import RobustBaseModel
from app.services.skills.doctrine import SOCRATIC_EVALUATOR_DOCTRINE_VERSION

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
#: D-142 (1A): توحيد الهمزات/الألف المقصورة/التاء المربوطة لمطابقة الإشارات بمتانة
#: («الأحمر»/«الأخضر» يجب أن تطابق «احمر»/«اخضر»).
_AR_UNIFY = str.maketrans("أإآٱىة", "اااايه")


def _normalize(text: str) -> str:
    return (text or "").translate(_AR_DIGITS).strip().lower()


def _sig_norm(text: str) -> str:
    """تطبيع متين لمطابقة إشارات الفهم: أرقام + همزات + ألف مقصورة + تاء مربوطة."""
    return _normalize(text).translate(_AR_UNIFY)


# ── الهدف التربوي المستتر لكل مفهوم (الطبقة 1 تقارن رد الطالب به) ──────────────────
HIDDEN_GOALS: dict[str, str] = {
    "numerator": "أن يدرك الطالب أن البيضاء مستحيلة (عددها 2 < 3) فيقتصر الحساب على الحمراء والخضراء.",
    "event_meaning": "أن يدرك أن الحادثة A = 3 كرات من نفس اللون، وأن البيضاء مستحيلة فيبقى الحمراء والخضراء.",
    "denominator": "أن يدرك أن المقام هو كل الطرق الممكنة لسحب 3 من 11 بصرف النظر عن اللون.",
    "ratio": "أن يدرك أن الاحتمال نسبة: الحالات الملائمة (البسط) إلى كل الطرق (المقام).",
    "combinations": "أن يدرك أن الاختيار دون ترتيب (توافيق) لا ترتيب — C(n,k).",
    "color_red": "أن يدرك أن عدد طرق اختيار 3 حمراء من 4 هو C(4,3).",
    "color_green": "أن يدرك أن عدد طرق اختيار 3 خضراء من 5 هو C(5,3).",
    "color_white": "أن يدرك أن سحب 3 بيضاء مستحيل لأن عددها 2 فقط.",
    "full_solution": "أن يدرك تسلسل الحل: الحالات الملائمة ثم كل الطرق ثم النسبة.",
}

#: المفهوم التالي في السُّلّم بعد إتقان المفهوم الحالي (للتسليم الرمزي المتدرّج).
NEXT_FOCUS: dict[str, str | None] = {
    "numerator": "denominator",
    "event_meaning": "denominator",
    "color_red": "color_green",
    "color_green": "denominator",
    "color_white": "numerator",
    "combinations": "numerator",
    "denominator": "ratio",
    "ratio": None,
    "full_solution": None,
}


def hidden_goal_for(concept: str) -> str:
    """الهدف التربوي المستتر للمفهوم (fallback لـ event_meaning)."""
    return HIDDEN_GOALS.get(concept, HIDDEN_GOALS["event_meaning"])


def next_focus_for(concept: str) -> str | None:
    """المفهوم التالي في السُّلّم (للسؤال المتابع بعد الفهم)."""
    return NEXT_FOCUS.get(concept, "denominator")


#: علامات فهم «الحالات الملائمة» حتمياً (للـ fallback عند تعذّر الـ LLM).
_UNDERSTANDING_SIGNALS: tuple[str, ...] = ("نفس اللون", "نفس لون", "ذات اللون", "اللون نفسه")
_COLOR_SIGNALS: tuple[str, ...] = ("حمراء", "خضراء", "احمر", "اخضر", "الاحمر", "الاخضر")
_IMPOSSIBLE_SIGNALS: tuple[str, ...] = ("مستحيل", "لا يمكن", "فقط", "2 فقط", "غير كاف", "لونين")

#: المفاهيم المغلقة التي يملك المحرك الرمزي حقيقتها (يمكن التحقق من صحة الإجابة حتمياً).
_SYMBOLIC_VERIFIABLE_CONCEPTS: frozenset[str] = frozenset(
    {"numerator", "event_meaning", "color_white"}
)


def deterministically_correct(student_answer: str, concept: str) -> bool:
    """D-142 (1A): هل إجابة الطالب صحيحة **حتمياً** (مُتحقَّقة رمزياً)؟

    تُرجِع True فقط حين تحمل الإجابة دلالة فهم **قابلة للتحقق** (سمّى الحمراء/الخضراء أو
    أقرّ باستحالة البيضاء «فقط»/«مستحيل»/«لونين»). هذا هو **السلطة الرمزية**: حين تكون True
    يُمنع على الـ LLM الفلاكي أن يخفض `understood` إلى False (يكسر كارثة التكرار). للمفاهيم
    غير القابلة للتحقق تُرجِع False ⇒ يُترك القرار للـ LLM (لا تأكيد كاذب).
    """
    if concept not in _SYMBOLIC_VERIFIABLE_CONCEPTS:
        return False
    t = _sig_norm(student_answer)
    if not t:
        return False
    has_same_color = any(_sig_norm(s) in t for s in _UNDERSTANDING_SIGNALS)
    has_color = any(_sig_norm(s) in t for s in _COLOR_SIGNALS)
    has_impossible = any(_sig_norm(s) in t for s in _IMPOSSIBLE_SIGNALS)
    return has_same_color or has_color or has_impossible


def _heuristic_understood(student_answer: str, concept: str) -> bool:
    """D-130: تقييم حتمي احتياطي (fail-open) — هل يحمل الرد دلالة الفهم؟

    لا يعاقب الطالب: عند الشكّ يُرجِع True (الطالب شغّل عقله) — التسليم الرمزي المتدرّج
    سيُكمل بأمان دون كشف الجواب كاملاً.
    """
    t = _normalize(student_answer)
    if not t:
        return False
    if concept in _SYMBOLIC_VERIFIABLE_CONCEPTS:
        return deterministically_correct(student_answer, concept)
    # لمفاهيم أخرى: أي رد غير فارغ يُعدّ محاولة فهم (لا نعاقب) — التسليم المتدرّج يُكمل.
    return True


# ── العقود (Pydantic) ────────────────────────────────────────────────────────
class SocraticEvaluatorInput(RobustBaseModel):
    """مدخلات المُقيّم — typed contract."""

    student_answer: str = Field(..., min_length=1, max_length=8000)
    concept: str = Field(..., min_length=1, max_length=64)
    facts: str = Field(default="", max_length=2000)
    history: list[dict[str, str]] | None = None
    #: D-142 (1A): إشارة السلطة الرمزية — يحسبها المُنسّق من المحرك الرمزي (combo). حين True
    #: يُمنع على الـ LLM إخفاض `understood` إلى False (إجابة مُتحقَّقة صحيحة ⇒ تقدّم حتمي).
    verified_correct: bool = False


class SocraticEvaluatorOutput(RobustBaseModel):
    """قرار المُقيّم: هل فهم + تشجيع لطيف + المفهوم التالي في السُّلّم."""

    understood: bool
    encouragement: str = ""
    next_focus: str | None = None
    source: str = "fallback"  # llm | fallback


# ── Prometheus metrics ─────────────────────────────────────────────────────────────
try:
    from prometheus_client import REGISTRY, Counter, Histogram

    if "cogniforge_skill_socratic_evaluator_total" in {m.name for m in REGISTRY.collect()}:
        _eval_total = None
        _eval_duration = None
    else:
        _eval_total = Counter(
            "cogniforge_skill_socratic_evaluator_total",
            "Socratic-evaluator decisions, labelled by understood/source.",
            ["understood", "source"],
        )
        _eval_duration = Histogram(
            "cogniforge_skill_socratic_evaluator_duration_seconds",
            "Socratic-evaluator latency.",
        )

    def _record(understood: bool, source: str, duration_s: float) -> None:
        with contextlib.suppress(Exception):
            if _eval_total is not None:
                _eval_total.labels(understood=str(understood).lower(), source=source).inc()
            if _eval_duration is not None:
                _eval_duration.observe(duration_s)

except Exception:  # pragma: no cover

    def _record(understood: bool, source: str, duration_s: float) -> None:
        pass


_DEFAULT_ENCOURAGEMENT = "أحسنت — استنتاجك في محله. لنُكمل معاً خطوةً بخطوة."


class SocraticEvaluatorSkill:
    """
    Skill الإصغاء النشط (الطبقة 1 — D-130).

    عقد دائم (لا يُكسر بدون ADR):
    1. الـ LLM يُقيّم *الفهم* فقط؛ الأرقام من المحرك الرمزي (الطبقة 3).
    2. التشجيع لا يكشف نتيجة نهائية أبداً (محروس بـ redact_final_answers).
    3. fail-open مطلق: أي تعذّر ⇒ تقييم حتمي لطيف، لا عقاب، لا إعادة طباعة.
    """

    _skill_name: str = "socratic_evaluator"
    doctrine_version: str = SOCRATIC_EVALUATOR_DOCTRINE_VERSION
    _LLM_TIMEOUT_S: float = 12.0

    async def evaluate(self, payload: SocraticEvaluatorInput) -> SocraticEvaluatorOutput:
        """يُقيّم رد الطالب الحرّ — LLM محروس مع fallback حتمي. لا يرفع استثناءات."""
        t0 = time.perf_counter()
        nxt = next_focus_for(payload.concept)
        # D-142 (1A): السلطة الرمزية — إجابة مُتحقَّقة صحيحة (من combo عبر `verified_correct`
        # أو من الإشارات الحتمية). حين True يُمنع على الـ LLM إخفاضها (يكسر كارثة التكرار).
        det_correct = payload.verified_correct or deterministically_correct(
            payload.student_answer, payload.concept
        )
        llm_result = await self._evaluate_with_llm(payload)
        if llm_result is not None:
            understood, encouragement = llm_result
            if det_correct:
                understood = True  # الـ LLM قد يرفع فقط، لا يخفض إجابةً مُتحقَّقة صحيحة
            out = SocraticEvaluatorOutput(
                understood=understood,
                encouragement=encouragement or _DEFAULT_ENCOURAGEMENT,
                next_focus=nxt,
                source="llm",
            )
            _record(out.understood, out.source, time.perf_counter() - t0)
            return out
        # fallback حتمي (fail-open)
        understood = det_correct or _heuristic_understood(payload.student_answer, payload.concept)
        out = SocraticEvaluatorOutput(
            understood=understood,
            encouragement=_DEFAULT_ENCOURAGEMENT if understood else "فكرة جيدة — لنقترب أكثر.",
            next_focus=nxt,
            source="fallback",
        )
        _record(out.understood, out.source, time.perf_counter() - t0)
        return out

    @classmethod
    async def _evaluate_with_llm(cls, payload: SocraticEvaluatorInput) -> tuple[bool, str] | None:
        """الطبقة 1: مُقيّم LLM محروس — يُرجِع (understood, encouragement) أو None.

        مخرج JSON مُقيَّد + timeout + حُرّاس النزاهة + fallback. التشجيع لا يكشف نتيجة.
        """
        import asyncio

        try:
            from app.core.ai_gateway import get_ai_client

            goal = hidden_goal_for(payload.concept)
            system_prompt = (
                "أنت مُقيّم إدراكي تربوي (لا تحلّ، لا تحسب، لا تكشف الجواب). قارن إجابة الطالب "
                "الحرّة بالهدف التربوي المستتر، وأخرِج JSON فقط بهذا الشكل بلا أي نص آخر:\n"
                '{"understood": true/false, "encouragement": "..."}\n'
                "التشجيع عربي فصيح جملة أو جملتان، يعترف بما أصاب فيه الطالب، **ولا يذكر أي "
                "نتيجة نهائية أو كسر (مثل 14/165 أو 56/165) ولا يحسب**."
            )
            user = (
                f"الهدف التربوي المستتر: {goal}\n"
                f"الحقائق (معطيات فقط): {payload.facts}\n"
                f"إجابة الطالب: {payload.student_answer.strip()[:1500]}\n"
                "هل فهم الطالب الهدف؟ أخرِج JSON فقط."
            )
            raw = await asyncio.wait_for(
                get_ai_client().send_message(system_prompt, user, temperature=0.2),
                timeout=cls._LLM_TIMEOUT_S,
            )
            if not raw or not isinstance(raw, str) or not raw.strip():
                return None

            understood, encouragement = cls._parse_json(raw)
            if understood is None:
                return None

            # ── الحراسة (طبقات قائمة) ──────────────────────────────────────────
            from app.services.skills.answer_redaction_skill import redact_final_answers
            from app.services.skills.arabic_stream_guard import is_probably_non_arabic
            from app.services.skills.content_integrity_skill import _strip_garbage_markers

            enc = _strip_garbage_markers(encouragement or "")
            enc, _ = redact_final_answers(enc, support_level=5)
            enc = enc.strip()
            if enc and is_probably_non_arabic(enc):
                enc = ""  # تشجيع غير عربي ⇒ نسقطه (القرار understood يبقى)
            return understood, enc
        except Exception:  # pragma: no cover — fail-safe
            return None

    @staticmethod
    def _parse_json(raw: str) -> tuple[bool | None, str]:
        """يستخرج (understood, encouragement) من مخرج LLM محروس. يُرجِع (None, '') عند الفشل."""
        import json
        import re

        text = raw.strip()
        # انتزاع أول كتلة JSON (النموذج قد يحفّها بنصّ).
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            with contextlib.suppress(Exception):
                data = json.loads(match.group(0))
                if isinstance(data, dict) and "understood" in data:
                    understood = bool(data.get("understood"))
                    enc = data.get("encouragement")
                    return understood, str(enc) if isinstance(enc, str) else ""
        # fallback: استدلال من كلمات صريحة.
        low = text.lower()
        if '"understood": true' in low or '"understood":true' in low:
            return True, ""
        if '"understood": false' in low or '"understood":false' in low:
            return False, ""
        return None, ""


_socratic_evaluator_singleton: SocraticEvaluatorSkill | None = None


def get_socratic_evaluator_skill() -> SocraticEvaluatorSkill:
    """يُرجع نسخة مفردة (lazy singleton)."""
    global _socratic_evaluator_singleton
    if _socratic_evaluator_singleton is None:
        _socratic_evaluator_singleton = SocraticEvaluatorSkill()
    return _socratic_evaluator_singleton


__all__ = [
    "HIDDEN_GOALS",
    "NEXT_FOCUS",
    "SocraticEvaluatorInput",
    "SocraticEvaluatorOutput",
    "SocraticEvaluatorSkill",
    "deterministically_correct",
    "get_socratic_evaluator_skill",
    "hidden_goal_for",
    "next_focus_for",
]
