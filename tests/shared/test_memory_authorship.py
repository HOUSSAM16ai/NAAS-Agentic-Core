"""تأليف الرسالة — نصّ النظام لا يُخزَّن بدور الطالب (D-229 · ISS-146).

العطل الحيّ: «[توجيه تربوي] …» كُتب في جدول رسائل الإنتاج **٢٨ مرّة بدور `user`**،
فصارت تعليماتُ النظام دليلاً من المحادثة يُقرأ بعد أسابيع.
"""

from __future__ import annotations

import pytest

from shared.memory import (
    SYSTEM_AUTHORED_MARKERS,
    MemoryAuthorshipError,
    assert_student_authored,
    is_system_authored,
    strip_system_markers,
)

#: النصّ الحقيقي من قاعدة الإنتاج (صفوف بدور `user`، يونيو 2026).
ISS_146_ROW = (
    "[توجيه تربوي] الطالب ما زال يبني هذا المفهوم. اشرح شرحاً كاملاً متدرجاً "
    "بسقالات: ثبّت الفكرة الأساسية والمعنى أولاً، ثم خطوات صغيرة مفصّلة بلغة بسيطة."
)

#: النصّ الحقيقي الآخر — ١٩٠٢ حرفاً وصلت طالباً كتب «لن أنجح هذا العام».
ISS_150_ROW = (
    "WARM‑UP: The instruction must be rendered in a coalesced English form that "
    "preserves a single flowing syntax."
)


class TestStudentTextPasses:
    """كلامُ الطالب الحقيقي يمرّ — الحارس يمنع التسميم لا التعلّم."""

    @pytest.mark.parametrize(
        "text",
        [
            "اعطني تمرين الاحتمالات 2024",
            "لم أفهم",
            "كيف نحسب A",
            "165",
            "لم افهم الاحتمالات و الآن عقدتها علي بمتتاليت",
            "ما هو المقام؟",
        ],
    )
    def test_real_student_messages_pass(self, text: str) -> None:
        assert is_system_authored(text) is False
        assert_student_authored(text, where="test")

    def test_empty_and_none_pass(self) -> None:
        """صفوف البطاقات المستقلّة تحمل `content=""` عمداً (ISS-106)."""
        assert is_system_authored("") is False
        assert is_system_authored(None) is False
        assert_student_authored("", where="test")


class TestSystemTextBlocked:
    """نصّ النظام يُرفَض صراحةً — لا صمت ولا تمرير."""

    def test_iss146_production_row_is_rejected(self) -> None:
        assert is_system_authored(ISS_146_ROW) is True
        with pytest.raises(MemoryAuthorshipError, match="تأليف النظام"):
            assert_student_authored(ISS_146_ROW, where="customer.save_message")

    def test_english_system_prompt_leak_is_rejected(self) -> None:
        assert is_system_authored(ISS_150_ROW) is True
        with pytest.raises(MemoryAuthorshipError):
            assert_student_authored(ISS_150_ROW, where="test")

    def test_internal_sentinel_is_rejected(self) -> None:
        """‏⟦…⟧ سُرِّبت ١٣ مرّة في نافذة يونيو."""
        assert is_system_authored("⟦مثال_محلول⟧ حدد المعطى") is True

    def test_deep_pedagogy_prefix_is_rejected(self) -> None:
        """مسموحٌ على السلك في MODE_B، ⛔ ممنوعٌ في التخزين."""
        assert is_system_authored("[وضع الشرح العميق] الطالب يعبّر عن حيرة") is True

    @pytest.mark.parametrize("marker", SYSTEM_AUTHORED_MARKERS)
    def test_every_declared_marker_is_detected(self, marker: str) -> None:
        """كل علامةٍ مُعلَنة مكشوفة فعلاً — قائمةٌ بلا كاشفٍ زينة."""
        assert is_system_authored(f"مقدمة {marker} وبقية النصّ") is True

    def test_marker_detected_mid_text_not_only_as_prefix(self) -> None:
        """النصّ المُسرَّب ظهر مرّةً بعد سطرٍ فارغ — حارسُ البادئة وحده كان سيمرّ."""
        assert is_system_authored("سؤال الطالب\n\n[توجيه تربوي] اشرح") is True

    def test_error_message_names_the_call_site(self) -> None:
        with pytest.raises(MemoryAuthorshipError, match="customer.save_message"):
            assert_student_authored(ISS_146_ROW, where="customer.save_message")


class TestStripIsNotASubstituteForBlocking:
    """التقليم للعرض والقياس — ⛔ ليس بديلاً عن المنع."""

    def test_strip_removes_markers(self) -> None:
        assert strip_system_markers("[توجيه تربوي] اشرح الفكرة") == "اشرح الفكرة"
        assert strip_system_markers("⟦مثال_محلول⟧ حدد") == "حدد"

    def test_stripped_text_is_still_not_student_authored_in_spirit(self) -> None:
        """نزعُ العلامة يجعل النصّ غير مرئيّ للحارس — ولهذا المنع عند الكتابة لا التقليم."""
        cleaned = strip_system_markers(ISS_146_ROW)
        assert is_system_authored(cleaned) is False
        assert "الطالب ما زال يبني هذا المفهوم" in cleaned
