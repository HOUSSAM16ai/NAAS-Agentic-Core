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

#: عملاء الواجهة الذين يقرؤون أجسام الأخطاء.
CLIENT_PATHS: tuple[Path, ...] = (
    REPO_ROOT / "frontend" / "app" / "utils" / "apiError.js",
    REPO_ROOT / "frontend" / "app" / "components" / "CogniForgeApp.jsx",
    REPO_ROOT / "frontend" / "public" / "js" / "legacy-app.jsx",
    REPO_ROOT / "app" / "static" / "js" / "legacy-app.jsx",
)

#: المفاتيح التي يجب أن يُخرجها المعالج دائماً.
REQUIRED_KEYS: frozenset[str] = frozenset(
    {"status", "detail", "message", "error_code", "data", "request_id", "timestamp"}
)

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


def _handler_emitted_keys() -> set[str]:
    """يستخرج مفاتيح جسم الخطأ من `build_error_payload` بـAST.

    يُقرأ من الشجرة لا بالنصّ: `grep` عن `"detail"` يطابق تعليقاً يشرح غيابها،
    وهو بالضبط الفخّ الذي يجعل البوّابة تشهد بما لم تقرأ (D-208).
    """
    tree = parse_source(HANDLER_PATH)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name == "build_error_payload"):
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Dict):
                return {
                    key.value
                    for key in sub.value.keys
                    if isinstance(key, ast.Constant) and isinstance(key.value, str)
                }
    return set()


def _detail_mirrors_message() -> bool:
    """هل `detail` و`message` يُسنَدان من نفس الاسم في باني الحمولة؟"""
    tree = parse_source(HANDLER_PATH)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name == "build_error_payload"):
            continue
        for sub in ast.walk(node):
            if not (isinstance(sub, ast.Return) and isinstance(sub.value, ast.Dict)):
                continue
            found: dict[str, str] = {}
            for key, value in zip(sub.value.keys, sub.value.values, strict=False):
                if (
                    isinstance(key, ast.Constant)
                    and key.value in ("detail", "message")
                    and isinstance(value, ast.Name)
                ):
                    found[key.value] = value.id
            return found.get("detail") is not None and found.get("detail") == found.get("message")
    return False


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
        for banned in _BANNED_FALLBACKS:
            if banned in argument:
                line = source[: match.start()].count("\n") + 1
                offences.append(f"{path.relative_to(REPO_ROOT)}:{line}: setError(... '{banned}')")
    return offences


def main() -> int:
    failures: list[str] = []

    emitted = _handler_emitted_keys()
    if not emitted:
        failures.append(
            "لم يُعثر على `build_error_payload` أو على قاموس إرجاعه في "
            f"{HANDLER_PATH.relative_to(REPO_ROOT)} — العقد بلا مصدر."
        )
    else:
        missing = REQUIRED_KEYS - emitted
        if missing:
            failures.append(
                "المعالج لا يُخرج مفاتيح إلزامية: "
                + ", ".join(sorted(missing))
                + " — كل مفتاحٍ يقرؤه عميلٌ يجب أن يُخرجه المعالج (ISS-152)."
            )

    if not _detail_mirrors_message():
        failures.append(
            "`detail` و`message` لا يُسنَدان من نفس القيمة في `build_error_payload` — "
            "قيمتان لنفس المعنى تعيدان إنتاج عطب «Login failed» (D-192)."
        )

    for client in CLIENT_PATHS:
        if not client.exists():
            failures.append(f"عميلٌ مُعلَن غير موجود: {client.relative_to(REPO_ROOT)}")
            continue
        for offence in _english_fallbacks(client):
            if offence in _FROZEN_DEBT:
                continue
            failures.append(
                f"{offence} — سلسلة إنجليزية تصل الطالب في مسار خطأ. "
                "استعمل `readApiError(res, '<رسالة عربية>')`."
            )

    stale = [
        entry
        for entry in _FROZEN_DEBT
        if entry
        not in {offence for client in CLIENT_PATHS for offence in _english_fallbacks(client)}
    ]
    for entry in stale:
        failures.append(
            f"دَين مُجمَّد لم يعد موجوداً: {entry} — احذفه من `_FROZEN_DEBT` "
            "(الدَّين يتقلّص فقط، والاستثناء الميت يُخفي عودة العطب)."
        )

    for failure in failures:
        print(f"❌ {failure}")

    if failures:
        print(f"\n❌ check_error_contract_parity: {len(failures)} violation(s).")
        return 1

    print(
        f"✅ check_error_contract_parity: المعالج يُخرج {len(emitted)} مفتاحاً، "
        f"و{len(CLIENT_PATHS)} عملاء يقرؤونه، وصفر سلسلة إنجليزية في مسارات الخطأ."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run_gate(main))
