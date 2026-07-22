"""
OutputFirewall — V46.0: جدار الحماية المزدوج للقنوات.

## المبدأ المعماري (Protocol V46.0)

يفرض هذا الـ Skill فصلاً صارماً بين قناتين مقدستين:

- **القناة A** (Channel A): حمولة JSON هيكلية — بيانات تربوية، حالة، نية بصرية.
  لا تحتوي أبداً على نثر أو HTML أو JSX أو تعليق سردي.

- **القناة B** (Channel B): صوت المعلم — Markdown نظيف، دافئ، سقراطي.
  لا تحتوي أبداً على وسوم HTML أو JSX أو مكونات واجهة مزيفة.

## الانتهاكات المرصودة

قبل V46.0 كانت الـ LLM تُخرج أحياناً:
- `<div>`, `<span>`, `<button>` داخل النص السردي
- مكونات JSX مزيفة (`<NextPortal>`, `<Accordion>`)
- أسهم قوائم منسدلة مزيفة وأزرار محاكاة
- نص HTML مضمَّن في الإجابة العربية

## آلية العمل

1. **الكشف**: regex patterns تُحدِّد التلوث في القناة B.
2. **التنظيف**: إزالة الوسوم مع الحفاظ على المحتوى النصي.
3. **الرفض**: إذا تجاوز التلوث عتبة الأمان → رفض وإعادة المحاولة.
4. **القياس**: Prometheus counters لكل رفض وتنظيف.

D-086 (2026-05-23): إنشاء OutputFirewall كـ Skill رسمي — V46.0.
"""

from __future__ import annotations

import logging
import re
import time
from typing import ClassVar, Literal

from pydantic import Field

from app.core.schemas import RobustBaseModel
from app.services.skills.base import BaseSkill

logger = logging.getLogger(__name__)

# ── Prometheus metrics — استيراد دفاعي ────────────────────────────────────────
try:
    from prometheus_client import Counter, Histogram

    _FIREWALL_CHECKS = Counter(
        "cogniforge_output_firewall_checks_total",
        "عدد فحوصات جدار الحماية",
        ["channel", "result"],
    )
    _FIREWALL_REJECTIONS = Counter(
        "cogniforge_output_firewall_rejections_total",
        "عدد الرفضات الكاملة (تلوث فوق العتبة)",
        ["channel", "reason"],
    )
    _FIREWALL_CLEANUPS = Counter(
        "cogniforge_output_firewall_cleanups_total",
        "عدد عمليات التنظيف الناجحة",
        ["channel"],
    )
    _FIREWALL_LATENCY = Histogram(
        "cogniforge_output_firewall_duration_seconds",
        "زمن فحص جدار الحماية",
        buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01],
    )
    _METRICS_AVAILABLE = True
except ImportError:
    _METRICS_AVAILABLE = False


def _record_check(channel: str, result: str) -> None:
    if _METRICS_AVAILABLE:
        _FIREWALL_CHECKS.labels(channel=channel, result=result).inc()


def _record_rejection(channel: str, reason: str) -> None:
    if _METRICS_AVAILABLE:
        _FIREWALL_REJECTIONS.labels(channel=channel, reason=reason).inc()


def _record_cleanup(channel: str) -> None:
    if _METRICS_AVAILABLE:
        _FIREWALL_CLEANUPS.labels(channel=channel).inc()


# ── أنماط التلوث في القناة B (صوت المعلم) ────────────────────────────────────

# وسوم HTML الصريحة
_HTML_TAG_PATTERN = re.compile(
    r"<(?:div|span|p|h[1-6]|ul|ol|li|table|tr|td|th|thead|tbody|"
    r"button|input|form|select|option|textarea|label|"
    r"img|a|nav|header|footer|section|article|aside|main|"
    r"script|style|link|meta|head|body|html|"
    r"br|hr|strong|em|b|i|u|s|code|pre|blockquote|"
    r"svg|path|circle|rect|polygon|g|defs|use|"
    r"iframe|video|audio|canvas|figure|figcaption)"
    r"(?:\s[^>]*)?>|</[a-zA-Z][a-zA-Z0-9]*>",
    re.IGNORECASE,
)

# مكونات JSX / React مزيفة (PascalCase مع props)
_JSX_COMPONENT_PATTERN = re.compile(
    r"<[A-Z][a-zA-Z0-9]*(?:\s[^>]*)?>|</[A-Z][a-zA-Z0-9]*>",
)

# بوابات Next.js المزيفة
_NEXTJS_PORTAL_PATTERN = re.compile(
    r"<(?:NextPortal|Portal|Suspense|ErrorBoundary|Provider|Context)[^>]*>",
    re.IGNORECASE,
)

# CSS مضمَّن
_INLINE_CSS_PATTERN = re.compile(
    r'style\s*=\s*["\'][^"\']*["\']|className\s*=\s*["\'][^"\']*["\']',
    re.IGNORECASE,
)

# أسهم قوائم منسدلة مزيفة وأزرار محاكاة
_FAKE_UI_ARTIFACTS_PATTERN = re.compile(
    r"▼\s*\w+|▶\s*\w+|►\s*\w+|"  # أسهم قوائم
    r"\[×\]|\[✓\]|\[→\]|"  # أزرار مزيفة
    r"onClick=\{|onChange=\{|onSubmit=\{|"  # event handlers
    r"import\s+React|from\s+['\"]react['\"]|"  # React imports
    r"export\s+default\s+function\s+[A-Z]",  # React component exports
)

# scaffolding تطبيق مزيف
_APP_SCAFFOLDING_PATTERN = re.compile(
    r"const\s+\w+\s*=\s*\(\)\s*=>\s*\{|"  # arrow function components
    r"function\s+[A-Z]\w+\s*\(\s*\)\s*\{|"  # function components
    r"return\s*\(\s*<|"  # JSX return
    r"ReactDOM\.render|"
    r"createRoot\(",
)

# جميع أنماط التلوث مجمَّعة مع أوزانها
_CONTAMINATION_PATTERNS: list[tuple[re.Pattern[str], str, float]] = [
    (_HTML_TAG_PATTERN, "html_tags", 0.4),
    (_JSX_COMPONENT_PATTERN, "jsx_components", 0.5),
    (_NEXTJS_PORTAL_PATTERN, "nextjs_portals", 0.6),
    (_INLINE_CSS_PATTERN, "inline_css", 0.3),
    (_FAKE_UI_ARTIFACTS_PATTERN, "fake_ui_artifacts", 0.3),
    (_APP_SCAFFOLDING_PATTERN, "app_scaffolding", 0.7),
]

# عتبة الرفض الكامل (مجموع الأوزان)
_REJECTION_THRESHOLD = 0.6

# ── Pydantic Contracts ────────────────────────────────────────────────────────


class FirewallInput(RobustBaseModel):
    """مدخلات جدار الحماية."""

    text: str = Field(..., description="النص المراد فحصه")
    channel: Literal["A", "B"] = Field(
        "B",
        description="القناة: A=JSON هيكلي، B=صوت المعلم",
    )
    intent: str = Field("educational", description="نية الإجابة للسياق")
    allow_cleanup: bool = Field(
        True,
        description="السماح بالتنظيف التلقائي بدل الرفض الكامل",
    )


class ContaminationDetail(RobustBaseModel):
    """تفاصيل تلوث مُكتشَف."""

    pattern_name: str
    weight: float
    match_count: int
    sample: str = Field("", description="مثال على التطابق (أول 80 حرف)")


class FirewallOutput(RobustBaseModel):
    """نتيجة فحص جدار الحماية."""

    passed: bool = Field(..., description="هل اجتاز النص الفحص")
    rejected: bool = Field(False, description="هل رُفض النص كلياً (تلوث فوق العتبة)")
    cleaned_text: str = Field("", description="النص بعد التنظيف (إذا طُبِّق)")
    contamination_score: float = Field(0.0, description="درجة التلوث (0-1)")
    details: list[ContaminationDetail] = Field(
        default_factory=list,
        description="تفاصيل التلوث المُكتشَف",
    )
    duration_ms: float = Field(0.0)


# ── دوال الكشف والتنظيف ───────────────────────────────────────────────────────


def _detect_contamination(
    text: str,
) -> tuple[float, list[ContaminationDetail]]:
    """يكشف التلوث في النص ويُعيد درجة التلوث وتفاصيله."""
    total_score = 0.0
    details: list[ContaminationDetail] = []

    for pattern, name, weight in _CONTAMINATION_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            total_score += weight
            sample = str(matches[0])[:80] if matches else ""
            details.append(
                ContaminationDetail(
                    pattern_name=name,
                    weight=weight,
                    match_count=len(matches),
                    sample=sample,
                )
            )

    return min(total_score, 1.0), details


def _clean_channel_b(text: str) -> str:
    """
    يُنظِّف القناة B من التلوث مع الحفاظ على المحتوى النصي.

    الاستراتيجية: استخراج النص من داخل الوسوم بدل حذفه كلياً،
    لأن الـ LLM قد يُغلِّف إجابة صحيحة داخل `<div>`.
    """
    cleaned = text

    # 1. استخراج النص من وسوم HTML (حذف الوسوم، الاحتفاظ بالمحتوى)
    cleaned = re.sub(r"<[^>]+>", "", cleaned)

    # 2. حذف JSX components كاملاً (لا محتوى نصي مفيد)
    cleaned = re.sub(
        r"<[A-Z][a-zA-Z0-9]*(?:\s[^>]*)?>.*?</[A-Z][a-zA-Z0-9]*>", "", cleaned, flags=re.DOTALL
    )
    cleaned = re.sub(r"<[A-Z][a-zA-Z0-9]*(?:\s[^>]*)?/>", "", cleaned)

    # 3. حذف inline CSS و className
    cleaned = re.sub(r'\s+style\s*=\s*["\'][^"\']*["\']', "", cleaned)
    cleaned = re.sub(r'\s+className\s*=\s*["\'][^"\']*["\']', "", cleaned)

    # 4. حذف event handlers
    cleaned = re.sub(r"\s+on[A-Z]\w+\s*=\s*\{[^}]*\}", "", cleaned)

    # 5. حذف React imports وscaffolding
    cleaned = re.sub(r"import\s+React[^\n]*\n?", "", cleaned)
    cleaned = re.sub(r'from\s+["\']react["\'][^\n]*\n?', "", cleaned)

    # 6. تنظيف الأسطر الفارغة المتعددة الناتجة عن الحذف
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()


# ── OutputFirewall Skill ──────────────────────────────────────────────────────


class OutputFirewall(BaseSkill[FirewallInput, FirewallOutput]):
    """
    جدار الحماية المزدوج للقنوات — V46.0.

    يفرض الفصل الصارم بين:
    - القناة A: JSON هيكلي (نية تربوية، حالة، بيانات بصرية)
    - القناة B: صوت المعلم (Markdown نظيف، لا HTML، لا JSX)

    الاستخدام:
        firewall = get_output_firewall()
        result = firewall.check(FirewallInput(text=llm_output, channel="B"))
        if result.rejected:
            # أعد المحاولة أو أرجع رسالة خطأ آمنة
            ...
        final_text = result.cleaned_text or llm_output
    """

    VERSION: ClassVar[str] = "1.0.0"
    SKILL_NAME: ClassVar[str] = "output_firewall"
    name: ClassVar[str] = "output_firewall"
    version: ClassVar[str] = "1.0.0"

    def run(self, inp: FirewallInput) -> FirewallOutput:
        """Polymorphic entry point (BaseSkill) — delegates to :meth:`check`."""
        return self.check(inp)

    def check(self, inp: FirewallInput) -> FirewallOutput:
        """
        يفحص النص ويُطبِّق جدار الحماية.

        للقناة B (صوت المعلم):
        - يكشف HTML/JSX/markup
        - ينظف إذا كان التلوث تحت العتبة
        - يرفض إذا تجاوز التلوث العتبة

        للقناة A (JSON هيكلي):
        - يتحقق من غياب النثر السردي
        - يرفض إذا وُجد نص سردي طويل
        """
        t0 = time.monotonic()

        try:
            if inp.channel == "B":
                return self._check_channel_b(inp, t0)
            return self._check_channel_a(inp, t0)
        except Exception as exc:
            logger.error("output_firewall.check_failed: %s", exc, exc_info=True)
            # Fail open — لا نكسر المسار أبداً
            return FirewallOutput(
                passed=True,
                rejected=False,
                cleaned_text=inp.text,
                contamination_score=0.0,
                duration_ms=round((time.monotonic() - t0) * 1000, 2),
            )

    def _check_channel_b(self, inp: FirewallInput, t0: float) -> FirewallOutput:
        """يفحص القناة B — صوت المعلم."""
        score, details = _detect_contamination(inp.text)
        duration_ms = round((time.monotonic() - t0) * 1000, 2)

        if score == 0.0:
            _record_check("B", "clean")
            return FirewallOutput(
                passed=True,
                rejected=False,
                cleaned_text=inp.text,
                contamination_score=0.0,
                details=[],
                duration_ms=duration_ms,
            )

        # تلوث مُكتشَف
        reason = details[0].pattern_name if details else "unknown"
        logger.warning(
            "output_firewall.channel_b_contamination score=%.2f reason=%s intent=%s",
            score,
            reason,
            inp.intent,
        )

        if score >= _REJECTION_THRESHOLD:
            # تلوث فوق العتبة — رفض كامل
            _record_check("B", "rejected")
            _record_rejection("B", reason)
            logger.error(
                "output_firewall.channel_b_REJECTED score=%.2f patterns=%s",
                score,
                [d.pattern_name for d in details],
            )
            return FirewallOutput(
                passed=False,
                rejected=True,
                cleaned_text="",
                contamination_score=score,
                details=details,
                duration_ms=duration_ms,
            )

        # تلوث تحت العتبة — تنظيف
        if inp.allow_cleanup:
            cleaned = _clean_channel_b(inp.text)
            _record_check("B", "cleaned")
            _record_cleanup("B")
            logger.info(
                "output_firewall.channel_b_cleaned score=%.2f chars=%d→%d",
                score,
                len(inp.text),
                len(cleaned),
            )
            return FirewallOutput(
                passed=True,
                rejected=False,
                cleaned_text=cleaned,
                contamination_score=score,
                details=details,
                duration_ms=duration_ms,
            )

        # تنظيف غير مسموح — رفض
        _record_check("B", "rejected_no_cleanup")
        _record_rejection("B", "cleanup_disabled")
        return FirewallOutput(
            passed=False,
            rejected=True,
            cleaned_text="",
            contamination_score=score,
            details=details,
            duration_ms=duration_ms,
        )

    def _check_channel_a(self, inp: FirewallInput, t0: float) -> FirewallOutput:
        """
        يفحص القناة A — JSON هيكلي.

        القناة A يجب أن تكون JSON نقياً. إذا وُجد نثر سردي طويل
        (> 200 حرف خارج مفاتيح JSON) فهذا انتهاك.
        """
        duration_ms = round((time.monotonic() - t0) * 1000, 2)
        text = inp.text.strip()

        # القناة A يجب أن تبدأ بـ { أو [
        if text and not (text.startswith("{") or text.startswith("[")):
            # نص سردي في قناة JSON — انتهاك
            _record_check("A", "narrative_in_json_channel")
            _record_rejection("A", "non_json_content")
            logger.warning(
                "output_firewall.channel_a_narrative_leak chars=%d preview=%.60s",
                len(text),
                text,
            )
            return FirewallOutput(
                passed=False,
                rejected=True,
                cleaned_text="",
                contamination_score=1.0,
                details=[
                    ContaminationDetail(
                        pattern_name="narrative_in_json_channel",
                        weight=1.0,
                        match_count=1,
                        sample=text[:80],
                    )
                ],
                duration_ms=duration_ms,
            )

        _record_check("A", "clean")
        return FirewallOutput(
            passed=True,
            rejected=False,
            cleaned_text=text,
            contamination_score=0.0,
            duration_ms=duration_ms,
        )


# ── Singleton ─────────────────────────────────────────────────────────────────
# Singleton: مُهيَّأ مرة واحدة — لا state داخلي، آمن للاستخدام المتزامن.
def get_output_firewall() -> OutputFirewall:
    """يُعيد singleton من OutputFirewall (BaseSkill.instance)."""
    return OutputFirewall.instance()


def apply_channel_b_firewall(
    text: str,
    intent: str = "educational",
    allow_cleanup: bool = True,
) -> tuple[str, bool]:
    """
    دالة مساعدة سريعة لتطبيق جدار الحماية على القناة B.

    تُستخدم في local_graph.py و orchestrator_client.py كطبقة دفاع أخيرة.

    Returns:
        (cleaned_text, was_rejected): النص المُنظَّف وهل رُفض الأصل.
        إذا رُفض → cleaned_text فارغ، المُستدعي يُعيد المحاولة أو يُرجع fallback.
    """
    firewall = get_output_firewall()
    result = firewall.check(
        FirewallInput(text=text, channel="B", intent=intent, allow_cleanup=allow_cleanup)
    )
    if result.rejected:
        return "", True
    return result.cleaned_text or text, False


__all__ = [
    "ContaminationDetail",
    "FirewallInput",
    "FirewallOutput",
    "OutputFirewall",
    "apply_channel_b_firewall",
    "get_output_firewall",
]
