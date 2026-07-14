from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

"""
ISS-121 (D-154) — نهاية «آلة تفريغ الحلول»: الكشف التدريجي + حارس تكرار محايد للحجب.

الكارثة الحيّة (screenshot + transcript، post-D-153):
1. «كيف» ⇒ `_build_symbolic_reveal` = الحل الكامل حتى «فاحتمال الحادثة A هو 14 من كل 165».
2. الإجابة الصحيحة ⇒ إعادة نفس التفريغ حرفياً — حارس D-142 كان يقارن المرشَّح (بأرقام)
   مع النسخة المحفوظة (المحجوبة بـ«؟» عبر D-113) فيَعمى؛ ومسار التصعيد الوحيد كان reveal
   فيبثّ المكرَّر كما هو.
3. الصيغ ASCII (`C(5,3) = (5×4×3)/(3×2×1) = 10`) تتبعثر بالـ bidi داخل RTL.
"""

from app.infrastructure.clients.orchestrator.tutor_sources import read_tutor_source
from app.infrastructure.clients.orchestrator_client import OrchestratorClient
from app.services.skills.dialogue_manager_skill import near_duplicate

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _combo() -> SimpleNamespace:
    return SimpleNamespace(
        n=11,
        k=3,
        total_combinations=165,
        same_group_favorable=14,
        groups=[
            SimpleNamespace(label="كرة حمراء", count=4, is_possible=True, favorable_combinations=4),
            SimpleNamespace(
                label="كرة بيضاء", count=2, is_possible=False, favorable_combinations=0
            ),
            SimpleNamespace(
                label="كرة خضراء", count=5, is_possible=True, favorable_combinations=10
            ),
        ],
    )


class TestLatexFmtComb:
    """Track 3: `_fmt_comb` ⇒ LaTeX (LTR-معزول، يقتل بعثرة bidi، ناجٍ من الحجب)."""

    def test_latex_form(self):
        out = OrchestratorClient._fmt_comb(4, 3, 4)
        assert out.startswith("$") and out.endswith("$")
        assert "C_{4}^{3}" in out and "\\dfrac" in out and "\\times" in out
        assert "(4×3×2)" not in out  # الصيغة ASCII القديمة (تتبعثر bidi) ذهبت

    def test_degenerate_form_latex(self):
        out = OrchestratorClient._fmt_comb(2, 3, 0)
        assert out == "$C_{2}^{3} = 0$"

    def test_survives_redaction(self):
        from app.services.skills.answer_redaction_skill import redact_final_answers

        out = OrchestratorClient._fmt_comb(11, 3, 165)
        redacted, _ = redact_final_answers(out, 5)
        assert "C_{11}^{3}" in redacted  # البنية LaTeX تَنجو (لا نمط C(...)=)


class TestZeroFinalAnswer:
    """Track 1: صفر كشف للنتيجة النهائية (roadmap §7) — الذيول أسئلة توليد."""

    def test_reveal_ends_with_generation_question(self, monkeypatch):
        monkeypatch.setattr(
            OrchestratorClient,
            "_load_canonical_combinations",
            classmethod(lambda *_args, **_kw: _combo()),
        )
        text = OrchestratorClient._build_symbolic_reveal("كيف", None)
        assert text is not None
        assert "من كل 165" not in text and "14/165" not in text
        assert "بنفسك" in text
        assert text.rstrip().endswith("؟")

    def test_symbolic_steps_end_with_questions(self):
        num = OrchestratorClient._build_symbolic_step(_combo(), None)
        ratio = OrchestratorClient._build_symbolic_step(_combo(), "ratio")
        assert num.rstrip().endswith("؟") and ratio.rstrip().endswith("؟")
        assert "من كل" not in num and "من كل" not in ratio

    def test_direct_explanation_tails_are_generative(self):
        src = read_tutor_source()
        # الذيول القديمة الكاشفة ذهبت
        assert "فاحتمال الحادثة A هو {same} من كل {total}." not in src
        assert 'f"4) الاحتمال = {same}/{total}."' not in src
        assert 'f"وبذلك يكون الاحتمال {same}/{total}."' not in src

    def test_procedure_routes_to_ladder_not_reveal(self):
        src = read_tutor_source()
        # فرع procedure في كتلة حالة الفهم يستدعي خطوة السُّلّم لا التفريغ.
        block = src.split("else:  # procedure — ISS-121 (D-154): سُلّم لا تفريغ", 1)
        assert len(block) == 2, "procedure ladder branch missing"
        # ISS-122 (D-155): probe التشخيص أولاً ثم الخطوة المحسوبة — النافذة تتّسع لهما.
        tail = block[1][:1300]
        assert "_build_diagnostic_probe(_proc_combo)" in tail
        assert "_build_symbolic_step(_proc_combo, None)" in tail
        assert tail.index("_build_diagnostic_probe(_proc_combo)") < tail.index(
            "_build_symbolic_step(_proc_combo, None)"
        )
        # لا استدعاء فعلي للتفريغ (ذكره في التعليق التوثيقي مسموح).
        assert "self._build_symbolic_reveal(" not in tail


class TestRedactionNeutralDedup:
    """Track 2: التطبيع محايد لتحويل الحجب — المحفوظ (؟) ≡ المبثوث (أرقام)."""

    def test_norm_for_dedup_neutralizes_redaction(self):
        full = "نجمع الحالات الممكنة فقط: 4 + 10 = 14"
        masked = "نجمع الحالات الممكنة فقط: 4 + 10 = ؟"
        assert OrchestratorClient._norm_for_dedup(full) == OrchestratorClient._norm_for_dedup(
            masked
        )

    def test_recently_emitted_sees_redacted_history(self):
        candidate = "فضاء العينة: $C_{11}^{3} = 165$ نجمعها: $4 + 10 = 14$"
        redacted_saved = "فضاء العينة: $C_{11}^{3} = ?$ نجمعها: $4 + 10 = ?$"
        history = [{"role": "assistant", "content": redacted_saved}]
        assert OrchestratorClient._recently_emitted(candidate, history) is True

    def test_near_duplicate_skill_neutral_too(self):
        assert near_duplicate("النتيجة = 14 من 165", "النتيجة = ؟ من ؟") is True


class TestNeverEmitDupChain:
    """Track 2: سلسلة «ممنوع بثّ مكرَّر» — بدائل السُّلّم موجودة في المسارين."""

    def _src(self) -> str:
        return read_tutor_source()

    def test_socratic_evaluation_has_alternatives_ladder(self):
        # ISS-122 (D-155): البدائل صارت واعية بالسؤال المعلّق (_first/_second من
        # _pending) والإنقاذ الكامل (reveal) **أخيراً** — كان أول البدائل فيعيد المعروض.
        src = self._src()
        seg = src.split("def _is_dup(t: str) -> bool:", 1)
        assert len(seg) == 2, "no-dup chain missing from _stream_socratic_evaluation"
        tail = seg[1][:1900]
        assert '("ratio", "numerator") if _pending == "denominator"' in tail
        assert "_build_symbolic_step(combo, _first" in tail
        assert "_build_symbolic_step(combo, _second" in tail
        assert "جرّب بنفسك: ركّب البسط" in tail
        assert tail.index("_build_symbolic_reveal") > tail.index("جرّب بنفسك: ركّب البسط")

    def test_understanding_state_guard_has_ladder(self):
        src = self._src()
        seg = src.split("def _d153_dup(t: str) -> bool:", 1)
        assert len(seg) == 2, "understanding-state ladder guard missing"
        tail = seg[1][:2900]
        assert "_build_symbolic_step(_lad_combo, _lf)" in tail
        assert "_build_symbolic_step(_lad_combo, _ls)" in tail
        # ISS-122 (D-155): الإنقاذ الكامل آخر البدائل.
        assert tail.index("_build_symbolic_reveal") > tail.index("جرّب بنفسك: ركّب البسط")

    def test_distinct_progressive_texts(self):
        combo = _combo()
        num = OrchestratorClient._build_symbolic_step(combo, None)
        ratio = OrchestratorClient._build_symbolic_step(combo, "ratio")
        assert OrchestratorClient._norm_for_dedup(num) != OrchestratorClient._norm_for_dedup(ratio)
