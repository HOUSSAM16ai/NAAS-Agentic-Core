"""D-182 — حيرة حول *طريقة* السحب المتتالي ⇒ خطوة السحب المتتالي (لا خطوة الحدث).

الكارثة (transcript حي): الطالب سأل «لم أفهم لماذا نضرب ثلاثة أرقام في بعضهم تنازلياً؟»
— سؤال عن *طريقة* الجزء II (السحب «على التوالي وبدون إرجاع»). لكن `_detect_focus_step`
لم يملك أي نمط للتنازل/التوالي/بدون-إرجاع، فسقط السؤال إلى الافتراض العام
(`_is_deep_pedagogy` بلا focus ⇒ `same_color_event`) فانحرف المعلّم إلى سؤال الحدث
الافتتاحي («أيّ الألوان تعطينا 3 كرات من نفس اللون؟») بدل معالجة حيرة الطالب الفعلية.

D-182 (additive, monolith-only — البورت لا يملك `_detect_focus_step`): إشارات «تنازلي /
على التوالي / بدون إرجاع / الترتيب» ⇒ `sequential_zero_product` **قبل** السقوط الافتراضي.
الحيرة العامة («لم أفهم» بلا إشارة طريقة) تبقى ⇒ `same_color_event` (لا تراجع).

stdlib + source-inspection — يعمل في الـ sandbox بلا pydantic (نمط D-122).
"""

from __future__ import annotations

from app.infrastructure.clients.orchestrator.tutor_sources import read_tutor_source

CLIENT_SRC = read_tutor_source()


# D-184: كانت هنا نسخة standalone مكتوبة يدوياً. النسخة اليدوية تكذب صامتاً عند أي
# تعديل لاحق للكاشف — وقد كذبت فعلاً: بعد D-184 صارت «فردي/زوجي» تُرجِع
# `product_parity_event` و«شرطي» تُرجِع `conditional_event`، بينما بقيت المرآة تؤكّد
# `same_color_event`. نُصرِّف الآن الدالة **من مصدرها الحقيقي** عبر `ast` — stdlib
# فقط (يبقى الاختبار sandbox-safe) وبلا أي احتمال انحراف بين المرآة والأصل.
def _load_detect_focus_step():
    import ast
    from pathlib import Path

    source_path = (
        Path(__file__).resolve().parents[2]
        / "app/infrastructure/clients/orchestrator/probability_ui.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_detect_focus_step":
            namespace: dict[str, object] = {}
            exec(compile(ast.Module([node], []), str(source_path), "exec"), namespace)
            return namespace["_detect_focus_step"]
    raise AssertionError("_detect_focus_step not found in probability_ui.py")


_detect_focus_step = _load_detect_focus_step()


# ── 1. سؤال الطالب الفعلي لم يعد ينحرف ────────────────────────────────────────
class TestSequentialMethodConfusion:
    def test_descending_multiplication_maps_to_sequential(self) -> None:
        # سؤال الـ transcript الحي — يجب أن يستهدف السحب المتتالي لا الحدث.
        q = "لم أفهم لماذا نضرب ثلاثة أرقام في بعضهم تنازلياً؟"
        assert _detect_focus_step(q) == "sequential_zero_product"
        assert _detect_focus_step(q) != "same_color_event"

    def test_successive_without_replacement_markers(self) -> None:
        for q in (
            "لماذا نسحب على التوالي وبدون إرجاع",
            "اشرح السحب بدون إرجاع",
            "لم أفهم دور الترتيب هنا",
            "لماذا الضرب تنازلي",
        ):
            assert _detect_focus_step(q) == "sequential_zero_product", q


# ── 2. لا تراجع: الحيرة العامة تبقى على الحدث الافتتاحي ────────────────────────
class TestNoRegression:
    def test_generic_confusion_has_no_method_focus(self) -> None:
        # «لم أفهم» بلا إشارة طريقة ⇒ `_detect_focus_step` تُرجع None، فيتكفّل
        # السقوط الافتراضي (`_is_deep_pedagogy` ⇒ same_color_event) كما كان.
        assert _detect_focus_step("لم أفهم") is None
        assert _detect_focus_step("مفهمتش والو") is None

    def test_event_and_variable_steps_unchanged(self) -> None:
        assert _detect_focus_step("اشرح P(A)") == "same_color_event"
        assert _detect_focus_step("ما هو E(X) والمتغير العشوائي") == "random_variable"


# ── 3. source-inspection: التخصيص مطبَّق فعلاً في المصدر المُركَّب ──────────────
class TestSourceWiring:
    def test_sequential_markers_present(self) -> None:
        assert '"تنازلي" in q' in CLIENT_SRC
        assert '"على التوالي" in q' in CLIENT_SRC
        assert '"بدون إرجاع" in q' in CLIENT_SRC

    def test_sequential_return_before_default(self) -> None:
        # نمط D-182 يجب أن يعيد sequential_zero_product قبل حاجب السقوط الافتراضي.
        marker_pos = CLIENT_SRC.index('"تنازلي" in q')
        default_pos = CLIENT_SRC.index('_focus_step_id = "same_color_event"')
        assert marker_pos < default_pos, "D-182 method-focus must precede the generic default."

    def test_companion_text_targets_sequential(self) -> None:
        assert "السحب المتتالي بدون إرجاع" in CLIENT_SRC
