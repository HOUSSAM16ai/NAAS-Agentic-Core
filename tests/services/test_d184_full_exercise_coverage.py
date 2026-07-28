"""D-184 — تغطية تمرين الاحتمالات كاملاً + إنهاء انحراف البؤرة السقراطية.

الكارثة (transcript حي، 2026-07-28):

    الطالب : «لماذا نضرب ثلاثة أرقام في بعضها»   (يسأل عن جداء أرقام الكرات — B وC)
    النظام : شرح 11×10×9 (عدّ الترتيبات) ثم ذيّله باعتراف أنّ هذا «يختلف عن جداء
             أرقام الكرات في الحوادث B وC وD»
    الطالب : «لم أفهم»
    النظام : «أيّ الألوان يمكن أن تعطينا 3 كرات من نفس اللون؟»   ← موضوع ثالث
    الطالب : «كيف»
    النظام : 4 + 10 = 14 …                                      ← يواصل في A

ثلاثة مواضيع، وسؤال الطالب لم يُلمَس. العلل المُثبَتة:

١. `_detect_focus_step` لم يملك أي نمط لتكافؤ **جداء الأرقام** (الحادثتان B وC).
٢. غياب إشارة صريحة + حيرة ⇒ إعادة ضبط قسرية إلى `same_color_event`: «لم أفهم»
   (ومعناها «لم أفهم ما شرحتَه للتوّ») كانت تُترجَم «ارجع للحادثة A» — محرّك الانحراف.
٣. `same_color_event` مُحمَّل: أسئلة B/C كانت تُوجَّه إليه فيُسأل الطالب عن الألوان.
٤. `sequential_zero_product` بؤرة **معلّقة** (D-182 أضافها بلا خطوة مقابلة).
٥. الأخطر — X كان يُنمذَج على **أول لون** بينما التمرين يُعرّفه بعدد الكرات ذات
   الرقم الزوجي: توزيع مختلف كلياً يُعرَض على الطالب (خطأ رياضي لا انحراف تربوي).

الاختبارات تقرأ **الكود الحقيقي**: الخطوات من `_build_full_exercise_story` على
المحتوى الرسمي من `knowledge_base/`، والكاشف يُستخرَج من مصدره عبر `ast` (لا نسخة
يدوية تكذب مع الوقت). البوّابة البنيوية تمنع تكرار العلّة ٤ لأي بؤرة مستقبلية.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.services.capabilities.exercise_retrieval import (
    ExerciseRetrievalRequest,
    detect_exercise_retrieval,
    load_exercise_questions_only,
)
from app.services.skills.probability_skill import ProbabilityCalculatorSkill

REPO_ROOT = Path(__file__).resolve().parents[2]
PROBABILITY_UI = REPO_ROOT / "app/infrastructure/clients/orchestrator/probability_ui.py"


# ── أدوات: استخراج الكاشفات المتداخلة من مصدرها الحقيقي (بلا نسخة يدوية) ────────
def _extract_nested_function(name: str):
    """يُصرِّف دالةً متداخلة من مصدرها الفعلي — لا تُغلق على شيء فتعمل مستقلّة.

    البديل (نسخة مكتوبة يدوياً داخل الاختبار) يكذب صامتاً عند أي تعديل لاحق.
    """
    tree = ast.parse(PROBABILITY_UI.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            namespace: dict[str, object] = {}
            exec(compile(ast.Module([node], []), str(PROBABILITY_UI), "exec"), namespace)
            return namespace[name]
    raise AssertionError(f"{name} not found in {PROBABILITY_UI}")


def _focus_step_return_values() -> set[str]:
    """كل المُعرَّفات التي قد تُرجعها `_detect_focus_step` — من الشجرة النحوية."""
    tree = ast.parse(PROBABILITY_UI.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_detect_focus_step":
            return {
                sub.value.value
                for sub in ast.walk(node)
                if isinstance(sub, ast.Return)
                and isinstance(sub.value, ast.Constant)
                and isinstance(sub.value.value, str)
            }
    raise AssertionError("_detect_focus_step not found")


@pytest.fixture(scope="module")
def official_questions() -> str:
    """نصّ التمرين الرسمي **أسئلة-فقط** (مناعة ISS-120: لا نثر الحل النموذجي)."""
    decision = detect_exercise_retrieval(
        ExerciseRetrievalRequest(question="اعطني تمرين الاحتمالات 2024")
    )
    assert decision.recognized and decision.matched_entry, "الاسترجاع الرسمي انكسر"
    content = load_exercise_questions_only(decision.matched_entry)
    assert content, "المحتوى الرسمي فارغ"
    return content


@pytest.fixture(scope="module")
def story(official_questions: str):
    skill = ProbabilityCalculatorSkill
    comp_raw = skill._extract_count_entities(official_questions)
    built = skill._build_full_exercise_story(comp_raw, 11, official_questions)
    assert built is not None, "تعذّر بناء القصّة الشاملة للتمرين الرسمي"
    return built


def _step(story_obj, step_id: str):
    return next(s for s in story_obj.exercise_steps if s.step_id == step_id)


# ── ٠. البوّابة البنيوية: لا بؤرة معلّقة أبداً (تمنع تكرار العلّة ٤) ─────────────
class TestFocusStepIdIntegrity:
    def test_every_focus_id_maps_to_a_real_step(self, story) -> None:
        """كل مُعرَّف يُرجعه الكاشف يجب أن يقابل خطوةً موجودة فعلاً.

        هذه هي البوّابة التي كانت ستمنع علّة D-182 يوم وُلدت: `sequential_zero_product`
        كان يُرسَل إلى الواجهة كـ`focus_step_id` بينما لا خطوة تحمل هذا المعرّف.
        """
        produced = {s.step_id for s in story.exercise_steps}
        for focus_id in _focus_step_return_values():
            assert focus_id in produced, (
                f"بؤرة معلّقة: `_detect_focus_step` تُرجِع {focus_id!r} "
                f"ولا خطوة تحمله. الخطوات المُولَّدة: {sorted(produced)}"
            )

    def test_step_indices_are_contiguous(self, story) -> None:
        indices = [s.step_index for s in story.exercise_steps]
        assert indices == list(range(len(indices))), f"ترقيم الخطوات غير متّصل: {indices}"

    def test_full_exercise_is_covered(self, story) -> None:
        """التمرين له ٦ أجزاء — لا يجوز أن تبقى نصفها بلا تمثيل بصري."""
        produced = {s.step_id for s in story.exercise_steps}
        assert {
            "data",
            "sample_space",
            "same_color_event",
            "product_parity_event",
            "conditional_event",
            "random_variable",
            "sequential_zero_product",
        } <= produced


# ── ١. الحادثتان B وC — جداء الأرقام (الأرقام من المحرك الرمزي حصراً) ───────────
class TestProductParityEvent:
    def test_parity_counts_match_official_text(self, official_questions: str) -> None:
        parity = ProbabilityCalculatorSkill.number_parity_counts(official_questions)
        assert parity == {"odd": 8, "even": 3, "zero": 2, "total": 11}

    def test_parity_groups_preserve_colour_membership(self, official_questions: str) -> None:
        """D-184: بلا انتماء الأرقام لألوانها يستحيل حساب الاحتمال الشرطي."""
        assert ProbabilityCalculatorSkill.number_parity_groups(official_questions) == [
            [1, 3],
            [0, 1, 1, 3],
            [0, 1, 1, 3, 4],
        ]

    def test_probability_b_matches_the_official_answer(self, story) -> None:
        """نصّ التمرين يُصرّح P(B) = 56/165 — المحرك الحتمي يجب أن يوافقه بالضبط."""
        state = _step(story, "product_parity_event").numerical_state
        assert (state["p_num"], state["p_den"]) == (56, 165)

    def test_complement_event_c_is_derived(self, story) -> None:
        state = _step(story, "product_parity_event").numerical_state
        assert state["complement_favorable"] == 165 - 56

    def test_message_answers_why_before_asking(self, story) -> None:
        """«أجب عن لماذا ثم اسأل»: الرسالة تشرح سبب ضرب الأرقام، ثم تسأل سؤالاً واحداً."""
        step = _step(story, "product_parity_event")
        assert "فردياً" in step.pedagogical_message
        assert "كل" in step.pedagogical_message  # «كل عامل فيه فردياً»
        assert step.interactive["expected_index"] == 1
        assert "ألوان" not in step.pedagogical_message  # ليس عن الألوان


# ── ٢. الاحتمال الشرطي P_A(B) — الشرط يُغيّر الفضاء لا الحدث ────────────────────
class TestConditionalEvent:
    def test_conditional_uses_event_a_as_denominator(self, story) -> None:
        state = _step(story, "conditional_event").numerical_state
        assert (state["p_num"], state["p_den"]) == (2, 14), "P_A(B) = 2/14 = 1/7"

    def test_impossible_colour_is_pedagogical_not_zero(self, story) -> None:
        """البيضاء لا تكفي — رسالة تربوية لا «C(2,3)=0» مضلِّل (§0/D-116)."""
        groups = _step(story, "conditional_event").numerical_state["groups"]
        white = next(g for g in groups if "بيضاء" in str(g["label"]))
        assert white["is_possible"] is False
        assert "لا تكفي" in str(white["pedagogical_string"])


# ── ٣. المتغيّر العشوائي X — العلّة الخامسة (خطأ رياضي صريح) ────────────────────
class TestRandomVariableFollowsExerciseDefinition:
    def test_x_is_modelled_by_number_parity_not_colour(self, story) -> None:
        """التمرين: «X يمثل عدد الكرات التي تحمل رقماً زوجياً» — لا عدد البيضاء.

        قبل D-184 كان التوزيع [(0,84),(1,72),(2,9)] (عدد الكرات البيضاء) — متغيّر
        عشوائي **آخر** تماماً يُعرَض على الطالب.
        """
        state = _step(story, "random_variable").numerical_state
        assert state["focal_label"] == "رقم زوجي"
        assert [(d["value"], d["p_num"]) for d in state["distribution"]] == [
            (0, 56),
            (1, 84),
            (2, 24),
            (3, 1),
        ]

    def test_distribution_sums_to_one(self, story) -> None:
        state = _step(story, "random_variable").numerical_state
        assert sum(int(d["p_num"]) for d in state["distribution"]) == state["total"] == 165

    def test_expectation_and_tail_probability(self, story) -> None:
        state = _step(story, "random_variable").numerical_state
        assert (state["expectation_num"], state["expectation_den"]) == (135, 165)  # 9/11
        assert (state["p_gt1_num"], state["p_gt1_den"]) == (25, 165)  # 5/33


# ── ٤. الحادثة D — السحب على التوالي بدون إرجاع (الترتيب يهمّ) ──────────────────
class TestSequentialZeroProduct:
    def test_ordered_denominator_and_complement(self, story) -> None:
        state = _step(story, "sequential_zero_product").numerical_state
        assert state["p_den"] == 990, "11×10×9 — ترتيبات لا تأليفات"
        assert state["p_num"] == 990 - 504, "المتمّم: 990 − (9×8×7)"
        assert state["ordered"] is True


# ── ٥. توجيه البؤرة — الترانسكريبت الحقيقي + صفر انحدار على D-182/D-122 ────────
class TestFocusRouting:
    detect = staticmethod(_extract_nested_function("_detect_focus_step"))

    @pytest.mark.parametrize(
        ("question", "expected"),
        [
            ("الحصول على 3 كرات جداء أرقامها عدد فردي", "product_parity_event"),
            ("لماذا نضرب حاصل ضرب الأرقام", "product_parity_event"),
            ("احسب الاحتمال الشرطي P_A(B)", "conditional_event"),
            ("جداء أرقامها معدوم", "sequential_zero_product"),
            ("عدد الكرات التي تحمل رقما زوجيا", "random_variable"),
        ],
    )
    def test_new_routes(self, question: str, expected: str) -> None:
        assert self.detect(question) == expected

    def test_product_questions_no_longer_land_on_colours(self) -> None:
        """العلّة ٣: سؤال عن تكافؤ الجداء كان يُوجَّه لخطوة الألوان."""
        for question in ("جداء أرقامها عدد فردي", "P(B)", "P(C)"):
            assert self.detect(question) != "same_color_event", question

    @pytest.mark.parametrize(
        ("question", "expected"),
        [
            # D-182 — إشارات طريقة السحب المتتالي تبقى مقدَّمة على تكافؤ الجداء.
            ("لم أفهم لماذا نضرب ثلاثة أرقام في بعضهم تنازلياً؟", "sequential_zero_product"),
            ("لماذا نسحب على التوالي وبدون إرجاع", "sequential_zero_product"),
            ("لم أفهم دور الترتيب هنا", "sequential_zero_product"),
            # D-122/D-120 — لا تراجع.
            ("اشرح P(A)", "same_color_event"),
            ("ما هو E(X) والمتغير العشوائي", "random_variable"),
        ],
    )
    def test_no_regression(self, question: str, expected: str) -> None:
        assert self.detect(question) == expected

    def test_bare_confusion_yields_no_focus(self) -> None:
        """«لم أفهم» وحدها بلا إشارة ⇒ None، فتتكفّل البؤرة اللاصقة (لا إعادة ضبط)."""
        assert self.detect("لم أفهم") is None
        assert self.detect("كيف") is None


# ── ٦. البؤرة اللاصقة — العلّة الثانية (محرّك الانحراف) ─────────────────────────
class TestStickyFocusWiring:
    SRC = PROBABILITY_UI.read_text(encoding="utf-8")

    def test_recovery_helper_exists(self) -> None:
        assert "def _recover_recent_focus()" in self.SRC

    def test_recovery_runs_before_the_generic_default(self) -> None:
        """الاسترجاع يجب أن يسبق `same_color_event` وإلا عادت الكارثة."""
        recovery = self.SRC.index("_focus_step_id = _recover_recent_focus()")
        default = self.SRC.index('_focus_step_id = "same_color_event"')
        assert recovery < default

    def test_recovery_walks_history_newest_first(self) -> None:
        assert "for _msg in reversed(_dialogue_history)" in self.SRC

    def test_sticky_focus_recovers_the_live_transcript_topic(self) -> None:
        """محاكاة الأدوار: بعد سؤال عن جداء الأرقام، «لم أفهم» تبقى على نفس البؤرة."""
        detect = _extract_nested_function("_detect_focus_step")
        part = _extract_nested_function("_detect_part_reference")
        history = [
            {"role": "user", "content": "اعطني تمرين الاحتمالات 2024"},
            {"role": "user", "content": "الحصول على 3 كرات جداء أرقامها عدد فردي"},
            {"role": "assistant", "content": "لنبدأ من تكافؤ الجداء."},
        ]
        # نفس منطق `_recover_recent_focus`: الأحدث أولاً، حوار الطالب/المساعد حصراً.
        recovered = None
        for message in reversed(history):
            recovered = detect(str(message["content"])) or part(str(message["content"]))
            if recovered:
                break
        assert recovered == "product_parity_event", "«لم أفهم» يجب ألا تعود لخطوة الألوان"

    def test_recovery_ignores_assistant_prose(self) -> None:
        """مُثبَت حياً: ردّ المساعد يحوي نصّ التمرين كاملاً (وفيه «نفس اللون» و«فردي»
        و«زوجي» معاً)، فلو قرأه الاسترجاع لعاد دائماً بأول فرع `same_color_event`
        مهما سأل الطالب — إعادة إنتاج الكارثة من باب آخر. البؤرة نيّة الطالب.
        """
        assert 'if _msg.get("role") != "user":' in self.SRC

    def test_live_transcript_holds_the_students_topic(self, official_questions: str) -> None:
        """الترانسكريبت الحقيقي عبر `_build_calculated_ui` — مسار النداء الفعلي."""
        from app.infrastructure.clients.orchestrator_client import OrchestratorClient

        history = [
            {"role": "user", "content": "اعطني تمرين الاحتمالات 2024"},
            {"role": "assistant", "content": official_questions},
        ]
        focuses = []
        for question in ("لماذا نضرب ثلاثة أرقام في بعضها", "لم أفهم", "كيف"):
            component = OrchestratorClient._build_calculated_ui(question, history)
            focuses.append(((component or {}).get("props") or {}).get("focus_step_id"))
            history.append({"role": "user", "content": question})
        assert focuses == ["product_parity_event"] * 3, (
            f"«لم أفهم» يجب أن تبقى على موضوع الطالب لا أن تقفز للألوان — {focuses}"
        )

    def test_companion_texts_target_the_new_focuses(self) -> None:
        assert "سنركّز على جداء أرقام الكرات" in self.SRC
        assert "سنركّز على الاحتمال الشرطي" in self.SRC


# ── ٧. التعميم: التمارين غير المرقّمة لا تنكسر (Anti-Overfitting D-076) ─────────
class TestGenericExerciseUnaffected:
    QUESTION = (
        "كيس يحتوي على 4 كرات حمراء و 5 كرات خضراء و 2 كرة بيضاء. "
        "نسحب 3 كرات دفعة واحدة. احسب احتمال الحصول على 3 كرات من نفس اللون."
    )

    def test_no_numbered_balls_means_no_parity_steps(self) -> None:
        skill = ProbabilityCalculatorSkill
        assert skill.number_parity_counts(self.QUESTION) is None
        comp_raw = skill._extract_count_entities(self.QUESTION)
        built = skill._build_full_exercise_story(comp_raw, 11, self.QUESTION)
        assert built is not None
        produced = {s.step_id for s in built.exercise_steps}
        assert produced.isdisjoint(
            {"product_parity_event", "conditional_event", "sequential_zero_product"}
        ), "خطوات الأرقام تُنبَعث لتمارين الكرات المرقّمة فقط"
        assert {"data", "sample_space", "same_color_event"} <= produced

    def test_colour_based_random_variable_still_works(self) -> None:
        """بلا تعريف تكافؤ، يبقى X على الصنف المحوري كما كان (صفر تغيير سلوكي)."""
        skill = ProbabilityCalculatorSkill
        comp_raw = skill._extract_count_entities(self.QUESTION)
        built = skill._build_full_exercise_story(comp_raw, 11, self.QUESTION)
        variable = next((s for s in built.exercise_steps if s.step_id == "random_variable"), None)
        assert variable is not None
        assert variable.numerical_state["focal_label"] != "رقم زوجي"
