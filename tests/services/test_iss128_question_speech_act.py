from __future__ import annotations

"""
ISS-128 (D-162) — «السؤال ليس إجابة»: بوّابة الفعل الكلامي + تصحيح السؤال المعلّق + التوافيق.

الكارثة الحيّة (transcript BAC-2024، post-D-161): الطالب سأل سؤالاً مفاهيمياً
«**ماذا نسمي** حساب 4 و 10 لم افهمها؟» (يطلب **اسم** العملية = التوافيق C(n,k))،
فردّ النظام «**إجابتك في الطريق الصحيح** —» وكأنها إجابة صحيحة، ثم **كشف جواب
سؤاله المعلّق بنفسه** (C(11,3)=165) وتقدّم للنسبة — تجاهل تام للسؤال.

الجذور الأربعة:
1. `_verify_numeric_answer` بلا أي حارس استفهامي — سؤال يحمل أرقاماً = إجابة.
2. خطوة البسط خزّنت `new_pending="numerator"` بينما سؤالها يسأل عن **المقام** ⇒
   `favs <= nums` ({4,10} ⊆ {4,10}) أطلق `step_correct` زائفاً.
3. نية التسمية («نسمي/ما اسم») عمياء في كل الطبقات + لا مفهوم `combinations`.
4. `_cognitive_turn` يسبق كل البوّابات المفاهيمية — لا هروب.

الإصلاح (D-162): `_is_question_not_answer` (أول `_verify_numeric_answer` + بوّابة
قبل S1) + pending = بؤرة السؤال المطروح فعلاً + مُجيب التسمية الحتمي (data-driven
من combo — يعمل لملايير التمارين) + مفهوم `combinations` في السجلّ + تكافؤ port
الخدمة المصغرة (Track 2A — بوّابة split-brain).
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.infrastructure.clients.orchestrator_client import OrchestratorClient

_REPO_ROOT = Path(__file__).resolve().parents[2]

#: رسالة الكارثة الحرفية من transcript المالك.
_CATASTROPHE_Q = "ماذا نسمي حساب 4 و 10 لم افهمها؟"


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


def _other_combo() -> SimpleNamespace:
    """تركيبة تمرين مختلف تماماً (عقد ملايير التمارين — data-driven لا أرقام مُصلَّبة)."""
    return SimpleNamespace(
        n=9,
        k=2,
        total_combinations=36,
        same_group_favorable=13,
        groups=[
            SimpleNamespace(
                color="red", label="كرة حمراء", count=3, is_possible=True, favorable_combinations=3
            ),
            SimpleNamespace(
                color="green",
                label="كرة خضراء",
                count=5,
                is_possible=True,
                favorable_combinations=10,
            ),
            SimpleNamespace(
                color="white",
                label="كرة بيضاء",
                count=1,
                is_possible=False,
                favorable_combinations=0,
            ),
        ],
    )


def _client_src() -> str:
    # D-168: المصدر المُركَّب عبر manifest D-164 (يشمل client + brain + كل الـ mixins)
    # — يقتل آخر concatenation يدوي من عصر ما قبل المانيفست.
    from app.infrastructure.clients.orchestrator.tutor_sources import read_tutor_source

    return read_tutor_source()


def _port_src() -> str:
    return (
        _REPO_ROOT
        / "microservices"
        / "orchestrator_service"
        / "src"
        / "services"
        / "overmind"
        / "probability_tutor.py"
    ).read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# 1) SOURCE GUARDS (deps-free — القفل البنيوي الذي يمنع عودة الكارثة على أي refactor)
# ─────────────────────────────────────────────────────────────────────────────
class TestSourceGuards:
    def test_verifier_rejects_questions_first(self):
        """RC-1: الحارس الاستفهامي أول `_verify_numeric_answer` — السؤال ليس إجابة أبداً."""
        src = _client_src()
        i = src.index("def _verify_numeric_answer(")
        body = src[i : src.index("\n    @", i)]
        assert "cls._is_question_not_answer(answer)" in body

    def test_pending_is_the_question_actually_asked(self):
        """RC-2: خطوة البسط تسأل عن المقام ⇒ pending="denominator" لا اسم الخطوة."""
        src = _client_src()
        i = src.index("def _cognitive_turn(")
        body = src[i : src.index("def _cognitive_turn_event_b(")]
        assert '"denominator" if step == "numerator"' in body

    def test_naming_resolver_wired_before_s2(self):
        """RC-3: مُجيب التسمية الحتمي قبل التحقّق الرقمي S2 داخل _cognitive_turn."""
        src = _client_src()
        i = src.index("def _cognitive_turn(")
        body = src[i : src.index("def _cognitive_turn_event_b(")]
        naming_at = body.index("_detect_naming_question(question, combo)")
        s2_at = body.index("_numeric = cls._verify_numeric_answer(")
        assert naming_at < s2_at

    def test_mid_dialogue_question_escapes_blind_ladder(self):
        """RC-4: السؤال وسط الحوار يهرب من سُلّم S1 (أسئلة كيف/كيفاش تبقى للسلسلة التعليمية)."""
        src = _client_src()
        i = src.index("def _cognitive_turn(")
        body = src[i : src.index("def _cognitive_turn_event_b(")]
        assert 'if _is_q and not _qg.startswith(("كيف", "كيفاش")):' in body

    def test_hal_stays_an_answer(self):
        """D-155 الثابتة: «هل» ليست في بادئات الأسئلة — «هل هي 14 من 165» إجابة."""
        src = _client_src()
        i = src.index("_QUESTION_OPENERS_NOT_ANSWERS: tuple[str, ...] = (")
        seg = src[i : src.index(")", i)]
        assert '"هل"' not in seg
        assert '"ماذا"' in seg  # التوسيع D-162

    def test_combinations_registered_in_property_registry(self):
        """RC-3: مفهوم التوافيق مدخل data في السجلّ (D-131 — لا فرع كود)."""
        sps = (_REPO_ROOT / "app" / "services" / "skills" / "semantic_property_skill.py").read_text(
            encoding="utf-8"
        )
        assert '"combinations": PropertySpec(' in sps
        assert "ماذا نسمي" in sps  # نية التسمية في _DEFINITIONAL_MARKERS

    def test_split_brain_parity_port_has_the_contracts(self):
        """Track 2A: عقود D-162 موجودة في port الخدمة المصغرة (العقلان لا يفترقان)."""
        port = _port_src()
        for marker in (
            "def is_question_not_answer(",
            "def detect_naming_question(",
            "def build_naming_answer(",
            "NAMING_MARKERS",
            "QUESTION_OPENERS_NOT_ANSWERS",
        ):
            assert marker in port, f"orchestrator port missing {marker}"


# ─────────────────────────────────────────────────────────────────────────────
# 2) بوّابة الفعل الكلامي — مصفوفة الحالات
# ─────────────────────────────────────────────────────────────────────────────
class TestSpeechActGate:
    @pytest.mark.parametrize(
        "message",
        [
            _CATASTROPHE_Q,
            "لماذا نجمع 4 و 10؟",
            "ما هو البسط",
            "ماذا يعني هذا الحساب",
            "متى يكون الجداء فردياً؟",
            "و ماذا نسمي هذا الحساب",  # واو العطف لا تحجب البادئة
            "ما اسم هذه العملية",
            "كيف حسبنا 4",  # سؤال — يُرفض من التحقّق الرقمي (لكن يبقى لسلسلة F2)
        ],
    )
    def test_questions_detected(self, message):
        assert OrchestratorClient._is_question_not_answer(message) is True

    @pytest.mark.parametrize(
        "message",
        [
            "هل هي 14 من 165",  # D-155: «هل» إجابة تطلب تأكيداً
            "14 على 165",
            "165",
            "نفس الشئ مع 11",
            "الحمراء و الخضراء فقط",
            "التوافيق",  # اسم مجرّد بلا نية تسمية استفهامية... يحوي marker؟ لا («توافيق» ليست في NAMING)
        ],
    )
    def test_answers_not_questions(self, message):
        assert OrchestratorClient._is_question_not_answer(message) is False


# ─────────────────────────────────────────────────────────────────────────────
# 3) التحقّق الرقمي — الكارثة مستحيلة + صفر انحدار D-155
# ─────────────────────────────────────────────────────────────────────────────
class TestNumericVerification:
    def test_catastrophe_question_never_step_correct(self):
        """الكارثة الحرفية: حتى مع pending الخاطئ القديم ⇒ None (لا اعتراف زائف)."""
        for pending in (None, "numerator", "denominator", "ratio"):
            assert (
                OrchestratorClient._verify_numeric_answer(_CATASTROPHE_Q, _combo(), pending) is None
            )

    @pytest.mark.parametrize(
        "answer, pending, expected",
        [
            ("14 على 165", "ratio", "final_ratio"),
            ("هل هي 14 من 165", "ratio", "final_ratio"),  # «هل» تبقى إجابة (D-155)
            ("165", "denominator", "step_correct"),
            ("نفس الشئ مع 11", "denominator", "direction"),
            ("4 و 10", "numerator", "step_correct"),  # قفزة مباشرة بعد probe — تبقى مُعترَفة
        ],
    )
    def test_d155_regressions_hold(self, answer, pending, expected):
        assert OrchestratorClient._verify_numeric_answer(answer, _combo(), pending) == expected

    def test_pending_denominator_rejects_numerator_values(self):
        """RC-2 مُصحَّح: بعد خطوة البسط pending=denominator ⇒ {4,10} لا تُعترف."""
        assert OrchestratorClient._verify_numeric_answer("4 و 10", _combo(), "denominator") is None


# ─────────────────────────────────────────────────────────────────────────────
# 4) مُجيب التسمية — data-driven (عقد ملايير التمارين)
# ─────────────────────────────────────────────────────────────────────────────
class TestNamingResolver:
    def test_detects_catastrophe_question(self):
        assert OrchestratorClient._detect_naming_question(_CATASTROPHE_Q, _combo()) is True

    def test_numbers_must_match_combo_values(self):
        """أرقام لا تنتمي لقيم التمرين ⇒ ليست سؤال تسمية عن خطواته."""
        assert OrchestratorClient._detect_naming_question("ماذا نسمي 7", _combo()) is False

    def test_works_for_any_exercise_combo(self):
        """data-driven: تركيبة تمرين مختلف تماماً (3/10/36) — نفس المنطق يعمل."""
        assert (
            OrchestratorClient._detect_naming_question("ماذا نسمي حساب 3 و 10", _other_combo())
            is True
        )
        # قيم تمرين BAC-2024 (4) ليست من قيم التمرين الآخر... 4 ليست في {9,2,36,13,3,10,5,1}
        assert (
            OrchestratorClient._detect_naming_question("ماذا نسمي حساب 4", _other_combo()) is False
        )

    def test_no_explain_marker_needed(self):
        """«كيف حسبنا 4» ليست تسمية (لها F2)؛ التسمية تتطلب marker تسمية."""
        assert OrchestratorClient._detect_naming_question("كيف حسبنا 4", _combo()) is False

    def test_answer_names_the_concept_and_reasks_pending(self):
        text = OrchestratorClient._build_naming_answer(_combo(), "denominator")
        assert text is not None
        assert "التوافيق" in text  # يُجيب بالاسم
        assert "إجابتك في الطريق الصحيح" not in text  # لا اعتراف زائف
        assert "165" not in text  # لا كشف لجواب السؤال المعلّق
        assert "كم عدد كل الطرق الممكنة" in text  # إعادة طرح السؤال المعلّق
        # نصّ إعادة السؤال يطابق قوالب الخطوات ⇒ pending يبقى مشتقاً صحيحاً من التاريخ.
        assert any(m in text for m, _f in OrchestratorClient._STEP_QUESTION_MARKERS)

    def test_answer_survives_redaction(self):
        """يَنجو من حجب D-113 بنيوياً (نمط _fmt_comb — D-154)."""
        from app.services.skills.answer_redaction_skill import redact_final_answers

        text = OrchestratorClient._build_naming_answer(_combo(), "denominator")
        redacted, hits = redact_final_answers(text)
        assert hits == 0
        assert redacted == text


# ─────────────────────────────────────────────────────────────────────────────
# 5) BEHAVIORAL — إعادة transcript الكارثة الحرفي عبر _cognitive_turn الحقيقي
# ─────────────────────────────────────────────────────────────────────────────
class TestCatastropheTranscriptReplay:
    def _skip_if_no_kb(self):
        if (
            OrchestratorClient._load_canonical_combinations("اعطني تمرين الاحتمالات 2024", None)
            is None
        ):
            pytest.skip("canonical combo unavailable (no knowledge_base in this env)")

    def _run_transcript(self) -> tuple[list[str], dict]:
        tutor_state: dict = {"kc_progress": {}, "turn_count": 0}
        history = [
            {"role": "user", "content": "اعطني تمرين الاحتمالات 2024"},
            {
                "role": "assistant",
                "content": (
                    "يحتوي كيس على 11 كرة: كرتان بيضاوان، أربع كرات حمراء، "
                    "خمس كرات خضراء. نسحب 3 كرات دفعة واحدة."
                ),
            },
        ]
        outs: list[str] = []

        def turn(q: str) -> str | None:
            text, delta = OrchestratorClient._cognitive_turn(q, history, tutor_state, None)
            if text:
                history.append({"role": "user", "content": q})
                history.append({"role": "assistant", "content": text})
                kcp = tutor_state.setdefault("kc_progress", {})
                for k, v in (delta or {}).items():
                    kcp[k] = v
                outs.append(text)
            tutor_state["turn_count"] = int(tutor_state.get("turn_count") or 0) + 1
            tutor_state.pop("kc_progress_delta", None)
            return text

        # D-165 (ISS-129): سؤال غير-كيف («ما هي قواعد...») لم يعد يُختطف بالـ probe —
        # يهرب لطبقات الإجابة (كما يفعل الـ port منذ D-162). طلب المساعدة الإجرائي
        # («كيف») هو ما يستحق «التشخيص قبل الشرح» (D-155).
        turn("كيف افهم قواعد هذا التمرين؟")  # T2 → probe
        turn("الحمراء و الخضراء فقط")  # T3 → خطوة البسط
        turn(_CATASTROPHE_Q)  # T4 → التسمية (الكارثة)
        turn("165")  # T5 → اعتراف + خطوة النسبة
        turn("14 على 165")  # T6 → أحسنت + الحادثة B
        return outs, tutor_state

    def test_full_transcript_kills_the_catastrophe(self):
        self._skip_if_no_kb()
        outs, tutor_state = self._run_transcript()
        assert len(outs) == 5, f"expected 5 tutor turns, got {len(outs)}"
        t2, t3, t4, t5, t6 = outs
        # T2: التشخيص قبل الشرح (D-155 — لا انحدار).
        assert "أيّ الألوان" in t2
        # T3: خطوة البسط + pending الصحيح = المقام (RC-2 مُصحَّح).
        assert "الحالات الملائمة" in t3
        # T4 — قلب الكارثة: يُجيب بالاسم، لا اعتراف زائف، لا كشف 165.
        assert "التوافيق" in t4
        assert "إجابتك في الطريق الصحيح" not in t4
        assert "165" not in t4
        assert "كم عدد كل الطرق الممكنة" in t4  # إعادة طرح السؤال المعلّق
        # pending بعد T4 يبقى denominator (لا تقدّم زائف).
        pend = tutor_state["kc_progress"].get("_pending") or {}
        assert pend.get("step_key") != "numerator"
        # T5: «165» تُعترف step_correct (الحوار يستأنف بسلاسة بعد التسمية).
        assert "165" in t5 and "الاحتمال" in t5
        # T6: النسبة النهائية ⇒ أحسنت + الانتقال للحادثة B (صفر انحدار D-155/D-158).
        assert "أحسنت" in t6 and "الحادثة B" in t6

    def test_pending_after_numerator_step_is_denominator(self):
        self._skip_if_no_kb()
        tutor_state: dict = {
            "kc_progress": {
                "prob_event_a": {
                    "state": "explained",
                    "representations_delivered": ["diagnostic_probe"],
                }
            },
            "turn_count": 1,
        }
        history = [{"role": "user", "content": "اعطني تمرين الاحتمالات 2024"}]
        text, delta = OrchestratorClient._cognitive_turn(
            "الحمراء و الخضراء فقط", history, tutor_state, None
        )
        assert text is not None and "الحالات الملائمة" in text
        pend = (delta or {}).get("_pending") or {}
        assert pend.get("step_key") == "denominator"


# ─────────────────────────────────────────────────────────────────────────────
# 6) port الخدمة المصغرة — نفس العقود (split-brain parity، سلوكياً)
# ─────────────────────────────────────────────────────────────────────────────
class TestOrchestratorPortParity:
    def _mod(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "prob_tutor_port",
            _REPO_ROOT
            / "microservices"
            / "orchestrator_service"
            / "src"
            / "services"
            / "overmind"
            / "probability_tutor.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    _EXERCISE = (
        "التمرين الأول — الاحتمالات\n"
        "يحتوي كيس على 11 كرة: كرتان بيضاوان مرقمتان بـ 1، 3، "
        "أربع كرات حمراء مرقمة بـ 0، 1، 1، 3، خمس كرات خضراء مرقمة بـ 0، 1، 1، 3، 4.\n"
        "نسحب عشوائياً 3 كرات دفعة واحدة. الحادثة A: الحصول على 3 كرات من نفس اللون."
    )

    def test_port_naming_question_answered_by_name(self):
        mod = self._mod()
        comp = mod.parse_composition(self._EXERCISE)
        assert comp is not None and comp["total"] == 165
        assert mod.is_question_not_answer(_CATASTROPHE_Q) is True
        assert mod.detect_naming_question(_CATASTROPHE_Q, comp) is True
        text = mod.deterministic_turn(_CATASTROPHE_Q, self._EXERCISE, history=[])
        assert text is not None and "التوافيق" in text
        assert "165" not in text

    def test_port_non_procedural_question_falls_to_llm(self):
        mod = self._mod()
        assert mod.deterministic_turn("لماذا نطرح هذا السؤال؟", self._EXERCISE, history=[]) is None

    def test_port_hal_and_answers_still_tutoring(self):
        mod = self._mod()
        assert mod.is_question_not_answer("هل هي 14 من 165") is False
        # «كيف أحل» الإجرائية تبقى للسُّلّم (لا تسقط للـ LLM).
        text = mod.deterministic_turn("كيف أحل هذا التمرين؟", self._EXERCISE, history=[])
        assert text is not None
