"""D-124 — مخرج الطوارئ الحتمي: كسر حلقة الكاروسيل + شرح رياضي مباشر.

الكارثة (transcript حي بعد D-123): D-123 نجح (لا «كرة زرقاء»/«سحب 2 من 11» — التلوّث
والهلوسة اختفيا) لكنه خلق «حلقة الموت اللانهائية»: بما أن D-116/D-123 يجعلان كل سؤال
احتمالات يُنهي دائماً إلى الكاروسيل (صفر LLM)، فإن سؤالاً محدّداً («بخصوص الكرات الحمراء
كيف وجدنا 4؟») أو حيرة متكررة («لم أفهم»×N) يُعيدان طباعة **نفس الكاروسيل** بلا تقدّم.

D-124 (تشخيص المالك CTO-grade): عداد محاولات + مخرج طوارئ ⇒ سؤال محدّد (فوراً) أو حيرة
≥ 2 يكسران الكاروسيل ويقدّمان شرحاً رياضياً **مباشراً حتمياً** (من التمرين الرسمي عبر
ProbabilityCalculatorSkill، history=None — D-123 — صفر LLM، صفر هلوسة).

stdlib + standalone logic + source-inspection — يعمل في الـ sandbox بلا pydantic.
"""

from __future__ import annotations

from pathlib import Path

from app.infrastructure.clients.orchestrator.tutor_sources import read_tutor_source

REPO_ROOT = Path(__file__).resolve().parents[2]
CLIENT_SRC = (
    read_tutor_source()
)  # D-163: عقل الاحتمالات استُخرج للوحدة المستقلة — نضمّ الاثنين ليصمد أي pin


# ── نُسَخ standalone مطابقة لمنطق D-124 (sandbox-safe replicas) ────────────────
_CONFUSION_MARKERS: tuple[str, ...] = (
    "لم أفهم",
    "لم افهم",
    "مفهمتش",
    "ما فهمت",
    "مافهمت",
    "ما افهم",
    "لا أفهم",
    "لا افهم",
    "مازلت",
    "ما زلت",
    "اشرح لي",
    "اشرحلي",
    "وضح لي",
    "وضحلي",
    "أين الشرح",
    "اين الشرح",
    "لا أعرف",
    "لا اعرف",
    "ماعرفت",
    "ما عرفت",
    "صعب",
    "أعد الشرح",
    "اعد الشرح",
)


def _count_probability_confusion(question: str, history: list[dict[str, str]] | None) -> int:
    texts: list[str] = [str(question or "")]
    for msg in history or []:
        if isinstance(msg, dict) and msg.get("role") == "user":
            texts.append(str(msg.get("content") or ""))
    count = 0
    for text in texts:
        low = text.strip()
        if low in ("؟", "?", "؟؟", "??", "؟!", "!؟"):
            count += 1
            continue
        if any(marker in low for marker in _CONFUSION_MARKERS):
            count += 1
    return count


def _detect_subpart_question(question: str) -> str | None:
    q = (question or "").lower()
    if any(m in q for m in ("حمراء", "الحمراء", "احمر", "الأحمر", "الاحمر", "حمر")):
        return "red"
    if any(m in q for m in ("خضراء", "الخضراء", "اخضر", "الأخضر", "الاخضر", "خضر")):
        return "green"
    if any(m in q for m in ("بيضاء", "البيضاء", "ابيض", "الأبيض", "الابيض", "بيض")):
        return "white"
    if any(m in q for m in ("165", "فضاء العينة", "العدد الكلي", "الفضاء", "c(11", "الكلي")):
        return "total"
    if any(
        m in q for m in ("14", "الملائمة", "الملاءمة", "نجمع", "لماذا نجمع", "الحالات الملائمة")
    ):
        return "sum"
    return None


def _fmt_comb(c: int, k: int, fav: int) -> str:
    # ISS-121 (D-154): نسخة مرآة للعقد الحالي — LaTeX (LTR-معزول، ناجٍ من الحجب بنيوياً).
    if k < 1 or c < k:
        return f"$C_{{{c}}}^{{{k}}} = {fav}$"
    num = r"\times ".join(str(c - i) for i in range(k))
    den = r"\times ".join(str(k - i) for i in range(k))
    return f"$C_{{{c}}}^{{{k}}} = \\dfrac{{{num}}}{{{den}}} = {fav}$"


# ── 1. كاشف السؤال المحدّد ─────────────────────────────────────────────────────
class TestDetectSubpartQuestion:
    def test_red_question(self) -> None:
        assert _detect_subpart_question("بخصوص الكرات الحمراء كيف وجدنا 4؟") == "red"

    def test_green_question(self) -> None:
        assert _detect_subpart_question("ولماذا الخضراء أعطت 10") == "green"

    def test_white_question(self) -> None:
        assert _detect_subpart_question("لماذا اللون الأبيض مستحيل") == "white"

    def test_total_question(self) -> None:
        assert _detect_subpart_question("كيف حصلنا على 165") == "total"
        assert _detect_subpart_question("ما هو فضاء العينة") == "total"

    def test_sum_question(self) -> None:
        assert _detect_subpart_question("لماذا نجمع لنحصل على 14") == "sum"

    def test_general_first_question_returns_none(self) -> None:
        # «كيف افهم السؤال الأول» سؤال عام ⇒ None ⇒ يبقى للكاروسيل البصري.
        assert _detect_subpart_question("كيف افهم السؤال الأول") is None
        assert _detect_subpart_question("اشرح لي التمرين") is None
        assert _detect_subpart_question("لم أفهم") is None


# ── 2. عداد الحيرة (يتجاهل «كيف» المجرّدة) ──────────────────────────────────────
class TestConfusionCounter:
    def test_kayf_alone_not_counted(self) -> None:
        # «كيف افهم السؤال الأول» الأولى ليست حيرة (لا تكسر التجربة البصرية).
        assert _count_probability_confusion("كيف افهم السؤال الأول", None) == 0

    def test_repeated_confusion_counts(self) -> None:
        history = [
            {"role": "user", "content": "لم أفهم"},
            {"role": "assistant", "content": "<carousel>"},
        ]
        # السؤال الحالي «اشرح لي» + history «لم أفهم» = 2.
        assert _count_probability_confusion("اشرح لي", history) == 2

    def test_bare_question_mark_counts(self) -> None:
        history = [{"role": "user", "content": "؟"}]
        assert _count_probability_confusion("؟", history) == 2

    def test_assistant_messages_ignored(self) -> None:
        history = [{"role": "assistant", "content": "لم أفهم كذا"}]
        assert _count_probability_confusion("مرحبا", history) == 0

    def test_escape_threshold(self) -> None:
        # المخرج يُفعَّل عند subpart أو counter ≥ 2.
        assert _count_probability_confusion("لم أفهم", None) == 1  # دون العتبة → كاروسيل
        h = [{"role": "user", "content": "لم أفهم"}]
        assert _count_probability_confusion("لم أفهم", h) == 2  # العتبة → مخرج الطوارئ


# ── 3. منسّق التوافيق (توسيع المضروب الحتمي) ────────────────────────────────────
class TestFmtComb:
    def test_red_4_choose_3(self) -> None:
        assert (
            _fmt_comb(4, 3, 4)
            == "$C_{4}^{3} = \\dfrac{4\\times 3\\times 2}{3\\times 2\\times 1} = 4$"
        )

    def test_green_5_choose_3(self) -> None:
        out = _fmt_comb(5, 3, 10)
        assert out.startswith("$C_{5}^{3}") and out.endswith("= 10$")

    def test_total_11_choose_3(self) -> None:
        out = _fmt_comb(11, 3, 165)
        assert "C_{11}^{3}" in out and out.endswith("= 165$")

    def test_impossible_guard(self) -> None:
        # c < k ⇒ لا توسيع مضروب مضلِّل.
        assert _fmt_comb(2, 3, 0) == "$C_{2}^{3} = 0$"


# ── 4. النصّ يَنجو من حجب الإجابة (D-113) — يتجنّب أنماط الحجب ────────────────────
class TestRedactionSurvival:
    def test_fmt_comb_survives_final_result_regex(self) -> None:
        # _FINAL_RESULT_RE: [PEC](...)=<عدد صرف>. بعد «C(4,3) = » يأتي «(» لا رقم.
        import re

        num_re = r"[-+]?\d[\d.,]*\s*(?:/\s*\d[\d.,]*)?\s*%?"
        final_result_re = re.compile(
            r"(?P<lhs>[PECpec]\s*(?:_?[A-Za-z])?\s*\([^)\n]{0,60}\)\s*=\s*)(?P<rhs>" + num_re + r")"
        )
        # ISS-121 (D-154): صيغة LaTeX ``C_{n}^{k}`` بلا قوسين بعد C ⇒ النمط
        # ``C(...)=عدد`` لا يُطابَق بنيوياً ⇒ تَنجو من الحجب.
        assert final_result_re.search(_fmt_comb(4, 3, 4)) is None
        assert final_result_re.search(_fmt_comb(11, 3, 165)) is None

    def test_probability_line_avoids_conclusion_keywords(self) -> None:
        # «الاحتمال = 14/165» لا يبدأ بـ إذن/ومنه/النتيجة/الجواب/فإن ⇒ يَنجو.
        import re

        num_re = r"[-+]?\d[\d.,]*\s*(?:/\s*\d[\d.,]*)?\s*%?"
        conclusion_re = re.compile(
            r"(?P<lhs>(?:إذن|ومنه|النتيجة|الجواب|فإن)[^=\n]{0,90}=\s*)(?P<rhs>" + num_re + r")"
        )
        assert conclusion_re.search("الاحتمال = 14/165") is None


# ── 5. source-inspection: الإصلاح موصول في chat_with_agent قبل الكاروسيل ────────
class TestSourceWiring:
    def test_helpers_defined(self) -> None:
        assert "def _count_probability_confusion(" in CLIENT_SRC
        assert "def _detect_subpart_question(" in CLIENT_SRC
        assert "def _fmt_comb(" in CLIENT_SRC
        assert "def _build_probability_direct_explanation(" in CLIENT_SRC

    def test_escape_hatch_precedes_calculated_ui(self) -> None:
        # المخرج يقع قبل _build_calculated_ui (وإلا MODE_A يُنهي المسار أولاً).
        hatch_pos = CLIENT_SRC.index(
            "_build_probability_direct_explanation(question, history_messages)"
        )
        calc_pos = CLIENT_SRC.index(
            "_ui_event = self._build_calculated_ui(question, history_messages=history_messages)"
        )
        assert hatch_pos < calc_pos, "escape hatch must run BEFORE _build_calculated_ui"

    def test_escape_hatch_follows_indexed_preempt(self) -> None:
        # المخرج يقع بعد الاسترجاع المُفهرَس (طلب «اعطني التمرين» يُخدَم أولاً).
        # D-137: matcher متين على لفّ الأسطر (الاستدعاء متعدّد الأسطر بعد ruff).
        preempt_pos = CLIENT_SRC.find("if self._has_indexed_match(")
        hatch_pos = CLIENT_SRC.find("_subpart = self._detect_subpart_question(question)")
        assert preempt_pos != -1 and hatch_pos != -1
        assert preempt_pos < hatch_pos

    def test_escape_condition_subpart_or_confusion(self) -> None:
        # D-125: تطوّر الشرط ليشمل المفاهيمي — العداد + subpart لا يزالان فيه.
        # D-137: الشرط أصبح متعدّد الأسطر — نطابق بعد تطبيع المسافات.
        flat = " ".join(CLIENT_SRC.split())
        assert "or _subpart is not None or _confusion_count >= 2" in flat

    def test_direct_explanation_uses_history_none(self) -> None:
        # D-123 immunity: التحليل من المحتوى الرسمي بـ history=None.
        seg = CLIENT_SRC[CLIENT_SRC.index("def _build_probability_direct_explanation(") :]
        # D-163: نهاية slice = الدالة التالية داخل العقل المستخرَج (_build_probability_tree_props
        # بقيت في الـ client كبانية UI فلم تعد تلي هذه الدالة في السلسلة المضمومة).
        seg = seg[: seg.index("\n    async def _build_probability_computational_answer")]
        # D-137/D-191: الآلية انتقلت إلى المُحلّ الواحد. القاعدة الباقية: الشرح
        # المباشر يأخذ أرقامه من `exercise_context` — الذي يحمل مناعة D-123
        # (history=None) وحارس ISS-120 (أسئلة-فقط) وحارس الموضوع، مجتمعةً في مكان
        # واحد بدل ثلاث نسخ متفرّقة.
        assert "resolve_exercise_context(" in seg
        resolver = CLIENT_SRC[CLIENT_SRC.index("class ExerciseContextSkill") :]
        assert "ProbabilityInput(question=candidate_text, history=None)" in resolver
        assert "load_exercise_questions_only(" in resolver
        # D-266 (ISS-159): topic-safe صار بالمُسنَد الواحد. الحرفية القديمة
        # `canonical_id != "probability"` كانت تحرس **وجود** الحارس لا **عمله**:
        # سؤال الفيزياء يُرجِع `None` فيسقط الشرط عند ساقه الأولى ولا يُنفَّذ أبداً.
        assert "is_foreign_to_probability(question)" in resolver  # topic-safe

    def test_direct_explanation_returns_and_breaks_loop(self) -> None:
        # عند نجاح البثّ ⇒ assistant_final + return (كسر الكاروسيل).
        seg = CLIENT_SRC[CLIENT_SRC.index("_subpart = self._detect_subpart_question(question)") :]
        seg = seg[: seg.index("Generative UI Streaming")]
        assert "self._stream_markdown_typing(_direct)" in seg
        assert '{"type": "assistant_final", "payload": {"content": ""}}' in seg
        assert "return" in seg

    def test_no_bare_kayf_in_confusion_markers(self) -> None:
        # «كيف» المجرّدة ممنوعة من علامات الحيرة (تكسر «كيف افهم السؤال الأول»).
        seg = CLIENT_SRC[CLIENT_SRC.index("_PROBABILITY_CONFUSION_MARKERS") :]
        seg = seg[: seg.index("def _count_probability_confusion")]
        assert '"كيف"' not in seg and "'كيف'" not in seg
