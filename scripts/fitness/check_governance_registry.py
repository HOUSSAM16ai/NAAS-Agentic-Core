#!/usr/bin/env python3
"""بوّابة فرض الحوكمة — D-266 / ISS-186.

## لماذا هذه البوّابة موجودة

المستودع يفرض على **الكود** برهاناً ثلاثياً (§6.6): `import + call chain + runtime
evidence`. ولم يكن يفرض شيئاً من ذلك على **الفوارض نفسها**.

القياس الذي وُلدت منه (2026-08-16): من ٧٠ بوّابة على القرص، كانت **سبع** لا يشغّلها
أيّ workflow ولا أيّ اختبار — موجودةٌ ومذكورةٌ دستورياً و**ميتة**:
`check_contracts_verified` · `check_core_kernel_env_profile` · `check_import_boundaries` ·
`check_legacy_routes_monotonic` · `check_legacy_traffic_zero_window` ·
`check_secret_key_consistency` · `check_stategraph_runtime_backbone`.

وهذا بالضبط **الثمن الثاني** في `ENGINEERING_DOCTRINE.md`: «فارضٌ بلا مرمى» — نفس صنف
ISS-148 (عقودٌ خضراء ومسارُ التسريب خارج مرماها)، لكن على مستوى المنظومة كلّها. و
`check_spec_kit_governance` (L3) كان يفحص **الذِّكر + الوجود** ولا يفحص **التنفيذ**؛
فبوّابةٌ لا تعمل تجتاز فحص «لا بوّابة يتيمة» وهي ميتة.

و`scripts/run_fitness_gates.py` يقرأ الـworkflow، فبوّابةٌ غير مُدرَجة فيه **ميتة محلياً
أيضاً**: لا تحمي، ولا هي محايدة — تُعطي طمأنينةً كاذبة.

## ما تفحصه

1. **التنفيذ (الساق الثالثة):** كل `check_*.py` في `scripts/fitness/` و`tools/ci/` إمّا
   يُنفَّذ (مذكور في `.github/workflows/*.yml` أو في اختبارٍ تحت `tests/`/`scripts/ci/`
   يشغّله CI) وإمّا مُصرَّح في `unenforced_debt` بسببٍ منطوق. القائمة **تتقلّص فقط**:
   بوّابةٌ في الدَّين صارت تُنفَّذ ⇒ فشل حتى تُحذَف من الدَّين (نمط `check_correlated_http`
   ثنائي الاتجاه — دَينٌ أُغلق بلا تحديث الرقم كذبٌ أيضاً).
2. **الوجود:** كل فارضٍ يسمّيه السجلّ موجودٌ على القرص؛ وكل بوّابةٍ على القرص يسمّيها
   السجلّ (لا يتيمة ولا وهم).
3. **التغطية:** كل قسم `## 0.N.` في `CLAUDE.md` له صفٌّ في السجلّ، والعكس.
4. **الخريطة لا تكذب:** كل `law_docs`/`status_docs` موجودٌ فعلاً (ISS-149).
5. **الغياب يُعلَن:** صفٌّ بلا فوارض يجب أن يحمل `no_enforcer_reason_ar` غير فارغ
   (D-206 L11: الغياب لا يعني الغموض).
6. **لا رقمَ يدوياً:** `.memory/ci-gates.md` لا يكتب عدد البوّابات نصّاً — يُشتَقّ
   (يمدّد D-192).

**لا تُستورد من `app/`** (نمط `check_pedagogical_os.py`) — نصّية خالصة تعمل في بيئة
متدهورة. Exit 0 = نظيف · 1 = انتهاك.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REGISTRY = REPO_ROOT / "docs" / "governance" / "CONSTITUTION_REGISTRY.json"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
CI_GATES_DOC = REPO_ROOT / ".memory" / "ci-gates.md"

#: مواطن البوّابات. أيّ موطنٍ ثالث يجب أن يُضاف هنا صراحةً — لا اكتشافَ ضمني.
GATE_HOMES = ("scripts/fitness", "tools/ci")

#: أين يُعتبر ذِكرُ البوّابة **تنفيذاً**. الاختبارات تحت `tests/` يشغّلها `test-monolith`،
#: و`scripts/ci` يشغّلها نفس الوظيفة — فبوّابةٌ يستدعيها اختبار مُنفَّذة فعلاً.
EXECUTION_SOURCES = (".github/workflows", "tests", "scripts/ci")

_FAILURES: list[str] = []


def _fail(msg: str) -> None:
    _FAILURES.append(msg)
    print(f"❌ {msg}")


def _pass(msg: str) -> None:
    print(f"✅ {msg}")


def _gates_on_disk() -> dict[str, str]:
    """اسم الملفّ ⇒ مساره النسبي. الاسم هو المفتاح لأنه ما يُكتب في الوثائق."""
    found: dict[str, str] = {}
    for home in GATE_HOMES:
        directory = REPO_ROOT / home
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("check_*.py")):
            found[path.name] = f"{home}/{path.name}"
    return found


def _patterns_for(source: str) -> tuple[str, ...]:
    """أيّ لواحق تُقرأ في هذا الموطن — الـworkflows YAML وما عداها بايثون."""
    return ("*.yml", "*.yaml") if "workflows" in source else ("*.py",)


def _read_all(root: Path, patterns: tuple[str, ...]) -> list[str]:
    """نصوص كل الملفّات المطابقة تحت جذرٍ واحد."""
    return [
        path.read_text(encoding="utf-8", errors="ignore")
        for pattern in patterns
        for path in root.rglob(pattern)
    ]


def _execution_text() -> str:
    """نصّ كل ما قد يشغّل بوّابة — يُقرأ مرّة."""
    chunks: list[str] = []
    for source in EXECUTION_SOURCES:
        root = REPO_ROOT / source
        if root.is_dir():
            chunks.extend(_read_all(root, _patterns_for(source)))
    return "\n".join(chunks)


def _check_execution(gates: dict[str, str], registry: dict) -> None:
    executed_in = _execution_text()
    debt: dict = registry.get("unenforced_debt", {})
    if not isinstance(debt, dict):
        _fail("`unenforced_debt` يجب أن يكون كائناً {اسم البوّابة: السبب}")
        return

    _check_dead_gates(gates, debt, executed_in)
    _check_debt_honesty(gates, debt, executed_in)


def _check_dead_gates(gates: dict[str, str], debt: dict, executed_in: str) -> None:
    """الاتجاه الأوّل: بوّابةٌ على القرص لا يشغّلها شيء ولا هي مُصرَّحة."""
    dead = [name for name in gates if name not in executed_in and name not in debt]
    if dead:
        _fail(
            "بوّابات على القرص لا يشغّلها أيّ workflow ولا أيّ اختبار ولا هي مُصرَّحة "
            f"في `unenforced_debt`: {sorted(dead)} — فارضٌ بلا مرمى (D-207)"
        )
        return
    _pass(f"كل البوّابات الـ{len(gates)} مُنفَّذة فعلاً (workflow أو اختبار) — دَينٌ: {len(debt)}")


def _check_debt_honesty(gates: dict[str, str], debt: dict, executed_in: str) -> None:
    """الاتجاه الآخر: دَينٌ أُغلق بلا تحديث القائمة كذبٌ أيضاً (نمط `check_correlated_http`)."""
    closed = [name for name in debt if name in executed_in]
    if closed:
        _fail(f"بوّابات في `unenforced_debt` صارت تُنفَّذ — احذفها من الدَّين: {sorted(closed)}")

    ghost_debt = [name for name in debt if name not in gates]
    if ghost_debt:
        _fail(f"`unenforced_debt` يسمّي بوّابات غير موجودة: {sorted(ghost_debt)}")

    empty_reason = [name for name, reason in debt.items() if not str(reason).strip()]
    if empty_reason:
        _fail(f"دَينٌ بلا سببٍ منطوق: {sorted(empty_reason)} — الخانة الفارغة تُقرأ نجاحاً")


def _rows(registry: dict) -> list[dict]:
    return list(registry.get("core_doctrines", [])) + list(registry.get("constitutions", []))


def _check_enforcers_exist(gates: dict[str, str], registry: dict) -> None:
    named: set[str] = set()
    for row in _rows(registry):
        for enforcer in row.get("enforcers", []):
            named.add(enforcer)
            if enforcer not in gates:
                _fail(f"§{row.get('section')}: يسمّي فارضاً غير موجود `{enforcer}`")

    unnamed = sorted(name for name in gates if name not in named)
    if unnamed:
        # ليست كل بوّابةٍ تحرس دستوراً بعينه (بوّابات بنيوية عامّة)، لكن يجب أن تكون
        # مذكورةً في وثيقةٍ حاكمة — وهذا ما يفحصه `check_spec_kit_governance` (L3).
        # هنا نكتفي بالإبلاغ كي لا تُنسَخ المسؤولية في بوّابتين.
        print(f"ℹ️  {len(unnamed)} بوّابة بنيوية غير مربوطة بدستورٍ بعينه (يفحص ذِكرَها L3).")
    _pass(f"كل الفوارض المسمّاة في السجلّ موجودة ({len(named)} فارضاً)")


def _check_sections(registry: dict) -> None:
    text = CLAUDE_MD.read_text(encoding="utf-8")
    in_doc = {m.group(1) for m in re.finditer(r"^## (0(?:\.\d+)?)\.\s", text, flags=re.M)}
    in_registry = {str(row.get("section")) for row in _rows(registry)}

    missing = sorted(in_doc - in_registry, key=lambda s: [int(p) for p in s.split(".")])
    if missing:
        _fail(f"أقسام §0.x في CLAUDE.md بلا صفٍّ في السجلّ: {missing}")
    ghost = sorted(in_registry - in_doc)
    if ghost:
        _fail(f"صفوف في السجلّ تشير إلى أقسامٍ غير موجودة في CLAUDE.md: {ghost}")
    if not missing and not ghost:
        _pass(f"تغطية كاملة: {len(in_doc)} قسماً دستورياً ⇄ {len(in_registry)} صفّاً")


def _declared_doc_paths(registry: dict) -> list[tuple[str, str]]:
    """كل مسارٍ يعِد به السجلّ، مقروناً بقسمه: `(§0.x, path)` — مسحٌ نقيّ."""
    return [
        (str(row.get("section")), rel)
        for row in _rows(registry)
        for key in ("law_docs", "status_docs")
        for rel in row.get(key, [])
    ]


def _check_doc_paths(registry: dict) -> None:
    declared = _declared_doc_paths(registry)
    broken = [f"§{section} → {rel}" for section, rel in declared if not (REPO_ROOT / rel).exists()]
    if broken:
        _fail(f"مسارات وثائق غير موجودة (خريطةٌ تكذب — ISS-149): {broken}")
        return
    _pass(f"كل مسارات الوثائق الـ{len(declared)} تصل إلى ملفّات موجودة")


def _check_declared_absence(registry: dict) -> None:
    silent = [
        str(row.get("section"))
        for row in _rows(registry)
        if not row.get("enforcers") and not str(row.get("no_enforcer_reason_ar", "")).strip()
    ]
    if silent:
        _fail(f"صفوف بلا فارضٍ وبلا `no_enforcer_reason_ar`: {silent} — الغياب يُعلَن (D-206 L11)")
    else:
        _pass("كل صفٍّ بلا فارضٍ يُصرِّح سببه (L11)")


#: استثناءات **منطوقة** لا صامتة (D-208 §7). تتقلّص فقط: كلّ إدخالٍ يحمل سببه.
_PHANTOM_EXCEPTIONS = {
    "check_confusion_never_an_answer.py": "دالّة داخل scripts/fitness/check_pedagogical_os.py لا ملفّ",
    "check_db.py": "أداة تشخيصٍ مُصرَّح أنها محفوظة خارج المستودع (.memory/auth_runtime_truth.md)",
}

#: مواضع لا يُقرأ ذِكرُ البوّابة فيها **ادّعاءَ وجود**:
#: `tests/` تبني ملفّات وهمية عمداً (تجارب سلبية) · `docs/archive/` مُجمَّد ·
#: `tasks.md`/`roadmap.md` موطنا العمل المُخطَّط (D-209: الطموح يُصنَّف ولا يُكتَم) ·
#: `infra/` خطوط ML لها مساراتها الخاصّة · `scripts/misc/` أدوات عابرة.
_PHANTOM_SCAN_SKIP = (
    "tests/",
    "docs/archive/",
    "scripts/misc/",
    "node_modules/",
    ".git/",
    "infra/",
    ".memory/tasks.md",
    ".memory/roadmap.md",
)


#: إحالةٌ إلى بوّابة. مسبوقةً بمسارٍ **غير** موطن بوّابة (`/tmp/…` · `pipelines/steps/…`)
#: فهي ملفٌّ آخر يحمل الاسم نفسه، لا إحالةٌ إلى بوّابةٍ في هذا المستودع.
_GATE_REFERENCE = re.compile(r"(?<![\w/.-])(?:scripts/fitness/|tools/ci/)?(check_[a-z0-9_]+\.py)")


def _scannable_files() -> list[Path]:
    """كل ملفّ قد يحمل إحالةً إلى بوّابة، بعد استبعاد المواطن المُصرَّحة."""
    return [
        path
        for suffix in ("*.py", "*.md", "*.yml", "*.yaml")
        for path in REPO_ROOT.rglob(suffix)
        if not any(str(path.relative_to(REPO_ROOT)).startswith(skip) for skip in _PHANTOM_SCAN_SKIP)
    ]


def _gate_names_in(path: Path) -> set[str]:
    """أسماء البوّابات المذكورة في ملفٍّ واحد."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    return {match.group(1) for match in _GATE_REFERENCE.finditer(text)}


def _check_no_phantom_enforcers(gates: dict[str, str]) -> None:
    """بوّابةٌ تُذكَر ولا توجد — إحالةٌ وهمية تُقرأ حمايةً قائمة.

    D-265 (L3) يفحص هذا في **قائمةٍ ثابتة من الوثائق** فقط. والقياس (D-266) أثبت أنّ
    الوهم يعيش خارجها: `shared/curriculum/registry.py` كان يقول «تفرضه بوّابة
    `check_curriculum_single_source`» — **وهي لم تُكتب قطّ**، أي أنّ قانون D-193
    («تعريف المفهوم واحد») بقي بلا فارضٍ منذ إقراره، وهو بالضبط لماذا أمكن لثلاثة
    تصنيفاتٍ للموضوع أن تتفرّق حتى وقعت ISS-159. المسح هنا على **المصدر والوثائق معاً**.
    """
    phantom: dict[str, set[str]] = {}
    for path in _scannable_files():
        rel = str(path.relative_to(REPO_ROOT))
        for name in _gate_names_in(path):
            if name not in gates and name not in _PHANTOM_EXCEPTIONS:
                phantom.setdefault(name, set()).add(rel)
    if phantom:
        detail = {name: sorted(where)[:3] for name, where in sorted(phantom.items())}
        _fail(f"إحالات وهمية — بوّابات مذكورة بلا ملفّ: {detail}")
        return
    _pass(f"صفر إحالة وهمية (استثناءات منطوقة: {len(_PHANTOM_EXCEPTIONS)})")


def _check_no_hand_typed_counts(gates: dict[str, str]) -> None:
    """`.memory/ci-gates.md` كان يقول «~31 فحصاً» — رقمٌ في نثرٍ يتقادم (D-192)."""
    if not CI_GATES_DOC.is_file():
        _fail("`.memory/ci-gates.md` مفقود")
        return
    text = CI_GATES_DOC.read_text(encoding="utf-8")
    hand_typed = re.findall(r"[~≈]\s*\d+\s*(?:فحص|بوّابة|بوابة|gates?|checks?)", text)
    if hand_typed:
        _fail(f"`.memory/ci-gates.md`: عددٌ مكتوب يدوياً {hand_typed} — يُشتَقّ من الـworkflow (D-192)")
        return
    marker = f"<!-- derived:gates_total={len(gates)} -->"
    if marker not in text:
        _fail(f"`.memory/ci-gates.md`: علامة العدد المُشتَقّ مفقودة أو متقادمة — المتوقّع `{marker}`")
        return
    _pass(f"`.memory/ci-gates.md`: العدد مُشتَقّ ومطابق ({len(gates)} بوّابة)")


# ──────────────────────────────────────────────────────────────────────────────
# الفارض المحلّي مطابقٌ لـCI أو مُعلَنٌ ميتاً (D-270 L7)
#
# D-266 أثبت أنّ بوّابةً على القرص لا يشغّلها شيء «تُقرأ حمايةً وهي ليست حماية».
# والقياس في 2026-08-19 وجد النمط نفسه **خارج** `scripts/fitness/`:
# `.pre-commit-config.yaml` — الفارض المحلّي الموثَّق في `Makefile` — لم يكن يُشغَّل
# في أيّ workflow، **وكان يناقض CI مناقضةً مباشرة**:
#
#   ① `black` (بلا وسائط ⇒ عرض 88) بينما `pyproject.toml` يفرض 100 وCI يفحص
#      بـ`ruff format --check`. القياس: **7917 سطراً في 1441 ملفّاً** طولها 89..100
#      حرفاً — أي أنّ تشغيل الخطّافات الموثَّقة كان **يضمن** دفعةً حمراء.
#   ② `isort` مُكرَّر أصلاً: قاعدة `I` مُفعَّلة داخل ruff بإعدادٍ مختلف.
#   ③ خطّاف `mypy` بلا `pydantic` بينما `mypy.ini` يحمل `plugins = pydantic.mypy`
#      ⇒ يخرج بالرمز 2 قبل فحص سطرٍ واحد. (CI واجه هذا وأصلحه؛ الفارض المحلّي لا.)
#
# فارضٌ يخالف CI أسوأ من غيابه: الغياب يُلاحَظ، والمخالفة **مصيدة** — من يتّبع
# الوثائق يُحمِّر الـCI ولا يفهم لماذا. ولذلك تُشتَقّ النسخ من الطرفين ولا تُكتب ثالثةً.
# ──────────────────────────────────────────────────────────────────────────────
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _ci_pin(tool: str) -> str | None:
    """نسخة الأداة كما يُثبِّتها CI — مُشتَقّة من الـworkflow لا مكتوبة هنا (D-192)."""
    if not CI_WORKFLOW.is_file():
        return None
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    match = re.search(rf"\b{re.escape(tool)}==([0-9][0-9A-Za-z.\-]*)", text)
    return match.group(1) if match else None


def _precommit_repos(config: dict) -> dict[str, str]:
    """`owner/name` ⇒ `rev` بلا بادئة `v`."""
    found: dict[str, str] = {}
    for repo in config.get("repos", []):
        url = str(repo.get("repo", ""))
        slug = "/".join(url.rstrip("/").split("/")[-2:])
        found[slug] = str(repo.get("rev", "")).lstrip("v")
    return found


def _precommit_hook_ids(config: dict) -> set[str]:
    return {
        str(hook.get("id", ""))
        for repo in config.get("repos", [])
        for hook in repo.get("hooks", [])
    }


def _check_mirror_pins(rel: str, repos: dict[str, str], contract: dict) -> set[str]:
    """كل أداةٍ يفرضها CI لها مرآةٌ محلّية بنفس النسخة. تُعيد الـslugs المُصرَّحة."""
    declared: set[str] = set()
    for mirror in contract.get("mirrors", []):
        slug, tool = mirror["repo"], mirror["tool"]
        declared.add(slug)
        if slug not in repos:
            _fail(f"{rel}: مرآة `{tool}` مفقودة — CI يفرضها والفارض المحلّي لا")
            continue
        ci_version, local_version = _ci_pin(tool), repos[slug]
        if ci_version is None:
            _fail(f"{rel}: `{tool}` مُعلَنٌ مرآةً لكن CI لا يُثبِّته — مرآةٌ بلا أصل")
        elif ci_version != local_version:
            _fail(
                f"{rel}: `{tool}` محلّياً {local_version} بينما CI يُثبِّت {ci_version} — "
                "أداةٌ تختلف بين الفارضين ليست فارضاً بل مصيدة"
            )
    return declared


def _check_config_contract(rel: str, contract: dict) -> None:
    path = REPO_ROOT / rel
    if not path.is_file():
        _fail(f"`local_enforcers` يسمّي إعداداً غير موجود: {rel}")
        return
    try:
        config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        # ⛔ إعدادٌ لم يُحلَّل لا يُشهَد له بالتطابق (D-208 §6).
        _fail(f"{rel}: تعذّر التحليل — لا يُعَدّ مطابقاً: {exc}")
        return

    repos = _precommit_repos(config)
    declared = _check_mirror_pins(rel, repos, contract)

    hook_ids = _precommit_hook_ids(config)
    for tool, reason in (contract.get("forbidden_tools") or {}).items():
        if tool in hook_ids:
            _fail(f"{rel}: الخطّاف `{tool}` ممنوع — {reason}")

    declared |= set(contract.get("local_only_repos") or {})
    if undeclared := sorted(set(repos) - declared):
        _fail(
            f"{rel}: مستودعات خطّافات غير مُصرَّحة {undeclared} — كل فارضٍ محلّي "
            "إمّا مرآةٌ لـCI وإمّا مُعلَنٌ محلّياً بسببه (D-206 L11)"
        )


def _check_local_enforcers(registry: dict) -> None:
    spec = registry.get("local_enforcers")
    if not isinstance(spec, dict) or not spec.get("configs"):
        _fail("`local_enforcers.configs` مفقود — L7 قانونٌ بلا فارض")
        return

    for rel, contract in sorted(spec["configs"].items()):
        _check_config_contract(rel, contract)

    debt = spec.get("unenforced_local_debt", {})
    if not isinstance(debt, dict):
        _fail("`local_enforcers.unenforced_local_debt` يجب أن يكون كائناً")
        return
    if empty := [name for name, reason in debt.items() if not str(reason).strip()]:
        _fail(f"دَينٌ محلّي بلا سببٍ منطوق: {sorted(empty)} — الخانة الفارغة تُقرأ نجاحاً")
        return
    _pass(f"الفوارض المحلّية مطابقةٌ لـCI عبر {len(spec['configs'])} إعداداً (دَينٌ مُعلَن: {len(debt)})")


# ──────────────────────────────────────────────────────────────────────────────
# فوارض العملية مُعلَنة لا مُكتشَفة (D-270 L1/L2/L3)
#
# `GATE_HOMES` تغطّي فوارض **المستودع الساكن**. أمّا فوارض **العملية** (وصف الدفعة ·
# جاهزية البلاغ) فتحتاج حمولة حدثٍ من GitHub، فلا تصلح لـ`run_fitness_gates`، ولا
# يجوز في الوقت نفسه أن تعيش في موطنٍ لا يعرفه السجلّ: «موطنٌ ثالث بلا إعلانٍ يعني
# بوّابةً غير مرئية» (D-266). فهي مُعلَنة هنا، ويُفحَص لكلٍّ منها **ملفّها** و**الـ
# workflow الذي يشغّلها فعلاً** — نفس الساق الثالثة، بمرمى آخر.
# ──────────────────────────────────────────────────────────────────────────────
PROCESS_HOME = ".github/scripts"


def _check_one_process_enforcer(name: str, contract: dict, home: Path) -> None:
    """المُتحقِّق موجودٌ، والـworkflow المُصرَّح موجودٌ **ويستدعيه فعلاً**."""
    if not (home / name).is_file():
        _fail(f"`process_enforcers` يسمّي مُتحقِّقاً غير موجود: {name}")
        return
    workflow_rel = str(contract.get("workflow", ""))
    workflow = REPO_ROOT / workflow_rel
    if not workflow.is_file():
        _fail(f"{name}: يُصرَّح أنّ `{workflow_rel}` يشغّله — والملفّ غير موجود")
        return
    if name not in workflow.read_text(encoding="utf-8"):
        _fail(
            f"{name}: `{workflow_rel}` لا يستدعيه — فارضٌ على القرص بلا مرمى "
            "(نفس صنف ISS-186، بمرمى العملية)"
        )


def _process_home_matches(home: Path, declared: set[str]) -> bool:
    """الموطن والسجلّ متطابقان في الاتجاهين — لا يتيمٌ على القرص ولا اسمٌ وهمي."""
    on_disk = {path.name for path in home.glob("*.py")} if home.is_dir() else set()
    if undeclared := sorted(on_disk - declared):
        _fail(f"مُتحقِّقات عملية على القرص بلا إعلانٍ في السجلّ: {undeclared}")
    if ghost := sorted(declared - on_disk):
        _fail(f"`process_enforcers` يسمّي ملفّات غير موجودة: {ghost}")
    return not undeclared and not ghost


def _check_process_enforcers(registry: dict) -> None:
    spec = registry.get("process_enforcers")
    if not isinstance(spec, dict) or not spec.get("enforcers"):
        _fail("`process_enforcers` مفقود — فوارض العملية بلا إعلان (موطنٌ غير مرئي)")
        return

    home = REPO_ROOT / str(spec.get("home", PROCESS_HOME))
    declared: dict = spec["enforcers"]

    for name, contract in sorted(declared.items()):
        _check_one_process_enforcer(name, contract, home)

    if _process_home_matches(home, set(declared)):
        _pass(f"فوارض العملية مُعلَنة ومُنفَّذة: {len(declared)} مُتحقِّقاً")


def main() -> int:
    if not REGISTRY.is_file():
        print(f"❌ السجلّ الدستوري مفقود: {REGISTRY.relative_to(REPO_ROOT)}")
        return 1
    try:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"❌ السجلّ الدستوري ليس JSON صالحاً: {exc}")
        return 1

    gates = _gates_on_disk()
    if not gates:
        print("❌ لم يُعثر على أيّ بوّابة — مواطن البوّابات خاطئة أو المستودع مبتور")
        return 1

    _check_execution(gates, registry)
    _check_enforcers_exist(gates, registry)
    _check_sections(registry)
    _check_doc_paths(registry)
    _check_declared_absence(registry)
    _check_no_phantom_enforcers(gates)
    _check_no_hand_typed_counts(gates)
    _check_local_enforcers(registry)
    _check_process_enforcers(registry)

    if _FAILURES:
        print(f"\n❌ {len(_FAILURES)} انتهاك — الحوكمة ليست مفروضة:")
        for failure in _FAILURES:
            print(f"   - {failure}")
        return 1
    print("\n✅ governance-registry: كل فارضٍ له مرمى، وكل دستورٍ له فارض، والخريطة لا تكذب.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
