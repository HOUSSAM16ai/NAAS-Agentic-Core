"""عقود ماسح JavaScript داخل بوّابة عقد الأخطاء (D-236 · ISS-152).

## لماذا هذا الملفّ موجود

`scripts/fitness/check_error_contract_parity.py` تفحص أنّ **لا سلسلة إنجليزية**
تصل الطالب في مسار خطأ. وقد وُجد في ماسحها **ثلاثة ثقوب صامتة متتالية**، كلّها من
صنفٍ واحد: يقرأ أقلّ ممّا يدّعي، ثمّ يُبلِّغ النظافة.

1. `_JS_ENTRY` كانت تقبل الاقتباس المفرد وحده ⇒ جداول بعلامةٍ أخرى تسقط كلّها.
2. `_SET_ERROR` كانت تشترط فاصلةً منقوطة ملاصقة ⇒ `setError('…')` بلا فاصلة يفلت.
3. `_balanced_span` كانت تتجاوز السلاسل النصّية **لا التعابير النمطية** ⇒ `/\\)/`
   يُغلِق الاستدعاء مبكّراً فتُقتطَع البقية، وفيها قد تكون السلسلة الممنوعة.

الثلاثة رصدتها مراجعة CodeRabbit، لا اختباراتُنا — لأن الاختبارات كانت تسأل «هل
تمرّ البوّابة على الشجرة الحالية؟» ولم تسأل **«ماذا لا تراه؟»**.

⚠️ ولهذا يُثبَّت السلوك هنا بدل التحقّق اليدوي: فحصٌ يُجرى مرّةً في طرفيةٍ ثمّ
يُنسى ليس حارساً. طلبت المراجعة «regression fixtures» صراحةً، وهذه هي.

**القاعدة الباقية والمُعلَنة:** هذا ماسحٌ معجميّ مصغّر لا مُحلِّل JavaScript كامل.
ما لا يفهمه **يرفع `_ParseError`** فتفشل البوّابة بصوتٍ مسموع — وهو الفرق بين
حدٍّ معروف وثقبٍ صامت.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_FITNESS = Path(__file__).resolve().parents[2] / "scripts" / "fitness"
if str(_FITNESS) not in sys.path:
    sys.path.insert(0, str(_FITNESS))

import check_error_contract_parity as gate
from check_error_contract_parity import _balanced_span, _ParseError

BANNED = "Login failed"


def _argument(source: str) -> str:
    """وسائط أوّل استدعاء في ``source``."""
    argument, _ = _balanced_span(source, source.find("("), "(", ")")
    return argument


# ── 1) السلسلة الممنوعة تبقى مرئية مهما كان ما حولها ────────────────────────
@pytest.mark.parametrize(
    ("source", "why"),
    [
        (r"setError(/\)/.test(v) ? 'Login failed' : null)", "قوسٌ داخل تعبير نمطي"),
        (r"setError(/[/]/.test(v) ? 'Login failed' : null)", "شرطة داخل صنف محارف"),
        (r"setError(/a\/b/.test(v) ? 'Login failed' : null)", "شرطة مهروبة"),
        (r"setError((x) === true ? 'Login failed' : null)", "أقواس متداخلة"),
        (r"setError(total / count + ' ' + 'Login failed')", "قسمة لا تعبير نمطي"),
        (r"setError(a /* ملاحظة */ + 'Login failed')", "تعليق كتلي لا تعبير نمطي"),
        (r'setError(cond ? "Login failed" : null)', "اقتباس مزدوج"),
        (r"setError(`Login failed`)", "قالب نصّي"),
    ],
)
def test_banned_string_stays_visible_to_the_scanner(source: str, why: str) -> None:
    """⛔ الماسح لا يقتطع النصّ قبل السلسلة الممنوعة.

    هذا هو العقد الذي انكسر ثلاث مرّات: البوّابة تُبلِّغ «صفر سلسلة إنجليزية» عن
    نصٍّ لم تقرأه كاملاً.
    """
    assert BANNED in _argument(source), f"السلسلة الممنوعة اختفت عن الماسح ({why})"


# ── 2) ما لا يُفهَم يُعلَن ولا يُبتَر ───────────────────────────────────────
@pytest.mark.parametrize(
    "source",
    [
        r"setError('x + y)",  # سلسلة غير مُغلَقة
        r"setError(+ 'hello)",
        r"setError((/hello)",  # تعبير نمطي غير مُغلَق ⇒ قوسٌ لا يُغلَق
        r"setError(nested(",
    ],
)
def test_unparseable_input_fails_closed(source: str) -> None:
    """⛔ نصٌّ غير متّزن يرفع خطأً — لا يُعيد نصفاً يُقرأ نظافةً.

    كانت الدالّة تُرجع ما تبقّى كأنّه وسائط كاملة، فتُفحَص قطعةٌ مبتورة ويُبلَّغ
    عنها بالنظافة (D-208: بوّابةٌ تشهد بما لم تقرأ).
    """
    with pytest.raises(_ParseError):
        _argument(source)


# ── 3) التوازن والتداخل يُحسبان صحيحاً ──────────────────────────────────────
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("f(abc)", "abc"),
        ("f(a(b)c)", "a(b)c"),
        ("f('a)b')", "'a)b'"),
        ('f("x)y")', '"x)y"'),
        ("f(`t)`)", "`t)`"),
        ("x { a { b } c }", None),  # يُفحَص بالمعقوفات أدناه
    ],
)
def test_span_boundaries(source: str, expected: str | None) -> None:
    """حدود الكتلة تُحسَب مع التداخل وعلامات الاقتباس الثلاث."""
    if expected is None:
        content, _ = _balanced_span(source, 0, "{", "}")
        assert content == " a { b } c "
        return
    assert _argument(source) == expected


def test_missing_opener_is_not_an_error() -> None:
    """غياب المحدِّد ليس عطباً — لا يوجد ما يُفحَص، ولا يُرفَع خطأ."""
    content, close = _balanced_span("no opener here", 0, "(", ")")
    assert content == ""
    assert close == -1


# ── 4) الكشف الحيّ على أشكال الاستدعاء الواقعية ─────────────────────────────
def test_set_error_without_trailing_semicolon_is_seen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⛔ استدعاءٌ بلا فاصلة منقوطة (داخل JSX) لا يفلت من الفحص.

    كان النمط القديم يشترط `;` ملاصقة، فكان `onClick={() => setError('…')}`
    غير مرئيّ — وهو الشكل الأكثر شيوعاً في JSX.
    """
    # `_english_fallbacks` تُبلِّغ المسار **نسبةً إلى جذر المستودع**، فيُوجَّه
    # الجذر إلى المجلّد المؤقّت كي يبقى الاختبار محصوراً بلا كتابةٍ في الشجرة.
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    client = tmp_path / "widget.jsx"
    client.write_text(
        "export const W = () => <button onClick={() => setError('Login failed')} />;\n",
        encoding="utf-8",
    )
    offences = gate._english_fallbacks(client)
    assert offences, "سقوطٌ إنجليزي بلا فاصلة منقوطة أفلت من الفحص"
    assert any(BANNED in offence for offence, _ in offences)


def test_comments_are_not_scanned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """التوثيق الذي **يشرح** العطب لا يُعَدّ ارتكاباً له.

    بوّابةٌ تعاقب شرح سبب وجودها تُعلِّم القارئ حذف الشرح.
    """
    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    client = tmp_path / "documented.jsx"
    client.write_text(
        "// كان السطر القديم: setError('Login failed')\n"
        "/* وأيضاً: setError('Registration failed') */\n"
        "const ok = () => setError('حدث خطأ.');\n",
        encoding="utf-8",
    )
    assert gate._english_fallbacks(client) == []
