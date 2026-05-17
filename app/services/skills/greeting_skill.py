"""GreetingSkill — Skill رسمي لردود التحيات الحتمية بدون LLM.

ISS-079 (D-067 — 2026-05-17):
المستخدم شاهد كارثة: "السلام عليكم" → رد etymological طويل بكلمات أجنبية
("hopephe pepe aaaa" / "وتُستَخدم كتعبير ترحيبي" بدلاً من رد التحية).

السبب الجذري: نماذج OpenRouter المجانية تُولِّد etymology طويلة عند سؤال
"السلام عليكم" مع system prompt "أجب بدقة" — تفسر التحية كسؤال علمي.

الحل: Skill رسمي يُعيد رد deterministic للتحيات الشائعة (0ms، 100% نظيف).
يحترم CLAUDE.md §0.5 — Skills Architecture بدلاً من Prompt Spaghetti.

Contract:
    skill = GreetingSkill()
    result = skill.invoke(GreetingSkillInput(question="السلام عليكم"))
    if isinstance(result, GreetingSkillOutput):
        # رد deterministic — لا LLM، لا تأخير
        return result.response
    # SkillFailure → caller يستخدم Skill آخر (BAC، general LLM)
"""

from __future__ import annotations

import re
import time
from typing import ClassVar, Literal

try:
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover

    class BaseModel:  # type: ignore[no-redef]
        pass

    def Field(*args, **kwargs):  # type: ignore[no-redef]  # noqa: N802
        return kwargs.get("default")


class GreetingSkillInput(BaseModel):
    """مدخلات Skill التحية."""

    question: str = Field(..., min_length=1, max_length=500)

    model_config: ClassVar[dict[str, object]] = {"arbitrary_types_allowed": True}


class GreetingSkillOutput(BaseModel):
    """مخرج Skill التحية عند التطابق."""

    skill: Literal["greeting"] = "greeting"
    success: Literal[True] = True
    matched_greeting: str
    response: str
    language: Literal["ar", "en", "fr"] = "ar"

    model_config: ClassVar[dict[str, object]] = {"arbitrary_types_allowed": True}


class GreetingSkillFailure(BaseModel):
    """مخرج Skill عند عدم التطابق."""

    skill: Literal["greeting"] = "greeting"
    success: Literal[False] = False
    reason: str

    model_config: ClassVar[dict[str, object]] = {"arbitrary_types_allowed": True}


GreetingSkillResult = GreetingSkillOutput | GreetingSkillFailure


# ─── قاموس التحيات الشامل ─────────────────────────────────────────────────────
# Key = normalized greeting، Value = response deterministic
_GREETING_RESPONSES: dict[str, tuple[str, str]] = {
    # (response, language)
    "السلام عليكم": (
        "وعليكم السلام ورحمة الله وبركاته! 🌿 كيف يمكنني مساعدتك في دراستك اليوم؟",
        "ar",
    ),
    "السلام": ("وعليكم السلام! كيف يمكنني مساعدتك اليوم؟", "ar"),
    "وعليكم السلام": ("أهلاً وسهلاً بك! كيف يمكنني مساعدتك في دراستك؟", "ar"),
    "مرحبا": ("أهلاً وسهلاً! كيف يمكنني مساعدتك اليوم؟", "ar"),
    "مرحبًا": ("أهلاً وسهلاً! كيف يمكنني مساعدتك اليوم؟", "ar"),
    "أهلا": ("أهلاً وسهلاً بك! كيف يمكنني مساعدتك؟", "ar"),
    "أهلاً": ("أهلاً وسهلاً بك! كيف يمكنني مساعدتك؟", "ar"),
    "هلا": ("أهلاً بك! كيف يمكنني مساعدتك؟", "ar"),
    "هلاً": ("أهلاً بك! كيف يمكنني مساعدتك؟", "ar"),
    "كيف حالك": ("بخير والحمد لله! شكراً لسؤالك. كيف يمكنني مساعدتك في دراستك؟", "ar"),
    "كيف الحال": ("بخير والحمد لله! كيف يمكنني مساعدتك اليوم؟", "ar"),
    "صباح الخير": ("صباح النور! كيف يمكنني مساعدتك في دراستك اليوم؟", "ar"),
    "صباح النور": ("صباح الخير! كيف يمكنني مساعدتك؟", "ar"),
    "مساء الخير": ("مساء النور! كيف يمكنني مساعدتك في دراستك؟", "ar"),
    "مساء النور": ("مساء الخير! كيف يمكنني مساعدتك؟", "ar"),
    "شكرا": ("العفو! 😊 إذا احتجت أي مساعدة أخرى، أنا هنا.", "ar"),
    "شكراً": ("العفو! 😊 سعيدٌ بمساعدتك.", "ar"),
    "شكرا جزيلا": ("العفو، لا شكر على واجب! 😊", "ar"),
    "hello": ("Hi! How can I help you with your studies today?", "en"),
    "hi": ("Hello! How can I help you today?", "en"),
    "hey": ("Hey there! How can I help?", "en"),
    "good morning": ("Good morning! How can I help you today?", "en"),
    "good evening": ("Good evening! How can I help you?", "en"),
    "bonjour": ("Bonjour ! Comment puis-je vous aider aujourd'hui ?", "fr"),
    "salut": ("Salut ! Comment puis-je vous aider ?", "fr"),
}


# ─── Blockers — منع fastpath عندما السؤال يحوي طلب علمي ───────────────────────
# D-065: السؤال الذي يحوي فعل تعليمي يذهب للـ LLM، حتى لو بدأ بتحية
_EDUCATIONAL_BLOCKERS: tuple[str, ...] = (
    "اشرح",
    "احسب",
    "اوجد",
    "أوجد",
    "حل ",
    "اعطني",
    "أعطني",
    "هات",
    "تمرين",
    "مسألة",
    "مادة",
    "درس",
    "قانون",
    "نظرية",
    "بكالوريا",
    "explain",
    "solve",
    "calculate",
    "find",
    "give me",
    "help with",
    "ما هو",
    "ما هي",
    "لماذا",
    "متى",
    "أين",
)

# "كيف" interrogative — blocker إلا إذا كان في تحية شائعة
_KAYFA_GREETINGS: tuple[str, ...] = (
    "كيف حالك",
    "كيف الحال",
    "كيف الأحوال",
    "كيف صحتك",
)

# الكلمات المسموح ظهورها بعد التحية (وعليكم، ورحمة، إلخ)
_ALLOWED_TAIL_WORDS: frozenset[str] = frozenset(
    {
        "وعليكم",
        "السلام",
        "ورحمة",
        "ورحمت",
        "رحمة",
        "الله",
        "وبركاته",
        "بركاته",
        "وسهلاً",
        "وسهلا",
        "بكم",
        "بك",
        "والله",
        "اليوم",
        "يا",
        "أستاذ",
        "أستاذي",
        "والاكرام",
        "في",
    }
)


def _record_metric(status: str, duration_s: float) -> None:
    """يبث Prometheus metrics للـ greeting skill — يحترم §0 doctrine."""
    try:
        from app.telemetry.unified_observability import get_unified_observability

        obs = get_unified_observability()
        obs.record_metric(
            "skill.greeting.invocations.total",
            1.0,
            labels={"status": status},
        )
        obs.record_metric("skill.greeting.duration_seconds", duration_s)
    except Exception:  # pragma: no cover
        pass


class GreetingSkill:
    """Skill رسمي للتحيات — يعيد ردود deterministic بدون LLM.

    Usage:
        skill = GreetingSkill()
        result = skill.invoke(GreetingSkillInput(question="السلام عليكم"))
        if isinstance(result, GreetingSkillOutput):
            return result.response  # 0ms response
        # SkillFailure → التالي في الـ fallback chain

    قواعد إلزامية:
    1. لا LLM call — كل الردود محفوظة في `_GREETING_RESPONSES`.
    2. blockers صارمة — أي طلب علمي يُلغي الـ fastpath.
    3. tail allowlist — السماح بـ "وبركاته"/"ورحمة الله" بعد التحية فقط.
    4. مقاييس Prometheus — `cogniforge_skill_greeting_invocations_total{status}`.
    """

    name: str = "greeting"
    version: str = "1.0.0"

    def invoke(self, payload: GreetingSkillInput) -> GreetingSkillResult:
        """نقطة الدخول — يُرجع GreetingSkillOutput أو GreetingSkillFailure."""
        t0 = time.perf_counter()
        try:
            response = self._match(payload.question)
            duration = time.perf_counter() - t0

            if response is None:
                _record_metric("no_match", duration)
                return GreetingSkillFailure(reason="no_greeting_match")

            text, language, matched = response
            _record_metric("success", duration)
            return GreetingSkillOutput(
                matched_greeting=matched,
                response=text,
                language=language,  # type: ignore[arg-type]
            )
        except Exception:
            duration = time.perf_counter() - t0
            _record_metric("error", duration)
            return GreetingSkillFailure(reason="internal_error")

    @staticmethod
    def _match(query: str) -> tuple[str, str, str] | None:
        """يطابق التحية — يُرجع (response, language, matched_key) أو None."""
        if not query:
            return None
        normalized = query.strip().lower()
        cleaned = re.sub(r"[^\w\s؀-ۿ]", "", normalized).strip()
        if not cleaned:
            return None

        # blocker: كيف interrogative (إلا تحيات كيف حالك)
        if "كيف" in normalized and not any(g in normalized for g in _KAYFA_GREETINGS):
            return None

        # blockers علمية — أي فعل سؤال يُلغي fastpath
        for blocker in _EDUCATIONAL_BLOCKERS:
            if blocker in normalized:
                return None

        # طابق exact أو starts_with بهامش ≤ 25 char (السلام عليكم ورحمة الله...)
        for greeting, (response, lang) in _GREETING_RESPONSES.items():
            g_lower = greeting.lower()
            if cleaned == g_lower:
                return response, lang, greeting
            if cleaned.startswith(g_lower) and len(cleaned) - len(g_lower) <= 25:
                tail_words = cleaned[len(g_lower) :].strip().split()
                if all(w in _ALLOWED_TAIL_WORDS or len(w) <= 2 for w in tail_words):
                    return response, lang, greeting
        return None


__all__ = [
    "GreetingSkill",
    "GreetingSkillFailure",
    "GreetingSkillInput",
    "GreetingSkillOutput",
    "GreetingSkillResult",
]
