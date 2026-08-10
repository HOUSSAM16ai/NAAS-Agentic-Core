"""بوّابة «عقد الأخطاء يُقرأ فعلاً» (D-236 · ISS-152).

## لماذا هذه البوّابة موجودة

الطالب كان يرى **`Login failed`** — سلسلة إنجليزية حرفية على منصّة عربية، تُخفي
السبب الحقيقي أيّاً كان. والجذر لم يكن في المصادقة أصلاً، بل في **عقدٍ مُعلَن
بنصفه**: الخلفية تُخرج `message`، والواجهة تقرأ `detail`.

مُبرهَنٌ حيّاً على خادم حقيقي قبل الإصلاح:

```text
POST /api/security/login  (كلمة سرّ خاطئة) -> 401
TOP-LEVEL KEYS: ['data', 'message', 'status', 'timestamp']
HAS 'detail' KEY: False
==> FRONTEND WOULD DISPLAY: 'Login failed'
```

طرفان يتكلّمان عقدين، ولا شيء يلاحظ. البوّابة تجعل ذلك مستحيلاً بنيويّاً.

## ما تفرضه

1. **المعالج يُخرج كل مفتاحٍ يقرؤه أي عميل.** تُقرأ مفاتيح المعالج من المصدر
   بـAST (لا نصّاً)، وتُقارَن بالمفاتيح التي تقرؤها الواجهات من أجسام الأخطاء.
2. ⛔ **لا سلسلة سقوط إنجليزية في مسار خطأ يراه الطالب.** العربية هي لغة الواجهة؛
   سلسلة إنجليزية في `setError(... || '...')` عطبٌ لغويّ وتشخيصيّ معاً.
3. **`detail` و`message` يحملان نفس القيمة** في باني الحمولة — حقلان بقيمتين
   مختلفتين يعيدان إنتاج العطب بصيغة أخرى (D-192).
4. **جداول الترجمة الثلاثة متطابقة.** رصدته مراجعة CodeRabbit وكانت مُحقّة:
   `ARABIC_BY_ERROR_CODE` و`ARABIC_BY_STATUS` مكرّران حرفياً في ثلاثة ملفّات
   (الملفّان القديمان يُحمَّلان كسكربتات عامة فلا يستطيعان الاستيراد)، والقاعدة
   كانت **مكتوبة في تعليق**. وهذا الـPR نفسه حجّته أنّ قاعدةً بلا فارضٍ آلي ليست
   قاعدة — فكان لزاماً أن يُطبَّق الحكم على الشيفرة التي يقدّمها.

**قاعدة الدَّين:** `_FROZEN_DEBT` **يتقلّص فقط** (سابقة D-105 · D-186): مدخل جديد
يُفشِل CI، ومدخلٌ صار نظيفاً يُفشِل CI أيضاً حتى يُحذَف — فلا تتراكم استثناءات ميتة.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ast_util import parse_source, run_gate

REPO_ROOT = Path(__file__).resolve().parents[2]

#: مصدر عقد الأخطاء — المعالج الذي يبني كل جسم خطأ.
HANDLER_PATH = REPO_ROOT / "app" / "middleware" / "fastapi_error_handlers.py"

#: المصدر القانوني لجداول الترجمة العربية.
TABLE_SOURCE = REPO_ROOT / "frontend" / "app" / "utils" / "apiError.js"

#: المرآتان — تُحمَّلان كسكربتات عامة في المتصفّح فلا تستطيعان الاستيراد.
TABLE_MIRRORS: tuple[Path, ...] = (
    REPO_ROOT / "frontend" / "public" / "js" / "legacy-app.jsx",
    REPO_ROOT / "app" / "static" / "js" / "legacy-app.jsx",
)

#: عملاء الواجهة الذين يقرؤون أجسام الأخطاء.
CLIENT_PATHS: tuple[Path, ...] = (
    TABLE_SOURCE,
    REPO_ROOT / "frontend" / "app" / "components" / "CogniForgeApp.jsx",
    *TABLE_MIRRORS,
)

#: المفاتيح التي يجب أن يُخرجها المعالج دائماً.
REQUIRED_KEYS: frozenset[str] = frozenset(
    {"status", "detail", "message", "error_code", "data", "request_id", "timestamp"}
)

#: العملاء الذين يقرؤون مفاتيح **جسم** الخطأ (لا مجرّد `setError`).
#: `CogniForgeApp.jsx` يفوّض القراءة إلى `readApiError` فلا يقرأ الجسم بنفسه.
_BODY_READING_CLIENTS: tuple[Path, ...] = (TABLE_SOURCE, *TABLE_MIRRORS)

#: الدالّة التي تقرأ جسم الخطأ في النسخ الثلاث — بالصيغتين (تصريح · سهمية).
#: اسم المعامل يُلتقَط منها **ولا يُفترَض**: الفحص يتبع الكود لا العكس.
_BODY_READER = re.compile(
    r"function\s+messageFromBody\s*\(\s*([A-Za-z_$][\w$]*)\s*\)"
    r"|const\s+messageFromBody\s*=\s*\(?\s*([A-Za-z_$][\w$]*)\s*\)?\s*=>"
)

#: أسماء الجداول التي يجب أن تتطابق عبر النسخ الثلاث.
TABLE_NAMES: tuple[str, ...] = ("ARABIC_BY_ERROR_CODE", "ARABIC_BY_STATUS")

#: سلاسل سقوط إنجليزية ممنوعة في مسارات الخطأ المرئية للطالب.
#: ⚠️ تُطابَق داخل `setError(...)` فقط — لا في التعليقات ولا في `console.*`،
#: وإلّا لأفشلت البوّابةُ التوثيقَ الذي يشرح سبب وجودها (وهو ما حدث في أول تشغيل).
_BANNED_FALLBACKS: tuple[str, ...] = (
    "Login failed",
    "Registration failed",
    "Connection failed",
    "Failed to load conversation",
    "An error occurred. Please try again.",
)

#: **دَين مُجمَّد — يتقلّص فقط.** فارغ عمداً: العطب أُصلح بالكامل، وأي مدخل هنا
#: يعني مساراً يعرض إنجليزيةً على طالب عربي.
_FROZEN_DEBT: dict[str, str] = {}


# ─── قراءة المعالج بـAST ─────────────────────────────────────────────────────


def _function_named(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    """يعيد أوّل دالّة بهذا الاسم في الشجرة."""
    return next(
        (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name),
        None,
    )


def _payload_dict() -> ast.Dict | None:
    """قاموس الإرجاع من `build_error_payload`.

    يُقرأ من الشجرة لا بالنصّ: `grep` عن `"detail"` يطابق تعليقاً يشرح غيابها،
    وهو بالضبط الفخّ الذي يجعل البوّابة تشهد بما لم تقرأ (D-208).
    """
    builder = _function_named(parse_source(HANDLER_PATH), "build_error_payload")
    if builder is None:
        return None
    returns = (n for n in ast.walk(builder) if isinstance(n, ast.Return))
    return next((n.value for n in returns if isinstance(n.value, ast.Dict)), None)


def _handler_emitted_keys() -> set[str]:
    """مفاتيح جسم الخطأ التي يُخرجها المعالج فعلاً."""
    payload = _payload_dict()
    if payload is None:
        return set()
    keys = (k for k in payload.keys if isinstance(k, ast.Constant))
    return {k.value for k in keys if isinstance(k.value, str)}


def _entry_variable(key: ast.expr | None, value: ast.expr, wanted: tuple[str, ...]) -> str | None:
    """اسم المتغيّر المُسنَد لمفتاحٍ مطلوب، أو ``None``."""
    if not isinstance(key, ast.Constant) or key.value not in wanted:
        return None
    return value.id if isinstance(value, ast.Name) else None


def _named_sources(payload: ast.Dict, wanted: tuple[str, ...]) -> dict[str, str]:
    """يربط كل مفتاح مطلوب بالمتغيّر الذي يُسنَد منه."""
    pairs = zip(payload.keys, payload.values, strict=False)
    found = ((k, _entry_variable(k, v, wanted)) for k, v in pairs)
    return {k.value: name for k, name in found if name is not None and isinstance(k, ast.Constant)}


def _detail_mirrors_message() -> bool:
    """هل `detail` و`message` يُسنَدان من نفس الاسم في باني الحمولة؟"""
    payload = _payload_dict()
    if payload is None:
        return False
    sources = _named_sources(payload, ("detail", "message"))
    detail = sources.get("detail")
    return detail is not None and detail == sources.get("message")


# ─── قراءة الجداول من ملفّات JS ──────────────────────────────────────────────

#: `const NAME = { ... };` — يشمل صيغة `export const` وصيغة السكربت العام.
_JS_TABLE = re.compile(r"(?:export\s+)?const\s+(\w+)\s*=\s*{(.*?)\n\s*};", re.DOTALL)

#: `key: 'value',` — المفتاح عاريًا أو مقتبَساً، والقيمة بأي علامة اقتباس
#: (مفردة · مزدوجة · قالبية). ⚠️ كانت تقبل المفردة وحدها، وهو **ثقبٌ صامت**
#: رصدته مراجعة CodeRabbit: لو كتبت النسخُ الثلاث قيمها بعلامة أخرى لسقط كل
#: مفتاح من كل قاموس، فقارن `_table_diff` فراغاً بفراغ وطبعت البوّابة سطر
#: النجاح. أي أنها تشهد بنصٍّ لم تقرأه — نفس عطب D-208 الذي يحذّر منه توثيقها.
_JS_ENTRY = re.compile(
    r"^\s*['\"]?(\w+)['\"]?\s*:\s*"
    r"(?:'((?:[^'\\]|\\.)*)'|\"((?:[^\"\\]|\\.)*)\"|`((?:[^`\\]|\\.)*)`)",
    re.MULTILINE,
)

#: كل سطرٍ **يبدو** مدخلاً. يُقارَن بعدد ما التُقط فعلاً، فيصير السقوط الصامت
#: مستحيلاً: ما لم يُفهَم يُعلَن بدل أن يُحذَف.
_JS_ENTRY_SHAPE = re.compile(r"^\s*['\"]?\w+['\"]?\s*:", re.MULTILINE)


def _js_tables(path: Path) -> dict[str, dict[str, str]]:
    """يستخرج جداول الترجمة من ملفّ JS كقواميس بايثون.

    Raises:
        ValueError: حين يتعذّر تحليل مدخلٍ واحد — البوّابة تتوقّف بدل أن تشهد
            على نصٍّ لم تفهمه.
    """
    source = _strip_comments(path.read_text(encoding="utf-8"))
    tables: dict[str, dict[str, str]] = {}
    for name, body in _JS_TABLE.findall(source):
        if name not in TABLE_NAMES:
            continue
        entries = {
            key: single or double or template
            for key, single, double, template in _JS_ENTRY.findall(body)
        }
        expected = len(_JS_ENTRY_SHAPE.findall(body))
        if len(entries) != expected:
            raise ValueError(
                f"{path.relative_to(REPO_ROOT)}: {name} — قُرئ {len(entries)} من {expected} مدخلاً. "
                "بوّابةٌ تقرأ بعض النصّ تشهد بما لم تقرأ (D-208)."
            )
        tables[name] = entries
    return tables


def _table_diff(name: str, source: dict[str, str], mirror: dict[str, str]) -> list[str]:
    """يصف الفروق بين جدول المصدر وجدول المرآة."""
    problems: list[str] = []
    missing = sorted(set(source) - set(mirror))
    extra = sorted(set(mirror) - set(source))
    changed = sorted(k for k in set(source) & set(mirror) if source[k] != mirror[k])
    if missing:
        problems.append(f"{name}: مفاتيح ناقصة في المرآة {missing}")
    if extra:
        problems.append(f"{name}: مفاتيح زائدة في المرآة {extra}")
    if changed:
        problems.append(f"{name}: قيم مختلفة لنفس المفتاح {changed}")
    return problems


# ─── قراءة سلاسل السقوط ──────────────────────────────────────────────────────

#: بداية استدعاء `setError(` — الوسائط تُقتطَع **بموازنة الأقواس** لا بتعبير نمطي.
#:
#: ⛔ كان النمط `setError\s*\(([^;]*?)\)\s*;`، وهو يفترض شيئين غير صحيحين: أن
#: الاستدعاء ينتهي بفاصلة منقوطة **ملاصقة**، وأنّ وسائطه **لا تحوي** فاصلة
#: منقوطة. فكان `setError(x)` بلا `;` (آخر عبارة في كتلة سهمية) و`setError(f(a);
#: b)` وكل استدعاءٍ يتبعه سطرٌ جديد قبل `;` **يمرّ بلا فحص** — أي أنّ البوّابة
#: تُبلِّغ النظافة عن نصٍّ لم تقرأه. رصدته مراجعة CodeRabbit، وهو نفس صنف عطب
#: `_JS_ENTRY` (الاقتباس المفرد) الذي رصدته قبله — والدرس واحد: **التعبير النمطي
#: لا يوازن الأقواس، فلا يُسأل أن يفعل.**
_SET_ERROR_OPEN = re.compile(r"\bsetError\s*\(")


class _ParseError(ValueError):
    """نصٌّ تعذّر فهمه — تفشل البوّابة صراحةً بدل أن تمرّ عليه بصمت."""


#: علامات الاقتباس الثلاث في JS.
_QUOTES: str = "'\"`"

#: جسم تعبيرٍ نمطي كامل: مهروب · صنف محارف · محرف عادي — ثمّ الشرطة الختامية.
_REGEX_LITERAL = re.compile(r"/(?:\\.|\[(?:\\.|[^\]\\])*]|[^/\\\n[])*/")

#: محارف تسبق `/` فتجعلها **بداية تعبير نمطي** لا قسمةً.
#: JS لا يُميَّز فيها الاثنان إلّا بالسياق؛ وهذه القائمة تغطّي مواضع التعبير النمطي
#: الواقعية داخل استدعاء (`setError(/x/.test(v) ? … )`). ⚠️ تقريبٌ مُعلَن لا
#: مُحلِّل كامل — ولذلك يُكمِّله **الفشل المُغلَق** أدناه.
_REGEX_PRECEDERS: str = "(,=:[!&|?{};+-*%~^<>"

#: كلماتٌ مفتاحية تُنهي سياقاً **يتوقّع قيمة**، فـ`/` بعدها تعبيرٌ نمطي لا قسمة.
#:
#: ⛔ `return /\)/.test(v)` هو الشكل الواقعي الذي أسقط التقريب الأوّل: آخر محرفٍ
#: قبل الشرطة هو `n` — حرفُ هوية — فقُرئت **قسمةً**، فمُسِح جسم التعبير كنصٍّ عادي
#: و`)` الذي بداخله أغلق الاستدعاء مبكّراً، فاختفت السلسلة الممنوعة بعده. رصدته
#: مراجعة CodeRabbit بمثالٍ مُشغَّل، وهو الثقب الصامت الرابع من نفس الصنف: الماسح
#: يقرأ أقلّ ممّا يدّعي ثمّ يُبلِّغ النظافة.
_REGEX_KEYWORDS: frozenset[str] = frozenset(
    {
        "return",
        "typeof",
        "instanceof",
        "in",
        "of",
        "new",
        "delete",
        "void",
        "throw",
        "case",
        "do",
        "else",
        "yield",
        "await",
    }
)

#: آخر كلمةٍ متّصلة قبل موضعٍ ما — لتمييز الكلمة المفتاحية عن اسمٍ ينتهي بها
#: (`myreturn / 2` قسمةٌ، و`return / 2` ليست تعبيراً صالحاً أصلاً).
_TRAILING_WORD = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*$")


def _starts_regex(source: str, index: int) -> bool:
    """هل الشرطة المائلة عند ``index`` تبدأ تعبيراً نمطياً؟

    يُقرأ آخر محرفٍ غير فراغيّ قبلها: بعد مُعامِلٍ أو فاصلةٍ أو قوسٍ مفتوح تكون
    تعبيراً نمطياً، وبعد قيمةٍ تكون قسمة.

    وتُقرأ **الكلمة** لا المحرف وحده: `return` تنتهي بحرف هوية، فالقراءة المحرفية
    وحدها كانت تصنّف `return /x/` قسمةً — وهو ثقبٌ صامت لا حدٌّ معروف.

    ⚠️ التعليقات ليست من شأن هذه الدالّة — يملكها `_scan_step` ويقفزها قبل أن
    تُسأل أصلاً (مصدرٌ واحد لقرار التعليق، لا فحصان يفترقان).
    """
    before = source[:index].rstrip(" \t\n\r")
    if not before:
        return True
    if before[-1] in _REGEX_PRECEDERS:
        return True
    word = _TRAILING_WORD.search(before)
    return word is not None and word.group() in _REGEX_KEYWORDS


def _skip_regex(source: str, index: int) -> int:
    """يعيد موضع ما بعد نهاية تعبيرٍ نمطي فُتح عند ``index``.

    ⛔ وُجدت هذه الدالّة لأن ``/\\)/`` كان **يُغلِق الاستدعاء مبكّراً**: تنتهي
    الوسائط عند القوس الذي بداخل التعبير النمطي، فتُقتطَع البقية — وفيها قد تكون
    السلسلة الممنوعة. أي أنّ البوّابة تُبلِّغ النظافة عن نصٍّ **قرأت نصفه**.
    رصدته مراجعة CodeRabbit بمسبارٍ مُشغَّل، وهو نفس صنف الثقب الصامت مرّتين قبله.

    النمط يُغطّي المهروب وصنف المحارف (فـ``/[/]/`` لا ينتهي عند الشرطة بداخله).

    ⛔ **وما لا يُطابِق يرفع `_ParseError` فوراً.** كانت الدالّة تُعيد ``index + 1``
    اتّكالاً على أنّ الاتّزان سيختلّ لاحقاً — وهو **رهانٌ يخسر**: تعبيرٌ نمطي غير
    مُنتهٍ يحتوي ``)`` يُغلِق الاستدعاء بالضبط ويجعل الاتّزان **سليماً ظاهرياً**،
    فيُبتَر النصّ بصمت وتُبلَّغ النظافة. رصدته مراجعة CodeRabbit، والفشل المُغلَق
    هو الفرق بين حدٍّ معروف وثقبٍ صامت (D-208).
    """
    match = _REGEX_LITERAL.match(source, index)
    if match is None:
        raise _ParseError(f"تعبيرٌ نمطي غير مُنتهٍ عند الموضع {index}: {source[index : index + 40]!r}")
    return match.end()


def _skip_comment(source: str, index: int) -> int:
    """يعيد موضع ما بعد تعليقٍ يبدأ عند ``index`` (``//`` أو ``/*``).

    ⛔ وُجدت لأنّ الماسح **لم يكن يفهم التعليقات إطلاقاً**: كان يمرّ على `/*` ثمّ
    يقرأ `*/` الختامية بدايةَ تعبيرٍ نمطي (لأن `*` من سوابق التعبير النمطي).
    عاش ذلك صامتاً ما دام `_skip_regex` يتقدّم محرفاً عند الفشل — وظهر لحظة صار
    الفشل مُغلَقاً. أي أنّ الصمت كان **يُخفي عطبين** لا واحداً.

    والتعليق غير المُنتهي يرفع خطأً كغيره: ما لا يُفهَم يُعلَن.
    """
    if source[index + 1 : index + 2] == "/":
        end = source.find("\n", index + 2)
        return len(source) if end == -1 else end + 1
    end = source.find("*/", index + 2)
    if end == -1:
        raise _ParseError(f"تعليقٌ كتليّ غير مُنتهٍ عند الموضع {index}")
    return end + 2


def _skip_string(source: str, index: int, quote: str) -> int:
    """يعيد موضع ما بعد نهاية سلسلةٍ نصّية فُتحت للتوّ، متجاوزاً المهروب."""
    i = index
    while i < len(source):
        ch = source[i]
        if ch == "\\":
            i += 2
            continue
        if ch == quote:
            return i + 1
        i += 1
    return i


def _scan_step(source: str, index: int, opener: str, closer: str) -> tuple[int, int]:
    """قرارُ محرفٍ واحد: ``(الموضع التالي, تغيّر العمق)``.

    السلسلة النصّية تُقفَز كاملةً فلا يُحسَب محدِّدٌ داخل نصّ، وما عداها يُغيّر
    العمق بـ``+1``/``-1``/``0``. فروعٌ متجاورة لا متداخلة — وهذا هو الغرض.
    """
    ch = source[index]
    if ch in _QUOTES:
        return _skip_string(source, index + 1, ch), 0
    if ch == "/":
        if source[index + 1 : index + 2] in ("/", "*"):
            return _skip_comment(source, index), 0
        if _starts_regex(source, index):
            return _skip_regex(source, index), 0
    return index + 1, {opener: 1, closer: -1}.get(ch, 0)


def _balanced_span(source: str, start: int, opener: str, closer: str) -> tuple[str, int]:
    """محتوى أوّل كتلةٍ متوازنة عند ``start`` أو بعده، وموضع مُغلِقها.

    ماسحٌ **واحد** للأقواس والأقواس المعقوفة معاً: كانت الدالّتان `_call_arguments`
    و`_brace_block` نسختين من الخوارزمية نفسها بمحدِّدَين مختلفَين، فقاست CodeScene
    التعقيد مرّتين وأصابت — والتكرار هنا أسوأ من مجرّد إطالة: خوارزميتان متطابقتان
    تنحرفان عند أوّل إصلاح يُطبَّق على إحداهما (نفس منطق قاعدة المرآة D-013).

    ⚠️ السلاسل النصّية **والتعابير النمطية** تُتجاوَز فلا يُحسَب محدِّدٌ بداخلها.

    ⛔ **وعدم الاتّزان يرفع خطأً — لا يُعيد نصفاً.** كانت الدالّة تُرجع ما تبقّى
    كأنّه وسائط كاملة، فتُفحَص قطعةٌ مبتورة ويُبلَّغ عنها بالنظافة. والبوّابة التي
    تشهد على نصٍّ قرأت بعضه هي العطب الذي وُجدت لتمنعه (D-208). رصدته مراجعة
    CodeRabbit، والفشل المُغلَق هنا يُكمِّل تقريب `_starts_regex`: ما لا يُفهَم
    **يُعلَن** بدل أن يمرّ.

    قرارُ المحرف الواحد مُستخرَجٌ في :func:`_scan_step` فتبقى الحلقة **مسطّحة**:
    قياسُ CodeScene («Bumpy Road») كان مُحقّاً — تفرّعٌ داخل تفرّعٍ داخل حلقةٍ يجعل
    الشرط الحاسم (`depth == 0`) مدفوناً في الطبقة الثالثة، وهو أسوأ موضعٍ لأهمّ سطر.
    """
    open_at = source.find(opener, start)
    if open_at == -1:
        return "", -1
    depth = 0
    i = open_at
    while i < len(source):
        nxt, delta = _scan_step(source, i, opener, closer)
        depth += delta
        if depth == 0:
            return source[open_at + 1 : i], i
        i = nxt
    line = source[:open_at].count("\n") + 1
    raise _ParseError(
        f"محدِّد {opener!r} عند السطر {line} لم يُغلَق — تعذّر تحديد نطاقه. "
        "البوّابة تفشل بدل أن تشهد على نصٍّ لم تقرأه كاملاً."
    )


#: تعليقات JS — سطرية وكتلية. تُحيَّد قبل الفحص مع **الحفاظ على أرقام الأسطر**
#: (يُستبدَل كل محرف بمسافة، وتبقى الأسطر الجديدة) كي يظلّ الموضع المُبلَّغ صحيحاً.
_JS_COMMENT = re.compile(r"/\*.*?\*/|//[^\n]*", re.DOTALL)


def _strip_comments(source: str) -> str:
    """يُحيّد التعليقات مع حفظ الإزاحة.

    بدون هذا كانت البوّابة تُفشِل **توثيقها الخاصّ**: `apiError.js` يشرح العطب
    باقتباس السطر القديم `setError((await res.json()).detail || 'Login failed')`،
    فطابقه الفحص. بوّابةٌ تعاقب شرحَ سبب وجودها تُعلِّم القارئ حذفَ الشرح.
    """
    return _JS_COMMENT.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), source)


def _english_fallbacks(path: Path) -> list[tuple[str, int]]:
    """يعيد ``(مفتاح الموضع, رقم السطر)`` لكل سقوطٍ إنجليزي ممنوع.

    ⚠️ **المفتاح بلا رقم سطر عمداً.** كان الدَّين المُجمَّد يُفهرَس بـ
    ``path:line: …``، فكان يكفي أن يُضاف سطرٌ أعلى الملفّ ليصير المفتاح غير
    مطابق — فيُبلَّغ الدَّينُ المعروف **مخالفةً جديدة** ويُبلَّغ في نفس الوقت
    **دَيناً قديماً لم يعد موجوداً**. رصدته مراجعة CodeRabbit. رقم السطر يبقى
    للتشخيص، ولا يدخل في الهوية.
    """
    if not path.exists():
        return []
    source = _strip_comments(path.read_text(encoding="utf-8"))
    rel = path.relative_to(REPO_ROOT)
    offences: list[tuple[str, int]] = []
    position = 0
    while (match := _SET_ERROR_OPEN.search(source, position)) is not None:
        argument, close = _balanced_span(source, match.end() - 1, "(", ")")
        line = source[: match.start()].count("\n") + 1
        offences.extend(
            (f"{rel}: setError(... '{banned}')", line)
            for banned in _BANNED_FALLBACKS
            if banned in argument
        )
        position = max(close + 1, match.end())
    return offences


# ─── الفحوص ──────────────────────────────────────────────────────────────────


def _check_handler_keys(emitted: set[str]) -> list[str]:
    """يتحقّق من أن المعالج يُخرج كل مفتاحٍ إلزامي."""
    if not emitted:
        return [
            "لم يُعثر على `build_error_payload` أو على قاموس إرجاعه في "
            f"{HANDLER_PATH.relative_to(REPO_ROOT)} — العقد بلا مصدر."
        ]
    missing = REQUIRED_KEYS - emitted
    if not missing:
        return []
    return [
        "المعالج لا يُخرج مفاتيح إلزامية: "
        + ", ".join(sorted(missing))
        + " — كل مفتاحٍ يقرؤه عميلٌ يجب أن يُخرجه المعالج (ISS-152)."
    ]


def _client_body_keys(path: Path) -> set[str]:
    """المفاتيح التي يقرؤها هذا العميل من **جسم الخطأ**.

    ⚠️ النطاق هو جسم ``messageFromBody`` وحده، واسم المعامل يُلتقَط من التوقيع.
    أوّل صياغةٍ لهذا الفحص مسحت الملفّ كلّه بحثاً عن ``body.*``، فأبلغت
    ``content`` و``conversation_id`` مخالفاتٍ — وهي حمولاتُ WebSocket لا أجسام
    أخطاء. أي أنّ الفحص نفسه كاد يصير مصدر ضجيجٍ يُطفَأ لاحقاً، وبوّابةٌ تُطفَأ
    أسوأ من بوّابةٍ لا تُكتَب.
    """
    if not path.exists():
        return set()
    source = _strip_comments(path.read_text(encoding="utf-8"))
    match = _BODY_READER.search(source)
    if match is None:
        return set()
    param = match.group(1) or match.group(2)
    block, _ = _balanced_span(source, match.end(), "{", "}")
    reader = re.compile(rf"\b{re.escape(param)}\s*\??\.\s*([A-Za-z_$][\w$]*)")
    return {
        hit.group(1)
        for hit in reader.finditer(block)
        if not block[hit.end() :].lstrip().startswith("(")
    }


def _check_client_keys(emitted: set[str]) -> list[str]:
    """⛔ **كل مفتاحٍ يقرؤه عميل يجب أن يُخرجه المعالج.**

    هذا هو العقد الذي وُلدت منه البوّابة، وهو **لم يكن مُنفَّذاً**: كان
    :func:`_check_handler_keys` يقارن المعالج بقائمة ثابتة مكتوبة هنا
    (``REQUIRED_KEYS``)، بينما يعد التوثيق بمقارنته **بما تقرؤه الواجهات فعلاً**.
    فبوّابةٌ تشهد بما لم تقرأ — نفس عطب D-208 الذي يستشهد به هذا الـPR نفسه.
    رصدته مراجعة CodeRabbit، وهو الآن مُنفَّذ: تُقرأ المفاتيح من الواجهات وتُقارَن
    بمخرَج المعالج، فلو أضاف أحدهم قراءة `body.reason` غداً بلا مُصدِرٍ لها
    لاحمرّت CI — وهذا بالضبط شكل عطب «Login failed» الأصلي.

    ولأن **الصمت يُقرأ نجاحاً** (D-207/D-208): عميلٌ لا تُقرأ منه مفاتيح البتّة
    يُبلَّغ مخالفةً، وإلّا لمرّ تغييرُ اسم متغيّر الجسم بلا فحص.
    """
    failures: list[str] = []
    for client in _BODY_READING_CLIENTS:
        rel = client.relative_to(REPO_ROOT)
        if not client.exists():
            continue  # الوجود يفحصه `_check_clients`
        try:
            keys = _client_body_keys(client)
        except _ParseError as exc:
            failures.append(f"{rel}: {exc}")
            continue
        if not keys:
            failures.append(
                f"{rel}: لم تُقرأ منه أي مفاتيح جسمٍ — إمّا غابت `messageFromBody` "
                "أو تغيّر شكلها فتعطّل الفحص. "
                "بوّابةٌ لا تقرأ ملفاً لا تُبلِّغ أنه نظيف."
            )
            continue
        unknown = sorted(keys - emitted)
        if unknown:
            failures.append(
                f"{rel}: يقرأ مفاتيح لا يُخرجها المعالج: {', '.join(unknown)} — "
                "هذا هو عطب «Login failed» بعينه (عقدٌ مُعلَن بنصفه)."
            )
    return failures


def _check_clients() -> list[str]:
    """يتحقّق من وجود كل عميل مُعلَن ومن خلوّه من الإنجليزية في مسارات الخطأ."""
    failures: list[str] = []
    for client in CLIENT_PATHS:
        if not client.exists():
            failures.append(f"عميلٌ مُعلَن غير موجود: {client.relative_to(REPO_ROOT)}")
            continue
        try:
            offences = _english_fallbacks(client)
        except _ParseError as exc:
            failures.append(f"{client.relative_to(REPO_ROOT)}: {exc}")
            continue
        failures.extend(
            f"{offence} (سطر {line}) — سلسلة إنجليزية تصل الطالب في مسار خطأ. "
            "استعمل `readApiError(res, '<رسالة عربية>')`."
            for offence, line in offences
            if offence not in _FROZEN_DEBT
        )
    return failures


def _check_tables() -> list[str]:
    """يتحقّق من تطابق جداول الترجمة عبر النسخ الثلاث.

    ``ValueError`` من :func:`_js_tables` (مدخلٌ لم يُفهَم) يُحوَّل إلى فشلٍ
    مقروء بدل traceback: البوّابة تفشل بوضوح، لا بصخب.
    """
    try:
        return _compare_tables()
    except ValueError as exc:
        return [str(exc)]


def _compare_tables() -> list[str]:
    """يقارن جداول المصدر بجداول المرآتين."""
    source_tables = _js_tables(TABLE_SOURCE)
    missing_here = [name for name in TABLE_NAMES if name not in source_tables]
    if missing_here:
        return [
            f"{TABLE_SOURCE.relative_to(REPO_ROOT)}: جدولٌ قانوني مفقود {missing_here} — "
            "المصدر بلا جدول يعني بوّابةً تقارن العدم."
        ]

    failures: list[str] = []
    for mirror in TABLE_MIRRORS:
        mirror_tables = _js_tables(mirror)
        rel = mirror.relative_to(REPO_ROOT)
        for name in TABLE_NAMES:
            if name not in mirror_tables:
                failures.append(f"{rel}: الجدول `{name}` مفقود في المرآة.")
                continue
            failures.extend(
                f"{rel}: {problem} — المرآة تخالف "
                f"{TABLE_SOURCE.relative_to(REPO_ROOT)} (قاعدة D-013)."
                for problem in _table_diff(name, source_tables[name], mirror_tables[name])
            )
    return failures


def _check_stale_debt() -> list[str]:
    """الدَّين يتقلّص فقط: مدخلٌ لم يعد فيه خرق يجب أن يُحذَف."""
    live = {offence for client in CLIENT_PATHS for offence in _english_fallbacks(client)}
    return [
        f"دَين مُجمَّد لم يعد موجوداً: {entry} — احذفه من `_FROZEN_DEBT` "
        "(الدَّين يتقلّص فقط، والاستثناء الميت يُخفي عودة العطب)."
        for entry in _FROZEN_DEBT
        if entry not in live
    ]


def _mirror_check() -> list[str]:
    """`detail` و`message` يجب أن يُسنَدا من نفس القيمة."""
    if _detail_mirrors_message():
        return []
    return [
        "`detail` و`message` لا يُسنَدان من نفس القيمة في `build_error_payload` — "
        "قيمتان لنفس المعنى تعيدان إنتاج عطب «Login failed» (D-192)."
    ]


def main() -> int:
    emitted = _handler_emitted_keys()
    failures = (
        _check_handler_keys(emitted)
        + _check_client_keys(emitted)
        + _mirror_check()
        + _check_clients()
        + _check_tables()
        + _check_stale_debt()
    )

    for failure in failures:
        print(f"❌ {failure}")

    if failures:
        print(f"\n❌ check_error_contract_parity: {len(failures)} violation(s).")
        return 1

    print(
        f"✅ check_error_contract_parity: المعالج يُخرج {len(emitted)} مفتاحاً، "
        f"و{len(CLIENT_PATHS)} عملاء يقرؤونه، وجداول الترجمة متطابقة عبر "
        f"{len(TABLE_MIRRORS) + 1} نسخ، وصفر سلسلة إنجليزية في مسارات الخطأ."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run_gate(main))
