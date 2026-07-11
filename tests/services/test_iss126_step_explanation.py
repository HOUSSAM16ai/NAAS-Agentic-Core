from __future__ import annotations

"""
ISS-126 (D-160) — قتل كارثة تدريس الاحتمالات من الجذر: «اشرح اشتقاق هذه الخطوة».

الكارثة الحيّة (transcript BAC-2024، post-D-159): الطالب يسأل «كيف حسبنا 4» (كيف
اشتُقّت C(4,3)=4) ثلاث مرّات ويتلقّى **النصّ نفسه حرفياً** («…ركّب الاحتمال بنفسك…
فما قيمة P(A)؟»). المرّة الـ47 لنفس نمط الفشل عبر D-113→D-159.

الجذر (ثلاثة إخفاقات مترابطة):
1. **نيّة مفقودة**: `_detect_subpart_question` يربط الألوان و14/165 فقط — لا القيم
   الملائمة 4/10 ⇒ «كيف حسبنا 4» يسقط للإنقاذ النهائي المكرَّر.
2. **تكرار غير محروس**: الإنقاذ النهائي في `_cognitive_turn` كان يُرجَع بلا `_recently_emitted`.
3. **كشف نصفي عبثي**: يُظهر 14 و165 ثم يرفض التركيب ويدور في حلقة «ركّب بنفسك».

الإصلاح (D-160):
- F1: حارس تكرار شامل — الإنقاذ النهائي وكل فرع يمرّ عبر `_recently_emitted`.
- F2: `_detect_step_explanation(question, combo)` **data-driven** يربط أرقام السؤال بقيم
  combo (يعمل لأي تمرين، لا 4/10 مُصلَّبة) + `forced_subpart` في
  `_build_probability_direct_explanation` (يُعيد استخدام كوده التعليمي).
- F3: الطالب العالق يتعلّم اشتقاق أصغر جزئية لم تُعرَض — لا كشف P(A) النهائي (M6/M8).
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.infrastructure.clients.orchestrator_client import OrchestratorClient

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _combo() -> SimpleNamespace:
    """تركيبة تمرين الاحتمالات BAC-2024 الرسمية (11 كرة، سحب 3، نفس اللون)."""
    return SimpleNamespace(
        n=11,
        k=3,
        total_combinations=165,
        same_group_favorable=14,
        groups=[
            SimpleNamespace(
                color="red", label="كرة حمراء", count=4, is_possible=True, favorable_combinations=4
            ),
            SimpleNamespace(
                color="white",
                label="كرة بيضاء",
                count=2,
                is_possible=False,
                favorable_combinations=0,
            ),
            SimpleNamespace(
                color="green",
                label="كرة خضراء",
                count=5,
                is_possible=True,
                favorable_combinations=10,
            ),
        ],
    )


def _client_src() -> str:
    # D-163: عقل الاحتمالات استُخرج للوحدة المستقلة — نضمّ الاثنين ليصمد أي pin.
    return (
        _REPO_ROOT / "app" / "infrastructure" / "clients" / "orchestrator_client.py"
    ).read_text(encoding="utf-8") + (
        _REPO_ROOT / "app" / "services" / "skills" / "probability_tutor_brain.py"
    ).read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# 1) SOURCE GUARDS (deps-free — القفل البنيوي الذي يمنع عودة الكارثة على أي refactor)
# ─────────────────────────────────────────────────────────────────────────────
class TestSourceGuards:
    def test_terminal_reveal_is_dedup_guarded(self):
        """F1: الإنقاذ النهائي في _cognitive_turn لم يعد يُرجَع بلا حارس تكرار."""
        src = _client_src()
        i = src.index("def _cognitive_turn(")
        j = src.index("def _cognitive_turn_event_b(")
        body = src[i:j]
        # يجب أن يُختبَر ناتج _build_symbolic_reveal ضد _recently_emitted قبل بثّه.
        assert "_build_symbolic_reveal(" in body
        assert "if text and not cls._recently_emitted(text, history_messages):" in body

    def test_step_explanation_branch_present(self):
        """F2: فرع «اشرح اشتقاق هذه الخطوة» موصول في _cognitive_turn قبل حلقة S1."""
        src = _client_src()
        i = src.index("def _cognitive_turn(")
        j = src.index("def _cognitive_turn_event_b(")
        body = src[i:j]
        assert "_detect_step_explanation(question, combo)" in body
        assert "forced_subpart=_explain_part" in body

    def test_forced_subpart_param_added(self):
        """F2: forced_subpart يُعيد استخدام الكود التعليمي القائم بلا كود جديد."""
        src = _client_src()
        assert "forced_subpart: str | None = None," in src
        assert "subpart = forced_subpart or cls._detect_subpart_question(question)" in src

    def test_stuck_student_teaches_not_loops(self):
        """F3: عند تكرار الإنقاذ ⇒ يُعلّم جزئية ملموسة لم تُعرَض (لا كشف P(A))."""
        src = _client_src()
        i = src.index("def _cognitive_turn(")
        j = src.index("def _cognitive_turn_event_b(")
        body = src[i:j]
        # حلقة تعليم جزئية ملموسة (red/green/white/total/sum) بعد الإنقاذ المكرَّر.
        assert 'for _part in ("red", "green", "white", "total", "sum"):' in body

    def test_escape_hatch_honors_step_explanation(self):
        """F4: الكتلة القديمة (defense-in-depth) تُكرّم نفس النيّة بنفس الكاشف."""
        src = _client_src()
        assert "_sc_part = (" in src
        assert "self._detect_step_explanation(question, _sc_combo)" in src


# ─────────────────────────────────────────────────────────────────────────────
# 2) DETECTOR — data-driven، marker-gated (يعمل بأي تمرين، لا 4/10 مُصلَّبة)
# ─────────────────────────────────────────────────────────────────────────────
class TestStepExplanationDetector:
    @pytest.mark.parametrize(
        "question, expected",
        [
            ("كيف حسبنا 4", "red"),  # 4 = عدد/تأليفات الحمراء
            ("اشرح كيف وصلنا لـ 10", "green"),  # 10 = تأليفات الخضراء
            ("كيف حسبنا 14", "sum"),  # 14 = مجموع الملائمة
            ("من أين جاءت 165", "total"),  # 165 = فضاء العينة
            ("وضّح كيف نحسب تأليفات الحمراء", "red"),  # كلمة لونية
            ("اشرح كيف حسبنا 5", "green"),  # 5 = عدد الخضراء (count)
        ],
    )
    def test_maps_value_or_color_to_part(self, question, expected):
        assert OrchestratorClient._detect_step_explanation(question, _combo()) == expected

    @pytest.mark.parametrize(
        "question",
        [
            "14 على 165",  # إجابة رقمية — لا علامة شرح ⇒ تبقى لتحقّق S2 (لا اختطاف)
            "هي 14 من 165",  # إجابة نهائية
            "اعطني تمرين",  # طلب محتوى
            "لم أفهم",  # حيرة بلا رقم/لون
            "كيف نحسب حادثة",  # علامة شرح لكن بلا رقم/لون ⇒ يبقى للتشخيص S3
        ],
    )
    def test_non_explanation_returns_none(self, question):
        assert OrchestratorClient._detect_step_explanation(question, _combo()) is None


# ─────────────────────────────────────────────────────────────────────────────
# 3) BEHAVIORAL — عبر الكود الحقيقي (يقرأ knowledge_base في CI؛ يُتخطّى محلياً بلا deps)
# ─────────────────────────────────────────────────────────────────────────────
class TestForcedSubpartTeaching:
    def _combo_or_skip(self):
        combo = OrchestratorClient._load_canonical_combinations("اعطني تمرين الاحتمالات 2024", None)
        if combo is None:  # knowledge_base غير متاح ⇒ يُتحقَّق في CI
            pytest.skip("canonical combo unavailable (no knowledge_base in this env)")
        return combo

    def test_forced_red_teaches_derivation_not_reveal(self):
        self._combo_or_skip()
        text = OrchestratorClient._build_probability_direct_explanation(
            "كيف حسبنا 4", None, forced_subpart="red"
        )
        assert text is not None
        assert "تأليفات" in text  # يُعلّم اشتقاق التأليفة
        assert "C_{4}^{3}" in text  # صيغة LaTeX الناجية من حجب D-113
        # F3/M8: لا يكشف النسبة النهائية P(A)=14/165.
        assert "14/165" not in text
        assert "\\boxed" not in text

    def test_forced_green_teaches_green(self):
        self._combo_or_skip()
        text = OrchestratorClient._build_probability_direct_explanation(
            "اشرح كيف وصلنا لـ 10", None, forced_subpart="green"
        )
        assert text is not None
        assert "C_{5}^{3}" in text
        assert "14/165" not in text


class TestNoRepeatControlFlow:
    """الإثبات السلوكي: «كيف حسبنا 4» ×3 ⇒ صفر تكرار حرفي + أول ردّ يُعلّم الحمراء."""

    def _prob_history(self) -> list[dict[str, str]]:
        # history يُثبت سياق الاحتمالات + خطوات مُسلَّمة (numerator/ratio).
        return [
            {"role": "user", "content": "اعطني تمرين الاحتمالات 2024"},
            {"role": "assistant", "content": "كيس فيه 11 كرة: حمراء وخضراء وبيضاء، نسحب 3 كرات."},
            {
                "role": "assistant",
                "content": OrchestratorClient._build_symbolic_step(_combo(), None),
            },
            {
                "role": "assistant",
                "content": OrchestratorClient._build_symbolic_step(_combo(), "ratio"),
            },
        ]

    def test_three_asks_no_verbatim_repeat(self):
        if (
            OrchestratorClient._load_canonical_combinations("اعطني تمرين الاحتمالات 2024", None)
            is None
        ):
            pytest.skip("canonical combo unavailable (no knowledge_base in this env)")
        tutor_state = {
            "kc_progress": {
                "prob_event_a": {
                    "state": "explained",
                    "representations_delivered": ["diagnostic_probe", "numerator", "ratio"],
                }
            },
            "turn_count": 3,
        }
        history = self._prob_history()
        outs: list[str] = []
        for _ in range(3):
            text, delta = OrchestratorClient._cognitive_turn(
                "كيف حسبنا 4", history, tutor_state, None
            )
            outs.append(text or "")
            if text:
                history.append({"role": "assistant", "content": text})
            # حاكِ record_turn (دمج الدلتا + تقدّم الدور).
            kcp = tutor_state.setdefault("kc_progress", {})
            for k, v in (delta or {}).items():
                kcp[k] = v
            tutor_state["turn_count"] = int(tutor_state.get("turn_count") or 0) + 1
            tutor_state.pop("kc_progress_delta", None)

        non_empty = [o for o in outs if o]
        assert non_empty, "cognitive_turn produced no output for the probability turn"
        # أول ردّ يُعلّم اشتقاق الحمراء (الجواب الفعلي على «كيف حسبنا 4»).
        assert "تأليفات" in non_empty[0] and "C_{4}^{3}" in non_empty[0]
        # صفر تكرار حرفي عبر الأدوار الثلاثة (كانت كلها متطابقة قبل الإصلاح).
        assert len(set(non_empty)) == len(non_empty)
        # لا كشف للنسبة النهائية في أي دور.
        assert all("14/165" not in o for o in non_empty)

    def _skip_if_no_kb(self):
        if (
            OrchestratorClient._load_canonical_combinations("اعطني تمرين الاحتمالات 2024", None)
            is None
        ):
            pytest.skip("canonical combo unavailable (no knowledge_base in this env)")

    def test_explanation_request_beats_numeric_verification(self):
        """F2-قبل-S2: «اشرح كيف حسبنا 14» يُعلّم اشتقاق المجموع — لا يُعامَل كإجابة «14»."""
        self._skip_if_no_kb()
        tutor_state = {
            "kc_progress": {
                "prob_event_a": {
                    "state": "explained",
                    "representations_delivered": ["diagnostic_probe"],
                    "_pending": {"kc": "prob_event_a", "focus": "numerator"},
                },
                "_pending": {"kc": "prob_event_a", "focus": "numerator"},
            },
            "turn_count": 2,
        }
        history = [{"role": "user", "content": "اعطني تمرين الاحتمالات 2024"}]
        text, _ = OrchestratorClient._cognitive_turn(
            "اشرح كيف حسبنا 14", history, tutor_state, None
        )
        assert text is not None
        # يُعلّم كيف تكوّن 14 (لا «أحسنت» ولا سؤال الحادثة B — ليس إجابةً).
        assert "أحسنت" not in text
        assert "الحادثة B" not in text

    def test_bare_numeric_answer_still_verified(self):
        """F2-قبل-S2 لا يكسر التحقّق: «14 على 165» (بلا علامة) ⇒ S2 اعتراف + الحادثة B."""
        self._skip_if_no_kb()
        tutor_state = {
            "kc_progress": {
                "prob_event_a": {
                    "state": "explained",
                    "representations_delivered": ["diagnostic_probe", "numerator", "ratio"],
                    "_pending": {"kc": "prob_event_a", "focus": "ratio"},
                },
                "_pending": {"kc": "prob_event_a", "focus": "ratio"},
            },
            "turn_count": 4,
        }
        history = [{"role": "user", "content": "اعطني تمرين الاحتمالات 2024"}]
        text, _ = OrchestratorClient._cognitive_turn("14 على 165", history, tutor_state, None)
        assert text is not None
        assert "أحسنت" in text and "الحادثة B" in text
