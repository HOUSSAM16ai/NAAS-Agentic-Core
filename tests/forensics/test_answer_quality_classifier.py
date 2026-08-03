"""عقد المصنِّف الشرعي — «الصمت» ثنائيٌّ لا عمودٌ واحد (D-209 · ISS-145).

هذا الاختبار يحرس الدرسَ الذي كلّف بلاغَ كارثةٍ كاملاً: قراءة `content` وحده أنتجت
ISS-145 («٢١٢ صفّاً فارغاً حُفِظ كإجابة») لعطبٍ **غير موجود** — إذ كانت الصفوف الـ212
كلّها تحمل بطاقة `ui_component` حقيقية. لو صُدِّق البلاغ لكان «الإصلاح» كسرَ مسار
البطاقات العامل.

فالتعريف الصحيح مُثبَّت هنا كودَاً: صمتٌ = `content` فارغ **و** `ui_component` غائب.
"""

from __future__ import annotations

import importlib.util
import sys
from functools import cache
from pathlib import Path
from types import ModuleType

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts/forensics/scan_answer_quality.py"


@cache
def _scan() -> ModuleType:
    """يُحمِّل السكربت **وقت الاختبار لا وقت الجمع** (D-105 · `check_test_hygiene`).

    كتابةُ `sys.modules` على مستوى الوحدة تُسمّم جلسة pytest كاملةً وقت الجمع (فئة
    ISS-113) — وقد أوقفتني البوّابة هنا فعلاً. والتسجيل نفسه **ضروري** لأن `@dataclass`
    يستبطن أنواعه عبر `sys.modules[cls.__module__]`، فوحدةٌ مُحمَّلة ديناميكياً وغير
    مُسجَّلة تُفشِل التحميل بـ`AttributeError` غامض. فالحلّ تأجيلُ الأثر لا إلغاؤه.
    """
    spec = importlib.util.spec_from_file_location("scan_answer_quality", _MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _turn(content: str | None, card: str | None = None) -> object:
    return _scan().Turn(message_id=1, content=content, ui_component=card)


def test_no_text_and_no_card_is_the_only_silence() -> None:
    assert _scan().classify(_turn("", None)) == "truly_silent"
    assert _scan().classify(_turn(None, None)) == "truly_silent"


@pytest.mark.parametrize(
    "component",
    [
        "full_exercise_story",
        "bkt_hint_display",
        "learning_path_card",
        "combinations_visualizer",
        "worked_example_card",
        "probability_tree",
    ],
)
def test_card_without_text_is_not_a_defect(component: str) -> None:
    """الحالة التي أخطأ فيها ISS-145 — البطاقة **هي** الجواب (D-116 · ISS-106).

    الستّة أعلاه هي المكوّنات التي ظهرت فعلاً في الصفوف الـ212 على الإنتاج.
    """
    assert _scan().classify(_turn("", f'{{"component":"{component}"}}')) is None


def test_promise_without_steps_is_still_a_defect() -> None:
    """ISS-148/D-207: عنوانٌ وخاتمة بلا خطوة — وعدٌ بشرحٍ لا يصل."""
    assert _scan().classify(_turn("لنكمل معاً خطوة بخطوة حتى النهاية:")) == "empty_promise"


def test_praise_over_confusion_is_a_defect() -> None:
    """ISS-149/D-208: الحيرة لا تُهنَّأ."""
    verdict = _scan().classify(_turn("أحسنت ✅ يبدو أنك أمسكت الفكرة، رغم أنك قلت لم أفهم"))
    assert verdict == "praise_over_confusion"


def test_a_real_arabic_answer_is_clean() -> None:
    assert _scan().classify(_turn("هذا شرحٌ عربيٌّ كاملٌ وطويلٌ بما يكفي ليكون جواباً حقيقياً.")) is None


def test_self_test_suite_passes() -> None:
    """المصنِّف يحمل بطاريته الخاصّة — نُشغّلها هنا كي تُعَدّ في تغطية CI."""
    assert _scan()._self_test() == 0
