#!/usr/bin/env python3
"""سلسلة التوريد تُبرَّد وتَصِف الموجود (D-270 L6).

**لماذا هذه البوّابة موجودة:**

معيار OpenHands في هذا الباب ثلاثة أشياء مجتمعة: **تبريدٌ** قبل الدمج
(``cooldown`` / ``exclude-newer = 7 days``)، و**تثبيتٌ حرفي** للتبعيات المباشرة،
و**إعدادٌ يصف ما هو موجود**. والقياس على هذا المستودع في 2026-08-19 أظهر أنّ
``.github/dependabot.yml`` كان يخرق الثلاثة معاً:

=========================================  ====================================================
الخرق                                       الأثر المقيس
=========================================  ====================================================
لا ``cooldown`` في أيّ منظومة                 نسخةٌ رُفعت قبل ساعة تُدمَج آلياً — وهو الباب
                                            الذي تدخل منه حزمةٌ مُختطَفة.
``directory: "/ai_service"``                 مجلّدٌ **غير موجود** — تغطيةٌ موعودة لا تحدث أبداً.
مجموعات ``flask*`` · ``chromadb*`` ·         **لا حزمة منها** في أيّ ``requirements*.txt``؛
``werkzeug`` · ``jinja2``                    الملفّ يصف نظاماً ليس هذا النظام.
``frontend/package.json`` بلا منظومة npm     ١٠ تبعيات واجهة **بلا أيّ تحديثٍ آلي** — والملفّ
                                            يبدو شاملاً فلا يسأل أحد.
``reviewers`` · ``assignees``                مفتاحان **مُهمَلان يتجاهلهما Dependabot بصمت**
                                            بينما ``.github/CODEOWNERS`` يغطّي المراجعة أصلاً.
=========================================  ====================================================

⚠️ **الفجوة الرابعة أخطرها**: الناقص يُلاحَظ، أمّا التغطية التي تبدو شاملة وليست كذلك
فلا يسألها أحد — نفس بنية ISS-191 (بابٌ منسيّ يُقرأ حضوراً).

**دَين التثبيت — لماذا ratchet لا منعٌ فوري:** القياس وجد **١٦٥** تبعية بايثون
و**٩** حزم npm بلا تثبيتٍ حرفي. فرضُ التثبيت دفعةً واحدة يعني ترقيةً جماعية غير
مُختبَرة عبر ثماني ملفّات — وهو أخطر من الدَّين نفسه. فالقائمة **مُجمَّدة وتتقلّص
فقط، وفي الاتجاهين**: تبعيةٌ جديدة غير مُثبَّتة ⇒ أحمر، ودَينٌ أُغلق بلا حذفه من
السجلّ ⇒ أحمر أيضاً (نمط ``check_correlated_http`` — D-189).
وثمن الإهمال مُثبَتٌ حيّاً في هذا المستودع: D-184 — نطاقٌ عائم لـ``ruff`` رقّى
المُدقِّق تحت المستودع، فاحمرّ ``main`` بلا تغيير سطرٍ واحد من الكود.

المصدر القانوني: ``docs/governance/SUPPLY_CHAIN.json``.
تُشغَّل ضمن وظيفة ``guardrails`` في ``.github/workflows/ci.yml``.
Exit 0 = نظيف · 1 = انتهاك.
"""

from __future__ import annotations

import fnmatch
import json
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
POLICY = REPO_ROOT / "docs" / "governance" / "SUPPLY_CHAIN.json"
FRONTEND_PKG = REPO_ROOT / "frontend" / "package.json"

_FAILURES: list[str] = []


def _fail(msg: str) -> None:
    _FAILURES.append(msg)
    print(f"❌ {msg}")


def _pass(msg: str) -> None:
    print(f"✅ {msg}")


def _requirement_name(spec: str) -> str:
    return re.split(r"[<>=!~\[; ]", spec.strip(), maxsplit=1)[0].strip()


def _python_dependencies() -> dict[str, list[str]]:
    """اسم الملفّ ⇒ أسماء تبعياته المباشرة (بلا سطور `-r` والتعليقات)."""
    result: dict[str, list[str]] = {}
    for path in sorted(REPO_ROOT.glob("requirements*.txt")):
        names: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.split("#")[0].strip()
            if stripped and not stripped.startswith("-"):
                names.append(_requirement_name(stripped))
        result[path.name] = names
    return result


def _npm_dependencies() -> dict[str, str]:
    if not FRONTEND_PKG.is_file():
        return {}
    package = json.loads(FRONTEND_PKG.read_text(encoding="utf-8"))
    return {
        name: version
        for key in ("dependencies", "devDependencies")
        for name, version in package.get(key, {}).items()
    }


# ──────────────────────────────────────────────────────────────────────────────
# ① إعداد Dependabot يصف ما هو موجود
# ──────────────────────────────────────────────────────────────────────────────
def _declared_directories(update: dict) -> list[str]:
    if "directories" in update:
        return list(update["directories"])
    return [update["directory"]] if "directory" in update else []


def _resolve(entry: str) -> list[Path]:
    """يوسّع `/microservices/*` إلى مجلّداتٍ فعلية؛ ويعيد المسار كما هو إن لم يكن نمطاً."""
    relative = entry.lstrip("/") or "."
    if any(ch in relative for ch in "*?["):
        return [p for p in REPO_ROOT.glob(relative) if p.is_dir()]
    target = REPO_ROOT / relative
    return [target] if target.is_dir() else []


def _check_cooldown(update: dict, label: str, required_days: int) -> None:
    days = (update.get("cooldown") or {}).get("default-days")
    if not isinstance(days, int) or days < required_days:
        _fail(f"{label}: `cooldown.default-days` غائب أو < {required_days} (القيمة: {days!r})")


def _check_deprecated_keys(update: dict, label: str, deprecated: tuple[str, ...]) -> None:
    for key in deprecated:
        if key in update:
            _fail(
                f"{label}: المفتاح `{key}` مُهمَل ويتجاهله Dependabot بصمت — "
                "احذفه (CODEOWNERS يغطّي المراجعة)"
            )


def _check_directories(update: dict, label: str) -> None:
    for entry in _declared_directories(update):
        if not _resolve(entry):
            _fail(f"{label}: `{entry}` لا يُطابق أيّ مجلّد موجود — تغطيةٌ موعودة لا تحدث")


def _check_group_patterns(update: dict, label: str, known: set[str]) -> None:
    for group, body in (update.get("groups") or {}).items():
        for pattern in body.get("patterns", []):
            if pattern == "*":
                continue
            if not any(fnmatch.fnmatch(name, pattern.lower()) for name in known):
                _fail(
                    f"{label} · المجموعة `{group}`: النمط `{pattern}` لا يطابق أيّ حزمةٍ "
                    "في المستودع — إعدادٌ يصف نظاماً آخر"
                )


def _check_one_update(
    update: dict,
    required_days: int,
    deprecated: tuple[str, ...],
    known_by_ecosystem: dict[str, set[str]],
) -> None:
    """كل قواعد L6 على منظومةٍ واحدة."""
    ecosystem = str(update.get("package-ecosystem", "?"))
    label = f"`{ecosystem}`"
    _check_cooldown(update, label, required_days)
    _check_deprecated_keys(update, label, deprecated)
    _check_directories(update, label)
    if (known := known_by_ecosystem.get(ecosystem)) is not None:
        _check_group_patterns(update, label, known)


def _load_dependabot(spec: dict) -> list[dict] | None:
    config_path = REPO_ROOT / spec.get("config_path", ".github/dependabot.yml")
    if not config_path.is_file():
        _fail(f"إعداد Dependabot مفقود: {spec.get('config_path')}")
        return None
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        # ⛔ ملفٌّ لم يُحلَّل لا يُشهَد له بالسلامة (D-208 §6).
        _fail(f"`dependabot.yml` ليس YAML صالحاً — لا يُعَدّ نظيفاً: {exc}")
        return None
    updates = (config or {}).get("updates", [])
    if not updates:
        _fail("`dependabot.yml` بلا أيّ `updates` — إعدادٌ يُقرأ حمايةً ولا يحرس شيئاً")
        return None
    return list(updates)


def _known_packages() -> dict[str, set[str]]:
    """الحزم الحقيقية لكل منظومةٍ يمكن التحقّق من أنماطها."""
    return {
        "pip": {name.lower() for names in _python_dependencies().values() for name in names},
        "npm": {name.lower() for name in _npm_dependencies()},
    }


def _check_dependabot(policy: dict) -> None:
    spec = policy.get("dependabot", {})
    updates = _load_dependabot(spec)
    if updates is None:
        return

    required_days = int(spec.get("required_cooldown_days", 7))
    deprecated = tuple(spec.get("deprecated_keys", ()))
    known = _known_packages()
    for update in updates:
        _check_one_update(update, required_days, deprecated, known)

    seen = {str(update.get("package-ecosystem", "?")) for update in updates}
    if missing := sorted(set(spec.get("required_ecosystems", {})) - seen):
        _fail(f"منظومات موجودة في المستودع وغير مُغطّاة: {missing} — فجوةٌ صامتة تُقرأ تغطية")

    if not _FAILURES:
        _pass(
            f"Dependabot يصف الموجود: {len(updates)} منظومة · تبريد ≥ {required_days} أيام · "
            "صفر مجلّدٍ وهمي · صفر نمطٍ بلا حزمة"
        )


# ──────────────────────────────────────────────────────────────────────────────
# ② دَين التثبيت — مُجمَّد، يتقلّص فقط، وفي الاتجاهين
# ──────────────────────────────────────────────────────────────────────────────
def _unpinned_name(line: str) -> str | None:
    """اسم الحزمة إن كان السطر متطلَّباً **غير مُثبَّت** — وإلّا `None`."""
    stripped = line.split("#", maxsplit=1)[0].strip()
    if not stripped or stripped.startswith("-"):
        return None
    if re.match(r"^[A-Za-z0-9_.\[\]-]+==[^,\s]+$", stripped):
        return None
    return _requirement_name(stripped)


def _actual_python_debt() -> dict[str, list[str]]:
    debt: dict[str, list[str]] = {}
    for path in sorted(REPO_ROOT.glob("requirements*.txt")):
        lines = path.read_text(encoding="utf-8").splitlines()
        if unpinned := [name for line in lines if (name := _unpinned_name(line))]:
            debt[path.name] = sorted(set(unpinned))
    return debt


def _actual_npm_debt() -> list[str]:
    return sorted(
        name for name, version in _npm_dependencies().items() if not re.match(r"^\d", version)
    )


def _diff(actual: set[str], declared: set[str], where: str) -> list[str]:
    problems = []
    if new := sorted(actual - declared):
        problems.append(f"{where}: تبعيات جديدة غير مُثبَّتة {new} — ثبّتها بـ`==`")
    if closed := sorted(declared - actual):
        problems.append(f"{where}: دَينٌ أُغلق بلا حذفه من السجلّ {closed} — حدِّث SUPPLY_CHAIN.json")
    return problems


def _check_pin_debt(policy: dict) -> None:
    declared = policy.get("pin_debt", {})
    declared_py: dict[str, list[str]] = declared.get("python", {})
    declared_npm: list[str] = declared.get("npm", {}).get("frontend/package.json", [])

    problems: list[str] = []
    actual_py = _actual_python_debt()
    for name in sorted(set(actual_py) | set(declared_py)):
        problems += _diff(set(actual_py.get(name, [])), set(declared_py.get(name, [])), name)
    problems += _diff(set(_actual_npm_debt()), set(declared_npm), "frontend/package.json")

    if problems:
        _fail("دَين التثبيت انحرف عن السجلّ (يتقلّص فقط — D-189): " + " · ".join(problems[:6]))
        return
    total = sum(len(v) for v in declared_py.values()) + len(declared_npm)
    _pass(f"دَين التثبيت مطابقٌ للسجلّ ولم يتّسع: {total} تبعيةً (بايثون + npm)")


def main() -> int:
    if not POLICY.is_file():
        print(f"❌ سياسة سلسلة التوريد مفقودة: {POLICY.relative_to(REPO_ROOT)}")
        return 1
    try:
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"❌ `SUPPLY_CHAIN.json` ليس JSON صالحاً: {exc}")
        return 1

    _check_dependabot(policy)
    _check_pin_debt(policy)

    if _FAILURES:
        print(f"\n❌ سلسلة التوريد (D-270 L6): {len(_FAILURES)} انتهاكاً")
        return 1
    print("\n✅ سلسلة التوريد (D-270 L6): مُبرَّدة، وتصف ما هو موجود.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
