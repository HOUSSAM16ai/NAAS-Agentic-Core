#!/usr/bin/env python3
"""بوّابة تكافؤ الواجهة التوليدية — ثلاثة سجلّات تتطابق أو CI أحمر (D-230 · ISS-145).

## القانون الأوّل في الدستور كان الوحيد بلا فارض

`CLAUDE.md §0.6` المرحلة ١: «الطالب **يتفاعل مع كائنات** لا يقرأ جداراً نصّياً»، والدردشة
«سطح تسليم فقط». وفحصٌ حيّ على قاعدة الإنتاج (2026-08-08 · 2250 ردّاً) قال العكس:
**٩٫٧٪ فقط** من الردود تحمل كائناً تفاعلياً، والانحدار حيّ — 36.6٪ (يونيو) ← 6.2٪
(يوليو) ← **3.4٪** (أغسطس). لم يره أحد لأن **لا شيء كان يقيسه**.

## ثلاثة أعطالٍ مقيسة وُلدت منها البنود الثلاثة

**① عقدٌ مُعلَن بنصفه.** سبق أن كانت `math_explanation_card` مُسجَّلة في الواجهة وغائبة
عن عقد الخادم، فكان المُطبِّع يرفضها ولا تصل الطالب أبداً (D-192). الاسم يجب أن يوجد في
**الطرفين** أو في لا طرف.

**② مكوّنٌ يصل ولا يُرسَم.** `worked_example_card` وصل الإنتاج **٧ مرّات بمحتوى فارغ**
وهو غير مُسجَّل في أيّ من السجلَّين — فرأى الطالب «تعذّر عرض المكوّن التفاعلي» ولا شيء
غيره. وISS-145 أُغلق «بالتفنيد» بادّعاء `truly_silent = 0` لأنه فحص أنّ مكوّناً
**مُرفَق** لا أنه **قابل للرسم**. الفحص الصحيح: **٧ أدوارٍ صامتة فعلاً**.
⛔ والاسم نفسه **محظورٌ بـD-115** (المثال المكشوف يخرق القاعدة الذهبية D-113) — فيُحرَس
هنا على **الطرفين**، بينما `check_skills_doctrine` يحرس الخادم وحده.

**③ إعلانٌ بلا باعث (زومبي).** `bkt_hint_display` (١٠٥ صفوف في الإنتاج) و
`learning_path_card` (٣٩ صفّاً) ما زالا مُعلَنَين في العقد ومُسجَّلَين في الواجهة، بينما
**لا سطر في المستودع كلّه يبثّهما** — بواعثهما أُزيلت وبقيت الإعلانات. وهذا وحده يفسّر
الانحدار: **١٥١ من ٢١٨** حدث واجهة تاريخي جاء من بواعثَ لم تعد موجودة.

سُلَّم الحقيقة (§6.6) يسمّي هذا `ZOMBIE`، وقاعدة D-016 تقول: **الأجهزة قبل التصوير**.
مكوّنٌ مُعلَنٌ بلا باعثٍ حيّ يجب أن يُعلَن دَيناً منطوقاً — لا أن يُقرأ كأنه قدرةٌ قائمة.

⛔ **الدَّين يتقلّص في الاتجاهين** (D-189): إعلانٌ جديد بلا باعث ⇒ أحمر، ومدخلُ دَينٍ
وُصِل باعثُه وبقي مكتوباً ⇒ أحمر أيضاً.

⛔ **ولا `except SyntaxError: return []`** (D-208 بند ٦).

تُشغَّل ضمن وظيفة `guardrails` في `.github/workflows/ci.yml`.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

BACKEND_CONTRACT = REPO_ROOT / "app/contracts/streaming.py"
FRONTEND_RENDERER = REPO_ROOT / "frontend/app/components/generative/GenerativeUIRenderer.jsx"
GENERATIVE_DIR = REPO_ROOT / "frontend/app/components/generative"

#: أسماء محظورة في **الطرفين**. المفتاح الاسم، والقيمة القرار الذي حظره.
BANNED_COMPONENTS: dict[str, str] = {
    "worked_example_card": (
        "D-115: المثال المكشوف يخرق القاعدة الذهبية السقراطية (D-113) — "
        "لا يُكشَف ما يستطيع الطالب توليده. وصل الإنتاج ٧ مرّات بمحتوى فارغ (ISS-145)"
    ),
}

#: إعلانٌ بلا باعثٍ حيّ — دَينٌ **منطوق** يتقلّص فقط.
#:
#: هذان مُصيَّران فعلاً في الواجهة (`BktMasteryCard` · `LearningPathCard`) وكانا يصلان
#: الطالب في نافذة يونيو 2026، ثمّ أُزيل باعثاهما وبقيت الإعلانات. لا يُحذفان لأن
#: المُصيِّر سليمٌ ومطلوب، ولا يُدَّعى أنهما يعملان — يُعلَنان دَيناً حتى يُعاد وصلهما.
_EMITTER_DEBT: dict[str, str] = {
    "bkt_hint_display": (
        "١٠٥ صفوف إنتاج؛ الباعث `_evaluate_and_emit_bkt` أُزيل ولم يبقَ إلّا ذكرُه "
        "في تعليقٍ بـtransport.py. المُصيِّر `BktMasteryCard.jsx` سليم"
    ),
    "learning_path_card": (
        "٣٩ صفّاً إنتاجياً؛ بلا باعثٍ في المستودع كلّه. المُصيِّر `LearningPathCard.jsx` سليم"
    ),
}

_REGISTRY_KEY = re.compile(r"^\s{4}([a-z][a-z0-9_]*)\s*:", re.MULTILINE)
_IMPORTED = re.compile(r"^import\s+\{\s*([A-Za-z0-9_]+)\s*\}\s+from\s+'\./([^']+)'", re.M)
_EMITTED = re.compile(r'"component"\s*:\s*"([a-z][a-z0-9_]*)"')

_SCAN_ROOTS: tuple[str, ...] = ("app", "microservices", "shared")


class ParityReadError(RuntimeError):
    """تعذّرت القراءة/التحليل — يُعلَن ولا يُبتلَع (D-208)."""


def _read(path: Path) -> str:
    if not path.is_file():
        raise ParityReadError(f"ملفٌّ مفقود: {path.relative_to(REPO_ROOT)}")
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover
        raise ParityReadError(f"تعذّرت قراءة {path}: {exc}") from exc


def _backend_components() -> set[str]:
    """يقرأ `KNOWN_UI_COMPONENTS` بـAST لا بـgrep — النصّ يكذب، الشجرة لا."""
    source = _read(BACKEND_CONTRACT)
    try:
        tree = ast.parse(source, filename=str(BACKEND_CONTRACT))
    except SyntaxError as exc:
        raise ParityReadError(f"{BACKEND_CONTRACT.name}: تعذّر التحليل — {exc}") from exc

    for node in ast.walk(tree):
        targets = (
            list(node.targets)
            if isinstance(node, ast.Assign)
            else [node.target]
            if isinstance(node, ast.AnnAssign)
            else []
        )
        if not any(isinstance(t, ast.Name) and t.id == "KNOWN_UI_COMPONENTS" for t in targets):
            continue
        value = node.value
        # frozenset({...}) — الوسيط الأوّل مجموعة حرفيات.
        if isinstance(value, ast.Call) and value.args:
            value = value.args[0]
        if isinstance(value, ast.Set | ast.List | ast.Tuple):
            return {
                el.value
                for el in value.elts
                if isinstance(el, ast.Constant) and isinstance(el.value, str)
            }
    raise ParityReadError("KNOWN_UI_COMPONENTS غير موجودة أو غير قابلة للقراءة الثابتة")


def _frontend_components() -> tuple[set[str], dict[str, str]]:
    """مفاتيح `COMPONENT_REGISTRY` + خريطة المكوّن ← ملفّه المستورَد."""
    source = _read(FRONTEND_RENDERER)
    start = source.find("const COMPONENT_REGISTRY")
    if start == -1:
        raise ParityReadError("COMPONENT_REGISTRY غير موجودة في المُصيِّر")
    end = source.find("\n};", start)
    if end == -1:
        raise ParityReadError("تعذّر تحديد نهاية COMPONENT_REGISTRY")

    keys = set(_REGISTRY_KEY.findall(source[start:end]))
    imports = dict(_IMPORTED.findall(source))
    return keys, imports


def _emitted_components() -> dict[str, str]:
    """كل حرفية `"component": "<name>"` في شيفرة الخادم ← أوّل موضعٍ يبثّها."""
    found: dict[str, str] = {}
    for root in _SCAN_ROOTS:
        base = REPO_ROOT / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise ParityReadError(f"{path}: تعذّرت القراءة — {exc}") from exc
            for name in _EMITTED.findall(text):
                found.setdefault(name, str(path.relative_to(REPO_ROOT)))
    return found


def _check_both_sides_agree(backend: set[str], frontend: set[str]) -> list[str]:
    """① الطرفان يتطابقان — لا عقدٌ مُعلَنٌ بنصفه (D-192)."""
    return [
        f"{name!r}: في عقد الخادم وغائبٌ عن سجلّ التصيير.\n"
        f"     سيصل الطالبَ نصٌّ بديل بدل الكائن — عقدٌ مُعلَنٌ بنصفه."
        for name in sorted(backend - frontend)
    ] + [
        f"{name!r}: في سجلّ التصيير وغائبٌ عن عقد الخادم.\n"
        f"     سيرفضه المُطبِّع فلا يصل أبداً (نفس عطب D-192)."
        for name in sorted(frontend - backend)
    ]


def _check_banned(backend: set[str], frontend: set[str], emitted: dict[str, str]) -> list[str]:
    """② المحظور محظورٌ في الطرفين وفي البثّ."""
    problems: list[str] = []
    for name, reason in BANNED_COMPONENTS.items():
        for where, registry in (("عقد الخادم", backend), ("سجلّ التصيير", frontend)):
            if name in registry:
                problems.append(f"{name!r} محظور وموجودٌ في {where}.\n     {reason}")
        if name in emitted:
            problems.append(f"{name!r} محظورٌ ويُبَثّ من {emitted[name]}.\n     {reason}")
    return problems


def _check_no_zombie_declaration(backend: set[str], emitted: dict[str, str]) -> list[str]:
    """③ لا إعلان بلا باعث — والدَّين يتقلّص في الاتجاهين (D-189)."""
    problems: list[str] = []
    for name in sorted(backend):
        if name in emitted or name in BANNED_COMPONENTS or name in _EMITTER_DEBT:
            continue
        problems.append(
            f"{name!r}: مُعلَنٌ في العقد بلا أيّ باعثٍ في المستودع (إعلانٌ زومبي).\n"
            f"     إمّا يُوصَل باعثه، أو يُسجَّل في _EMITTER_DEBT بسببٍ منطوق. "
            f"الإعلان بلا باعث يُقرأ قدرةً قائمة وهو ليس كذلك (§6.6 · D-016)."
        )
    for name, reason in sorted(_EMITTER_DEBT.items()):
        if name in emitted:
            problems.append(
                f"{name!r}: صار له باعثٌ حيّ ({emitted[name]}) وما زال في _EMITTER_DEBT.\n"
                f"     احذف السطر — دَينٌ أُغلق وبقي مكتوباً كذبٌ صامت (D-189). [{reason}]"
            )
        elif name not in backend:
            problems.append(f"{name!r}: في _EMITTER_DEBT ولم يعد مُعلَناً في العقد — احذف السطر.")
    return problems


def _check_emitted_is_declared(
    backend: set[str], frontend: set[str], emitted: dict[str, str]
) -> list[str]:
    """④ كل ما يُبَثّ مُعلَنٌ في الطرفين."""
    problems: list[str] = []
    for name, where in sorted(emitted.items()):
        if name not in backend:
            problems.append(f"{name!r} يُبَثّ من {where} وهو غير مُعلَنٍ في عقد الخادم.")
        if name not in frontend:
            problems.append(f"{name!r} يُبَثّ من {where} وهو غير مُسجَّلٍ في المُصيِّر.")
    return problems


def _check_imports_resolve(imports: dict[str, str]) -> list[str]:
    """⑤ كل مكوّنٍ مستورَدٍ في المُصيِّر له ملفّ."""
    return [
        f"المُصيِّر يستورد {symbol!r} من './{rel}' والملفّ غير موجود.\n"
        f"     استيرادٌ مكسور يُسقِط الحزمة كلّها لا مكوّناً واحداً."
        for symbol, rel in sorted(imports.items())
        if not (GENERATIVE_DIR / f"{rel}.jsx").is_file()
    ]


def main() -> int:
    try:
        backend = _backend_components()
        frontend, imports = _frontend_components()
        emitted = _emitted_components()
    except ParityReadError as exc:
        print(f"❌ تكافؤ الواجهة التوليدية: {exc}")
        print("   بوّابةٌ لا تقرأ ملفاً لا تُبلِّغ أنه نظيف (D-208 بند ٦).")
        return 1

    problems = (
        _check_both_sides_agree(backend, frontend)
        + _check_banned(backend, frontend, emitted)
        + _check_no_zombie_declaration(backend, emitted)
        + _check_emitted_is_declared(backend, frontend, emitted)
        + _check_imports_resolve(imports)
    )

    if problems:
        print("❌ تكافؤ الواجهة التوليدية (D-230 · ISS-145) — مخالفات:\n")
        for item in problems:
            print(f"  • {item}")
        print(
            "\n   القاعدة: الاسم في عقد الخادم **و** سجلّ التصيير **و** له باعثٌ حيّ — "
            "أو يُعلَن دَيناً منطوقاً. الإرفاق ليس تسليماً."
        )
        return 1

    live = sorted(backend - set(_EMITTER_DEBT))
    print(
        f"✅ تكافؤ الواجهة التوليدية: {len(backend)} مكوّناً مُعلَناً في الطرفين · "
        f"{len(live)} منها بباعثٍ حيّ · {len(_EMITTER_DEBT)} دَينٌ منطوق · "
        f"{len(BANNED_COMPONENTS)} محظورٌ غائبٌ عن الطرفين."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
