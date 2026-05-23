"""
اختبارات OutputFirewall و TopicLock — Protocol V46.0 (D-086).

يتحقق من:
1. OutputFirewall يكشف HTML/JSX في القناة B ويُنظِّفها.
2. OutputFirewall يرفض التلوث الشديد (فوق العتبة).
3. OutputFirewall يمرِّر النص النظيف بدون تعديل.
4. OutputFirewall يرفض النثر في القناة A (JSON channel).
5. TopicLock يكشف تسرب مواضيع (احتمالات → تفاضل).
6. TopicLock يمرِّر الإجابات النظيفة.
7. TopicLock يتجاهل انتقالات الموضوع الصريحة.
8. apply_channel_b_firewall دالة مساعدة تعمل بشكل صحيح.
"""

from __future__ import annotations

from app.services.skills.output_firewall import (
    FirewallInput,
    OutputFirewall,
    apply_channel_b_firewall,
    get_output_firewall,
)
from app.services.skills.topic_lock import (
    TopicLock,
    TopicLockInput,
    get_topic_lock,
)

# ── OutputFirewall — القناة B ─────────────────────────────────────────────────


class TestOutputFirewallChannelB:
    """اختبارات جدار الحماية على القناة B (صوت المعلم)."""

    def setup_method(self) -> None:
        self.firewall = OutputFirewall()

    def test_clean_arabic_markdown_passes(self) -> None:
        """نص عربي نظيف بـ Markdown يجتاز الفحص بدون تعديل."""
        text = (
            "## شرح قانون الاحتمالات\n\n"
            "الاحتمال هو نسبة عدد الحالات المواتية إلى عدد الحالات الممكنة.\n\n"
            "$$P(A) = \\frac{|A|}{|\\Omega|}$$\n\n"
            "**مثال:** إذا كان الكيس يحتوي على 3 كرات حمراء و2 زرقاء،\n"
            "فاحتمال سحب كرة حمراء هو \\(\\frac{3}{5}\\)."
        )
        result = self.firewall.check(FirewallInput(text=text, channel="B"))
        assert result.passed is True
        assert result.rejected is False
        assert result.contamination_score == 0.0
        assert result.cleaned_text == text

    def test_html_div_detected_and_cleaned(self) -> None:
        """وسوم <div> تُكشَف وتُنظَّف مع الحفاظ على المحتوى النصي."""
        text = "<div class='answer'>الاحتمال هو نسبة الحالات المواتية إلى الحالات الممكنة.</div>"
        result = self.firewall.check(FirewallInput(text=text, channel="B"))
        assert result.passed is True
        assert result.rejected is False
        assert result.contamination_score > 0.0
        assert "<div" not in result.cleaned_text
        assert "الاحتمال" in result.cleaned_text

    def test_jsx_component_above_threshold_rejected(self) -> None:
        """مكونات JSX متعددة فوق العتبة تُرفض كلياً."""
        text = (
            "<ProbabilityTree>\n"
            "  <Node label='A' />\n"
            "  <Node label='B' />\n"
            "</ProbabilityTree>\n"
            "<Accordion title='الحل'>\n"
            "  <AccordionItem>الخطوة الأولى</AccordionItem>\n"
            "</Accordion>"
        )
        result = self.firewall.check(FirewallInput(text=text, channel="B"))
        assert result.rejected is True
        assert result.passed is False
        assert result.cleaned_text == ""

    def test_nextjs_portal_rejected(self) -> None:
        """بوابات Next.js المزيفة تُرفض."""
        text = (
            "إليك الشرح:\n"
            "<NextPortal target='sidebar'>\n"
            "  <MathCard equation='P(A)=3/5' />\n"
            "</NextPortal>"
        )
        result = self.firewall.check(FirewallInput(text=text, channel="B"))
        assert result.rejected is True

    def test_inline_css_with_html_tag_rejected(self) -> None:
        """<span> مع CSS مضمَّن يُرفض (html_tags=0.4 + inline_css=0.3 = 0.7 ≥ عتبة)."""
        text = '<span style="color: red; font-weight: bold;">الاحتمال المطلوب هو 3/5</span>'
        result = self.firewall.check(FirewallInput(text=text, channel="B"))
        # html_tags (0.4) + inline_css (0.3) = 0.7 ≥ _REJECTION_THRESHOLD (0.6) → رفض
        assert result.rejected is True
        assert result.contamination_score >= 0.6

    def test_standalone_inline_css_cleaned(self) -> None:
        """CSS مضمَّن بدون وسوم HTML يُنظَّف (وزن 0.3 < عتبة 0.6)."""
        text = 'الاحتمال المطلوب هو 3/5 className="highlight"'
        result = self.firewall.check(FirewallInput(text=text, channel="B"))
        assert result.passed is True
        assert "className=" not in result.cleaned_text

    def test_react_import_rejected(self) -> None:
        """React imports في النص السردي تُرفض."""
        text = (
            "import React from 'react';\n"
            "export default function Answer() {\n"
            "  return (<div>الاحتمال = 3/5</div>);\n"
            "}"
        )
        result = self.firewall.check(FirewallInput(text=text, channel="B"))
        assert result.rejected is True

    def test_cleanup_disabled_rejects_instead(self) -> None:
        """عند تعطيل التنظيف، التلوث تحت العتبة يُرفض بدل التنظيف."""
        text = "<p>الاحتمال هو 3/5</p>"
        result = self.firewall.check(FirewallInput(text=text, channel="B", allow_cleanup=False))
        assert result.rejected is True

    def test_empty_text_passes(self) -> None:
        """النص الفارغ يجتاز الفحص."""
        result = self.firewall.check(FirewallInput(text="", channel="B"))
        assert result.passed is True

    def test_latex_math_not_flagged(self) -> None:
        """معادلات LaTeX لا تُعتبر تلوثاً."""
        text = (
            "الحل:\n"
            "$$P(A \\cap B) = P(A) \\times P(B|A)$$\n"
            "بالتعويض: $$P = \\frac{3}{5} \\times \\frac{2}{4} = \\frac{3}{10}$$"
        )
        result = self.firewall.check(FirewallInput(text=text, channel="B"))
        assert result.passed is True
        assert result.contamination_score == 0.0


# ── OutputFirewall — القناة A ─────────────────────────────────────────────────


class TestOutputFirewallChannelA:
    """اختبارات جدار الحماية على القناة A (JSON هيكلي)."""

    def setup_method(self) -> None:
        self.firewall = OutputFirewall()

    def test_valid_json_passes(self) -> None:
        """JSON صحيح يجتاز الفحص."""
        text = '{"type": "probability_tree", "nodes": [], "routing_mode": "MODE_A"}'
        result = self.firewall.check(FirewallInput(text=text, channel="A"))
        assert result.passed is True
        assert result.rejected is False

    def test_narrative_in_json_channel_rejected(self) -> None:
        """نثر سردي في قناة JSON يُرفض."""
        text = "إليك شرح مفصل للاحتمالات وكيفية حسابها خطوة بخطوة..."
        result = self.firewall.check(FirewallInput(text=text, channel="A"))
        assert result.rejected is True
        assert result.contamination_score == 1.0

    def test_json_array_passes(self) -> None:
        """مصفوفة JSON تجتاز الفحص."""
        text = '[{"step": 1, "label": "الحدث الأول"}, {"step": 2, "label": "الحدث الثاني"}]'
        result = self.firewall.check(FirewallInput(text=text, channel="A"))
        assert result.passed is True


# ── apply_channel_b_firewall helper ──────────────────────────────────────────


class TestApplyChannelBFirewall:
    """اختبارات الدالة المساعدة apply_channel_b_firewall."""

    def test_clean_text_returned_unchanged(self) -> None:
        text = "الاحتمال هو نسبة الحالات المواتية."
        cleaned, rejected = apply_channel_b_firewall(text)
        assert rejected is False
        assert cleaned == text

    def test_html_cleaned(self) -> None:
        text = "<p>الاحتمال هو نسبة الحالات المواتية.</p>"
        cleaned, rejected = apply_channel_b_firewall(text)
        assert rejected is False
        assert "<p>" not in cleaned
        assert "الاحتمال" in cleaned

    def test_heavy_jsx_rejected(self) -> None:
        text = (
            "<ProbabilityTree>\n"
            "<Node /><Node /><Node />\n"
            "</ProbabilityTree>\n"
            "import React from 'react';\n"
            "export default function Tree() { return (<div />); }"
        )
        cleaned, rejected = apply_channel_b_firewall(text)
        assert rejected is True
        assert cleaned == ""

    def test_empty_string_passes(self) -> None:
        _cleaned, rejected = apply_channel_b_firewall("")
        assert rejected is False

    def test_singleton_reuse(self) -> None:
        """get_output_firewall يُعيد نفس الـ instance."""
        fw1 = get_output_firewall()
        fw2 = get_output_firewall()
        assert fw1 is fw2


# ── TopicLock ─────────────────────────────────────────────────────────────────


class TestTopicLock:
    """اختبارات قفل الموضوع."""

    def setup_method(self) -> None:
        self.lock = TopicLock()

    def _prob_history(self) -> list[dict[str, str]]:
        """تاريخ محادثة في موضوع الاحتمالات."""
        return [
            {"role": "user", "content": "اشرح لي الاحتمالات في البكالوريا"},
            {"role": "assistant", "content": "الاحتمال هو نسبة الحالات المواتية..."},
            {"role": "user", "content": "ما هو فضاء العينة في هذا التمرين؟"},
        ]

    def test_clean_probability_answer_passes(self) -> None:
        """إجابة نظيفة في موضوع الاحتمالات تجتاز الفحص."""
        result = self.lock.check(
            TopicLockInput(
                response="احتمال سحب كرة حمراء = 3/5 لأن فضاء العينة يحتوي 5 كرات.",
                question="ما احتمال سحب كرة حمراء؟",
                history=self._prob_history(),
            )
        )
        assert result.passed is True
        assert result.active_topic == "probability"

    def test_calculus_leak_in_probability_context_flagged(self) -> None:
        """تسرب مفاهيم التفاضل في سياق الاحتمالات يُسجَّل كانتهاك."""
        result = self.lock.check(
            TopicLockInput(
                response=(
                    "لحساب الاحتمال نستخدم المشتقة الأولى للدالة ثم نُطبِّق قاعدة السلسلة للتكامل."
                ),
                question="ما احتمال سحب كرة حمراء؟",
                history=self._prob_history(),
            )
        )
        assert result.passed is False
        assert "calculus" in result.leaked_topics
        assert result.active_topic == "probability"

    def test_explicit_topic_transition_bypasses_lock(self) -> None:
        """انتقال صريح للموضوع يُلغي القفل."""
        result = self.lock.check(
            TopicLockInput(
                response="بالتأكيد، دعنا ننتقل إلى موضوع التفاضل والتكامل.",
                question="انتقل إلى التفاضل",
                history=self._prob_history(),
            )
        )
        assert result.passed is True
        assert result.is_topic_transition is True

    def test_no_history_passes(self) -> None:
        """بدون تاريخ لا يوجد موضوع نشط — يجتاز الفحص."""
        result = self.lock.check(
            TopicLockInput(
                response="الاحتمال هو 3/5.",
                question="ما الاحتمال؟",
                history=[],
            )
        )
        assert result.passed is True
        assert result.active_topic is None

    def test_active_topic_override(self) -> None:
        """تجاوز الكشف التلقائي للموضوع يعمل بشكل صحيح."""
        result = self.lock.check(
            TopicLockInput(
                response="نستخدم المشتقة لحل هذه المسألة.",
                question="اشرح",
                history=[],
                active_topic_override="probability",
            )
        )
        assert result.passed is False
        assert "calculus" in result.leaked_topics

    def test_singleton_reuse(self) -> None:
        """get_topic_lock يُعيد نفس الـ instance."""
        tl1 = get_topic_lock()
        tl2 = get_topic_lock()
        assert tl1 is tl2

    def test_exception_in_check_fails_open(self) -> None:
        """أي استثناء داخلي يُعيد passed=True (fail-open)."""
        # نُمرِّر history غير صالح — يجب ألا يكسر المسار
        result = self.lock.check(
            TopicLockInput(
                response="إجابة عادية.",
                question="سؤال عادي.",
                history=[{"role": "user"}],  # content مفقود
            )
        )
        assert result.passed is True
