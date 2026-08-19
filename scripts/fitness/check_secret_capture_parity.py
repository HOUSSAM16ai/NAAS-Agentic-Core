#!/usr/bin/env python3
"""بوّابة تكافؤ التقاط السرّ — D-268 / ISS-191.

## لماذا هذه البوّابة موجودة

طلبُ المالك كان بسيطاً: «اجعل `HONCHO_API_KEY` يُلتقَط آلياً 100% مثل Supabase
وOpenRouter». والقياس الحيّ (2026-08-19) أثبت أنّ **«مثل OpenRouter» ليس شيئاً واحداً**:
السرّ يعبر **عشرة أبواب** من حساب GitHub إلى العملية، والأبواب لم تكن تتّفق أصلاً.

ما قيس على تسعة أسرار × عشرة أبواب:

* `SUPABASE_EDGE_FUNCTION_URL/KEY` غائبان عن `devcontainer.json:remoteEnv` بينما
  `supervisor.sh` يحقنهما و`secrets.env.example` يوثّقهما. أي أنّ ضبطهما كسرَّي
  Codespaces **لا يصل الحاوية أبداً**: حاضرٌ في الحساب، غائبٌ عن العملية — وهو أسوأ
  من الغياب لأنه يُقرأ حضوراً.
* `TAVILY_API_KEY` يعبر ستّة أبواب و**بلا حقلٍ في `AppSettings`**، فكان يُقرأ بـ
  `os.environ` في موضعين داخل `app/` — خرقاً مباشراً لقاعدة CLAUDE.md §6
  («⛔ لا `os.environ` في كود التطبيق»). القاعدة كانت **نثراً بلا فارض**: صنف العطب
  الذي عالجه D-188، ونفس شكل ISS-148 (فارضٌ بلا مرمى).
* `OPENAI_API_KEY` غائبٌ عن كل القوالب.
* `FIRECRAWL_API_KEY` يُقرأ في `app/` **ولا بابَ يلتقطه** — فيقرأ `None` دائماً.

ولا مصدرَ واحداً يقول «ما هي أسرار التشغيل؟». فكلّ سرٍّ يُضاف حيث تذكّر كاتبُه ويُنسى
حيث لم يتذكّر — وهو بالضبط ما أنتج الصفوف الناقصة أعلاه.

`config/secret_catalog.json` هو ذلك المصدر (نمط D-186 للنيّة · D-193 للمنهاج ·
D-202 للنماذج)، وهذه البوّابة تجعل البابَ المنسيّ **مستحيلاً** لا «مكروهاً».

## ما تفرضه

1. **التغطية:** كل سرٍّ حاضرٌ عند كل بابٍ يُصرِّحه، بالشكل الذي يُصرِّحه الباب.
2. **ثنائية الاتجاه:** اسمُ مفتاحٍ خارجي (`*_API_KEY`) يظهر عند بابٍ ولا صفَّ له في
   الكتالوج ولا هو رديفٌ مُعلَن ⇒ أحمر. (لا سرَّ خفيّ.)
3. **الأبواب مُعلَنة لا مُكتشَفة:** كل بابٍ مسارُه موجود، وشكلُه من الأشكال التي
   تعرفها هذه البوّابة. شكلٌ مجهول ⇒ أحمر، لا تخطٍّ صامت.
4. **القارئ القانوني:** كل سرٍّ له حقلٌ في `AppSettings` أو `no_reader_reason_ar`
   منطوق؛ و⛔ لا قراءة `os.environ`/`os.getenv` لسرٍّ مُكتلَج داخل `app/`.
   الدَّين المُجمَّد **فارغ** ويتقلّص في الاتجاهين.
5. **الأنماط مُشتقّة:** `check_no_committed_secrets` تقرأ أنماط الكتالوج ولا تكتبها
   يدوياً — كمّيةٌ واحدة بمصدرين تتفرّق (D-192).

**صدق التحليل (D-208):** ملفٌّ يتعذّر تحليله يُبلَّغ عنه انتهاكاً — ⛔ لا
`except SyntaxError: return []`. بوّابةٌ لا تقرأ ملفاً لا تُبلِّغ أنه نظيف.

**لا تُستورد من `app/`** — نصّية خالصة تعمل في بيئةٍ متدهورة.
Exit 0 = نظيف · 1 = انتهاك.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG = REPO_ROOT / "config" / "secret_catalog.json"
SETTINGS = REPO_ROOT / "app" / "core" / "settings" / "base.py"
COMMITTED_SECRETS_GATE = REPO_ROOT / "scripts" / "fitness" / "check_no_committed_secrets.py"
APP_TREE = REPO_ROOT / "app"

#: الدَّين المُجمَّد: مواضع `os.environ` لسرٍّ مُكتلَج داخل `app/` ما زالت قائمة.
#: **يبدأ فارغاً** — المواضع الثلاثة المقيسة أُصلحت في D-268 نفسه. ويتقلّص في
#: الاتجاهين: موضعٌ جديد أحمر، وموضعٌ أُغلق بلا حذفه من هنا أحمر أيضاً (نمط
#: `check_correlated_http` — دَينٌ أُغلق بلا تحديث الرقم كذبٌ كالدَّين المكتوم).
FROZEN_ENV_READ_DEBT: frozenset[str] = frozenset()

#: **القارئ القانوني نفسه** — حزمة الإعدادات هي من يقرأ البيئة بالتعريف، فمنعُها من
#: ذلك يعني منعَ قراءة الإعداد أصلاً. وقراءتها وقت الاستيراد ليست سهواً بل قانوناً
#: مكتوباً في CLAUDE.md §0: «Process env wins over `.env` at module import time» —
#: `base.py` يقرأ `APP_DATABASE_URL` **قبل** أن تقرأ pydantic-settings الملفّ، وبلا
#: ذلك يُقلع التطبيق على قاعدةٍ غير التي ضبطها المُشغِّل. استثناءٌ منطوق لا صامت
#: (D-208 البند 7)، وهو **موطنٌ واحد** لا قائمةُ إعفاءاتٍ تتمدّد.
LAWFUL_READER_PACKAGE = "app/core/settings/"

#: اسمُ مفتاحٍ خارجي. ضيّقٌ عمداً: `*_API_KEY` وحده يعني اعتماداً يُصدره طرفٌ خارجي،
#: بينما `POSTGRES_PASSWORD` وأخواته إعدادُ مكدّسٍ داخلي لا سرَّ مورَّد. نمطٌ فضفاض
#: يُنتج ضجيجاً، والضجيج يُعلِّم الناس تجاهل البوّابة.
_EXTERNAL_KEY_NAME = re.compile(r"\b([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*_API_KEY)\b")

_FAILURES: list[str] = []


def _fail(msg: str) -> None:
    _FAILURES.append(msg)
    print(f"❌ {msg}")


def _ok(msg: str) -> None:
    print(f"✅ {msg}")


# ─────────────────────────────────────────────────────────────────────────────
# أشكال الارتباط عند كل باب
# ─────────────────────────────────────────────────────────────────────────────
def _form_json_key(text: str, name: str) -> bool:
    """`"NAME": "${localEnv:NAME}"` في devcontainer.json."""
    return f'"{name}"' in text


def _form_shell_set_env_key(text: str, name: str) -> bool:
    """`_set_env_key "NAME" "$NAME"` في supervisor.sh — الحقن الفعلي لا الذِّكر."""
    return f'_set_env_key "{name}"' in text


def _form_dotenv_assignment(text: str, name: str) -> bool:
    """`NAME=...` على أوّل السطر في قالب dotenv."""
    return re.search(rf"(?m)^{re.escape(name)}=", text) is not None


def _form_dotenv_or_commented(text: str, name: str) -> bool:
    """كسابقه، ويقبل الشكل المُعلَّق `# NAME=` للمفاتيح الاختيارية."""
    return re.search(rf"(?m)^#?\s*{re.escape(name)}=", text) is not None


def _form_shell_assignment(text: str, name: str) -> bool:
    """`NAME_V="${NAME:-}"` أو `echo "NAME=..."` في جسر compose."""
    return f"{name}=" in text or f"{name}:-" in text


def _form_pydantic_field(text: str, name: str) -> bool:
    """`NAME: str | None = Field(...)` داخل AppSettings."""
    return re.search(rf"(?m)^\s*{re.escape(name)}\s*:", text) is not None


def _form_yaml_key(text: str, name: str) -> bool:
    """`NAME: value` في workflow أو compose."""
    return re.search(rf"(?m)^\s*{re.escape(name)}:", text) is not None


_FORMS = {
    "json_key": _form_json_key,
    "shell_set_env_key": _form_shell_set_env_key,
    "dotenv_assignment": _form_dotenv_assignment,
    "dotenv_or_commented": _form_dotenv_or_commented,
    "shell_assignment": _form_shell_assignment,
    "pydantic_field": _form_pydantic_field,
    "yaml_key": _form_yaml_key,
}


def _load_catalog() -> dict:
    if not CATALOG.is_file():
        _fail(f"الكتالوج مفقود: {CATALOG.relative_to(REPO_ROOT)} — لا مصدرَ يُقرأ.")
        return {}
    try:
        return json.loads(CATALOG.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _fail(f"الكتالوج غير قابل للقراءة ({exc}) — بوّابةٌ لا تقرأ مصدرها لا تُبرِّئ الشجرة.")
        return {}


def _door_texts(doors: dict) -> dict[str, str]:
    """نصّ كل بابٍ مقروءاً مرّة. بابٌ مفقود انتهاكٌ لا تخطٍّ (البند 3)."""
    texts: dict[str, str] = {}
    for door_id, meta in doors.items():
        path = REPO_ROOT / meta["path"]
        if not path.is_file():
            _fail(f"الباب «{door_id}» يشير إلى مسارٍ غير موجود: {meta['path']} (ISS-149).")
            continue
        if meta.get("form") not in _FORMS:
            _fail(
                f"الباب «{door_id}» شكلُه {meta.get('form')!r} وهو غير معروفٍ لهذه البوّابة.\n"
                f"   شكلٌ مجهول يعني باباً لا يُفحَص — والصمت يُقرأ نجاحاً (D-207)."
            )
            continue
        texts[door_id] = path.read_text(encoding="utf-8")
    return texts


# ─────────────────────────────────────────────────────────────────────────────
# البند 1 — التغطية
# ─────────────────────────────────────────────────────────────────────────────
def _check_coverage(catalog: dict, texts: dict[str, str]) -> None:
    doors: dict = catalog["doors"]
    all_ids = set(doors)
    for secret in catalog["secrets"]:
        name = secret["name"]
        required = list(secret.get("doors", []))
        skipped: dict = secret.get("doors_not_applicable", {})

        unknown = (set(required) | set(skipped)) - all_ids
        if unknown:
            _fail(f"{name}: بابٌ غير مُعلَن {sorted(unknown)} — الأبواب مُعلَنة لا مخترَعة.")
        both = set(required) & set(skipped)
        if both:
            _fail(f"{name}: بابٌ مطلوبٌ وغير منطبقٍ معاً {sorted(both)} — تصنيفٌ يناقض نفسه.")
        unclassified = all_ids - set(required) - set(skipped)
        if unclassified:
            _fail(
                f"{name}: أبوابٌ بلا تصنيف {sorted(unclassified)}.\n"
                f"   ⛔ الخانة الفارغة تُقرأ نجاحاً — صنِّفها مطلوبةً أو صرِّح سببَ عدم انطباقها."
            )
        for door_id, reason in skipped.items():
            if not str(reason).strip():
                _fail(f"{name}: الباب «{door_id}» غير منطبقٍ بلا سبب — الغياب يُعلَن (D-206 L11).")

        for door_id in required:
            text = texts.get(door_id)
            if text is None:  # بابٌ فشل تحميله — أُبلِغ عنه أعلاه
                continue
            check = _FORMS[doors[door_id]["form"]]
            if not check(text, name):
                _fail(
                    f"{name} غائبٌ عن الباب «{door_id}» ({doors[door_id]['path']}).\n"
                    f"   سرٌّ يعبر بعض الأبواب لا كلَّها يصل في بيئةٍ ويختفي في أخرى بلا سببٍ ظاهر."
                )


# ─────────────────────────────────────────────────────────────────────────────
# البند 2 — ثنائية الاتجاه
# ─────────────────────────────────────────────────────────────────────────────
def _check_no_uncatalogued(catalog: dict, texts: dict[str, str]) -> None:
    known: set[str] = set()
    for secret in catalog["secrets"]:
        known.add(secret["name"])
        known.update(secret.get("aliases", []))

    for door_id, text in sorted(texts.items()):
        for found in sorted(set(_EXTERNAL_KEY_NAME.findall(text))):
            if found in known:
                continue
            _fail(
                f"الباب «{door_id}» يحمل مفتاحاً خارجياً بلا صفٍّ في الكتالوج: {found}.\n"
                f"   أضِف صفَّه في config/secret_catalog.json، أو أعلِنه رديفاً "
                f"(`aliases`) لسرٍّ قائم إن كان اسماً مُنطاقاً لنفس المفتاح."
            )


# ─────────────────────────────────────────────────────────────────────────────
# البند 4 — القارئ القانوني
# ─────────────────────────────────────────────────────────────────────────────
def _check_lawful_reader(catalog: dict, texts: dict[str, str]) -> None:
    settings_text = texts.get("app_settings", "")
    for secret in catalog["secrets"]:
        name = secret["name"]
        reader = secret.get("lawful_reader")
        if reader is None:
            if not str(secret.get("no_reader_reason_ar", "")).strip():
                _fail(f"{name}: بلا قارئٍ قانوني وبلا سبب منطوق — الغياب يُعلَن (D-206 L11).")
            continue
        if settings_text and not _form_pydantic_field(settings_text, reader):
            _fail(
                f"{name}: القارئ القانوني المُعلَن «{reader}» غير موجودٍ في AppSettings.\n"
                f"   خريطةٌ تكذب أسوأ من غياب الخريطة (ISS-149)."
            )


def _catalogued_names(catalog: dict) -> set[str]:
    names: set[str] = set()
    for secret in catalog["secrets"]:
        names.add(secret["name"])
        names.update(secret.get("aliases", []))
    return names


class _EnvReadVisitor(ast.NodeVisitor):
    """يجمع أسماء المتغيّرات المقروءة بـ`os.environ[...]` / `os.environ.get` / `os.getenv`."""

    def __init__(self) -> None:
        self.names: list[tuple[int, str]] = []

    def _record(self, node: ast.AST, arg: ast.expr) -> None:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            self.names.append((getattr(node, "lineno", 0), arg.value))

    def visit_Subscript(self, node: ast.Subscript) -> None:
        target = node.value
        if (
            isinstance(target, ast.Attribute)
            and target.attr == "environ"
            and isinstance(target.value, ast.Name)
            and target.value.id == "os"
        ):
            self._record(node, node.slice)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Attribute) and node.args:
            is_getenv = (
                func.attr == "getenv" and isinstance(func.value, ast.Name) and func.value.id == "os"
            )
            is_environ_get = (
                func.attr == "get"
                and isinstance(func.value, ast.Attribute)
                and func.value.attr == "environ"
            )
            if is_getenv or is_environ_get:
                self._record(node, node.args[0])
        self.generic_visit(node)


def _check_no_env_reads(catalog: dict) -> None:
    """⛔ لا قراءة `os.environ` لسرٍّ مُكتلَج داخل `app/` (CLAUDE.md §6)."""
    catalogued = _catalogued_names(catalog)
    hits: set[str] = set()

    for path in sorted(APP_TREE.rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel.startswith(LAWFUL_READER_PACKAGE):
            continue
        source = path.read_text(encoding="utf-8", errors="ignore")
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            # صدق التحليل (D-208): ملفٌّ لا يُقرأ يُبلَّغ عنه، ولا يُعَدّ نظيفاً.
            _fail(f"{rel}: تعذّر تحليله ({exc.msg}) — بوّابةٌ لا تقرأ ملفاً لا تشهد بنظافته.")
            continue
        visitor = _EnvReadVisitor()
        visitor.visit(tree)
        for line_no, var in visitor.names:
            if var not in catalogued:
                continue
            hits.add(rel)
            if rel in FROZEN_ENV_READ_DEBT:
                continue
            _fail(
                f"{rel}:{line_no}: قراءةُ «{var}» بـ`os.environ` داخل `app/`.\n"
                f"   القارئ القانوني الوحيد هو `get_settings()` (CLAUDE.md §6) — "
                f"قراءةٌ موازية تعني إعدادين لقيمةٍ واحدة، ونسختان = رقمان لنفس السؤال."
            )

    for rel in sorted(FROZEN_ENV_READ_DEBT - hits):
        _fail(
            f"{rel} نظيفٌ الآن — احذفه من FROZEN_ENV_READ_DEBT.\n"
            f"   دَينٌ أُغلق بلا تحديث القائمة كذبٌ كالدَّين المكتوم (نمط check_correlated_http)."
        )


# ─────────────────────────────────────────────────────────────────────────────
# البند 5 — الأنماط مُشتقّة لا مكتوبة
# ─────────────────────────────────────────────────────────────────────────────
def _check_patterns_derived(catalog: dict) -> None:
    if not COMMITTED_SECRETS_GATE.is_file():
        _fail("`check_no_committed_secrets.py` مفقود — البند 5 بلا مرمى.")
        return
    gate_text = COMMITTED_SECRETS_GATE.read_text(encoding="utf-8")

    if "secret_catalog" not in gate_text:
        _fail(
            "`check_no_committed_secrets.py` لا يقرأ `config/secret_catalog.json`.\n"
            "   الأنماط تُشتَقّ من الكتالوج — قائمتان لكمّيةٍ واحدة تتفرّقان (D-192)."
        )

    for secret in catalog["secrets"]:
        pattern = secret.get("value_pattern")
        if pattern is None:
            if not str(secret.get("no_pattern_reason_ar", "")).strip():
                _fail(f"{secret['name']}: بلا نمطٍ وبلا سبب منطوق — الغياب يُعلَن (D-206 L11).")
            continue
        try:
            re.compile(pattern)
        except re.error as exc:
            _fail(f"{secret['name']}: `value_pattern` لا يُصرَّف ({exc}) — نمطٌ ميت لا يحرس شيئاً.")
            continue
        if pattern in gate_text:
            _fail(
                f"{secret['name']}: نمطُه مكتوبٌ **حرفياً** داخل `check_no_committed_secrets.py`.\n"
                f"   المصدر واحد: احذفه من البوّابة ودَعها تقرؤه من الكتالوج."
            )


def _check_debt_declared(catalog: dict) -> None:
    debt = catalog.get("unenforced_debt", {})
    if not isinstance(debt, dict):
        _fail("`unenforced_debt` يجب أن يكون كائناً {اسم: سبب}.")
        return
    for key, reason in debt.items():
        if not str(reason).strip():
            _fail(f"`unenforced_debt[{key}]` بلا سببٍ منطوق — الدَّين يُعلَن أو لا يُقبَل.")


def main() -> int:
    catalog = _load_catalog()
    if not catalog:
        return 1

    texts = _door_texts(catalog["doors"])
    _check_coverage(catalog, texts)
    _check_no_uncatalogued(catalog, texts)
    _check_lawful_reader(catalog, texts)
    _check_no_env_reads(catalog)
    _check_patterns_derived(catalog)
    _check_debt_declared(catalog)

    if _FAILURES:
        print(f"\n❌ secret-capture-parity: {len(_FAILURES)} انتهاكاً.")
        return 1

    doors = len(catalog["doors"])
    secrets = len(catalog["secrets"])
    _ok(f"كل سرٍّ عبر كل بابٍ يُصرِّحه ({secrets} سرّاً × {doors} أبواب، كل خانةٍ مُصنَّفة)")
    _ok("لا مفتاحَ خارجيٍّ بلا صفٍّ في الكتالوج (التغطية ثنائية الاتجاه)")
    _ok("كل سرٍّ له قارئٌ قانوني أو سببٌ منطوق — و⛔ صفر `os.environ` في `app/`")
    _ok("أنماط الأسرار مُشتقّة من الكتالوج لا مكتوبةً في البوّابة")
    print("\n✅ secret-capture-parity: البابُ المنسيّ مستحيل، لا مكروه.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
