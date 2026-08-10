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
_JS_TABLE = re.compile(r"(?:export\s+)?const\s+(\w+)\s*=\s*\{(.*?)\n\s*\};", re.DOTALL)

#: `key: 'value',` — المفتاح عاريًا أو مقتبَساً، والقيمة بعلامة اقتباس مفردة.
_JS_ENTRY = re.compile(r"^\s*['\"]?([\w]+)['\"]?\s*:\s*'((?:[^'\\]|\\.)*)'", re.MULTILINE)


def _js_tables(path: Path) -> dict[str, dict[str, str]]:
    """يستخرج جداول الترجمة من ملفّ JS كقواميس بايثون."""
    source = _strip_comments(path.read_text(encoding="utf-8"))
    tables: dict[str, dict[str, str]] = {}
    for name, body in _JS_TABLE.findall(source):
        if name in TABLE_NAMES:
            tables[name] = dict(_JS_ENTRY.findall(body))
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

#: `setError(...)` أو `setError(await readApiError(...))` — نلتقط الوسائط كاملةً.
_SET_ERROR = re.compile(r"setError\s*\(([^;]*?)\)\s*;", re.DOTALL)

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


def _english_fallbacks(path: Path) -> list[str]:
    """يعيد سلاسل السقوط الإنجليزية الممنوعة داخل استدعاءات `setError`."""
    if not path.exists():
        return []
    source = _strip_comments(path.read_text(encoding="utf-8"))
    offences: list[str] = []
    for match in _SET_ERROR.finditer(source):
        argument = match.group(1)
        line = source[: match.start()].count("\n") + 1
        offences.extend(
            f"{path.relative_to(REPO_ROOT)}:{line}: setError(... '{banned}')"
            for banned in _BANNED_FALLBACKS
            if banned in argument
        )
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


def _check_clients() -> list[str]:
    """يتحقّق من وجود كل عميل مُعلَن ومن خلوّه من الإنجليزية في مسارات الخطأ."""
    failures: list[str] = []
    for client in CLIENT_PATHS:
        if not client.exists():
            failures.append(f"عميلٌ مُعلَن غير موجود: {client.relative_to(REPO_ROOT)}")
            continue
        failures.extend(
            f"{offence} — سلسلة إنجليزية تصل الطالب في مسار خطأ. "
            "استعمل `readApiError(res, '<رسالة عربية>')`."
            for offence in _english_fallbacks(client)
            if offence not in _FROZEN_DEBT
        )
    return failures


def _check_tables() -> list[str]:
    """يتحقّق من تطابق جداول الترجمة عبر النسخ الثلاث."""
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
