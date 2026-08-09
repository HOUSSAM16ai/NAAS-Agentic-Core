#!/usr/bin/env python3
"""يمنع ارتدادَ سباكة CI إلى قوالب المُولِّدات — القانون يصير فارضاً (D-235).

**لماذا هذه البوّابة موجودة:**

في 2026-08-09 اكتُشف أن تكاملَي الجودة الخارجيَّين **لا يعملان**، وأن كليهما كان يبدو
سليماً من الخارج:

- ``codescene-coverage`` كان ينتهي ``success`` في كل تشغيل بينما خطوة الرفع نفسها
  ``skipped`` — لأن السرّ لم يكن موجوداً بعد. **لم يرفع بايتاً منذ كُتب**، ولا شيء قاله.
  وظيفةٌ خضراء لم تفعل شيئاً لا يميّزها شيءٌ عن وظيفةٍ فعلت.
- ``qodana_code_quality.yml`` كان قد حُصِّن في D-234 (``checkout@v5`` · ``contents: read``
  · حارس سرّ · مهلة)، ثمّ **ابتلع الدمجُ الآلي التحصينَ كاملاً** وأعاد قالب المُولِّد
  الخام. حدث ذلك **ثلاث مرّات** (``2cbab01`` · ``065b13f`` · ``f4b3b40``)، وفي كل مرّة
  عاد تحذير Node20 و``contents: write`` وغياب الحارس، ولم يلاحظ ذلك أيُّ فحص.

القاعدتان كانتا **مكتوبتين في D-234** ومشروحتين بتعليقات مطوَّلة داخل الملفّ نفسه —
ومع ذلك مُحيتا مرّتين. وهذا هو «الثمن الأول» في العقيدة الهندسية: **قانونٌ بلا فارضٍ آلي
يُنسى في أوّل PR عاجل** (``ENGINEERING_DOCTRINE.md``). فهذه هي الفارض.

**الدَّين المُجمَّد فارغ ويتقلّص فقط.** الشجرة نظيفة بعد D-235، فتبقى كذلك.

**صدق البوّابة (D-208 §6):** ملفٌّ لا يُحلَّل **يُبلَّغ عنه فشلاً** ولا يُعَدّ نظيفاً —
بوّابة لا تقرأ ملفاً لا تشهد بأنه سليم.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github/workflows"
COMPOSITE_ACTIONS = REPO_ROOT / ".github/actions"

#: أرضية إصدارات إجراءات GitHub الرسمية — **مقيسة** من الشجرة يوم D-235 لا مُخترَعة.
#: D-141 يوجب node24 وصفر warning، و``actions/checkout@v3`` كان يطبع
#: ``##[warning]Node.js 20 is deprecated`` في كل تشغيل Qodana. الأرضية ترتفع بقرارٍ
#: مكتوب حين تُرقّى الشجرة، ولا تنخفض أبداً.
MIN_ACTION_MAJOR: dict[str, int] = {
    "actions/checkout": 5,
    "actions/setup-python": 6,
    "actions/setup-node": 5,
    "actions/upload-artifact": 6,
    "actions/download-artifact": 6,
}

#: رموز خدمات خارجية. كل واحدٍ منها **يجب** أن يُقرأ عبر ``env`` على مستوى الوظيفة
#: (سياق ``secrets`` غير متاح في ``if:``) وأن تحرسه خطوةٌ بشرط حضور — وإلّا فشلت كل
#: PR من fork بدل أن تتخطّى، أو — الأسوأ — تخطّت **بصمت** كما فعلت CodeScene شهراً.
SAAS_TOKEN_ENV: tuple[str, ...] = ("QODANA_TOKEN", "CS_ACCESS_TOKEN")

#: ⛔ D-234: لا Qodana ولا CodeScene في ``required-ci``. تعطُّلُ خدمةٍ خارجية أو انتهاءُ
#: صلاحية رمزٍ يجب ألّا يجعل المستودع غير قابل للدمج.
FORBIDDEN_IN_REQUIRED_CI: tuple[str, ...] = ("codescene-coverage", "qodana")

#: الدَّين المُجمَّد — **فارغ**، ويتقلّص فقط (سابقة D-105).
FROZEN_DEBT: frozenset[str] = frozenset()

_ACTION_REF = re.compile(r"uses:\s*([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@v(\d+)")
_QODANA_SECRET = re.compile(r"secrets\.QODANA_TOKEN[A-Za-z0-9_]*")


def _rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def _yaml_files() -> list[Path]:
    files = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    files += sorted(COMPOSITE_ACTIONS.rglob("action.yml"))
    files += sorted(COMPOSITE_ACTIONS.rglob("action.yaml"))
    return files


def _load(path: Path, errors: list[str]) -> dict[str, Any] | None:
    """يُحمِّل YAML — والفشل **يُبلَّغ** ولا يُبتلَع (D-208 §6)."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError) as exc:
        errors.append(
            f"❌ {_rel(path)}: تعذّر تحليل الملفّ ({exc.__class__.__name__}).\n"
            f"   البوّابة **لا تشهد** بنظافة ملفٍّ لم تقرأه — أصلِح الملفّ أو احذفه."
        )
        return None
    return data if isinstance(data, dict) else None


def _jobs(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    jobs = doc.get("jobs")
    if not isinstance(jobs, dict):
        return {}
    return {name: body for name, body in jobs.items() if isinstance(body, dict)}


def _steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    steps = job.get("steps")
    if not isinstance(steps, list):
        return []
    return [s for s in steps if isinstance(s, dict)]


def _check_action_versions(path: Path, text: str, errors: list[str]) -> None:
    for match in _ACTION_REF.finditer(text):
        action, major = match.group(1), int(match.group(2))
        floor = MIN_ACTION_MAJOR.get(action)
        if floor is None or major >= floor:
            continue
        line_no = text[: match.start()].count("\n") + 1
        errors.append(
            f"❌ {_rel(path)}:{line_no}: `{action}@v{major}` أقدم من الأرضية `v{floor}`.\n"
            f"   D-141 يوجب إجراءات node24 وصفر warning — و`checkout@v3` كان يطبع\n"
            f"   `Node.js 20 is deprecated` في كل تشغيل. رفِّع الإصدار، ولا تُخفِّض الأرضية."
        )


def _token_envs(scope: dict[str, Any]) -> set[str]:
    env = scope.get("env")
    if not isinstance(env, dict):
        return set()
    return {key for key in env if key in SAAS_TOKEN_ENV}


def _check_token_guard(path: Path, name: str, job: dict[str, Any], errors: list[str]) -> None:
    job_tokens = _token_envs(job)
    step_tokens: set[str] = set()
    for step in _steps(job):
        step_tokens |= _token_envs(step)

    # رمزٌ يُقرأ داخل خطوةٍ فقط لا يمكن أن يحرسه ``if:`` — سياق ``env`` الخاصّ بالخطوة
    # غير مرئيّ لشرطها. فمكانه مستوى الوظيفة.
    for token in sorted(step_tokens - job_tokens):
        errors.append(
            f"❌ {_rel(path)} · job `{name}`: `{token}` مُعرَّف على مستوى الخطوة فقط.\n"
            f"   انقله إلى `env:` على مستوى الوظيفة — شرطُ الخطوة لا يرى `env` الخاصّ بها،\n"
            f"   فبدون ذلك يستحيل الحارس وتفشل كل PR من fork."
        )

    for token in sorted(job_tokens):
        conditions = [str(step.get("if", "")) for step in _steps(job)]
        has_run_guard = any(f"env.{token} != ''" in cond for cond in conditions)
        has_absence_report = any(f"env.{token} == ''" in cond for cond in conditions)
        if not has_run_guard:
            errors.append(
                f"❌ {_rel(path)} · job `{name}`: لا خطوة محروسة بـ`if: env.{token} != ''`.\n"
                f"   بلا الحارس تفشل كل PR من fork (لا أسرار لها) بدل أن تتخطّى — D-234."
            )
        if not has_absence_report:
            errors.append(
                f"❌ {_rel(path)} · job `{name}`: التخطّي عند غياب `{token}` **صامت**.\n"
                f"   أضف خطوة `if: env.{token} == ''` تكتب `::warning` + سطراً في\n"
                f"   `$GITHUB_STEP_SUMMARY`. وظيفةٌ خضراء لم تفعل شيئاً يجب أن تقول ذلك\n"
                f"   (§0 «لا فشل صامت» · L11 «الغياب لا يعني الغموض») — وهذا حرفياً ما\n"
                f"   أخفى أن CodeScene لم يرفع تقريراً واحداً منذ كُتبت الوظيفة."
            )


def _check_third_party_write(path: Path, name: str, job: dict[str, Any], errors: list[str]) -> None:
    third_party = [
        str(step["uses"])
        for step in _steps(job)
        if isinstance(step.get("uses"), str)
        and not str(step["uses"]).startswith(("actions/", "./", "docker/"))
    ]
    if not third_party:
        return
    permissions = job.get("permissions")
    if isinstance(permissions, dict) and permissions.get("contents") == "write":
        errors.append(
            f"❌ {_rel(path)} · job `{name}`: `contents: write` في وظيفةٍ تستدعي إجراءً من\n"
            f"   طرفٍ ثالث ({third_party[0]}). الفحص الساكن يقرأ الشيفرة ويكتب checks — لا\n"
            f"   سبب لمنحه دفعاً إلى المستودع (D-187: القدرة ≠ الأمان)."
        )


def _check_qodana_diagnostic(path: Path, name: str, job: dict[str, Any], errors: list[str]) -> None:
    uses_qodana = any(
        isinstance(step.get("uses"), str) and "qodana-action" in str(step["uses"])
        for step in _steps(job)
    )
    if not uses_qodana:
        return
    if not any("failure()" in str(step.get("if", "")) for step in _steps(job)):
        errors.append(
            f"❌ {_rel(path)} · job `{name}`: لا خطوة تشخيص `if: failure()`.\n"
            f"   مُعرَّف مشروع Qodana Cloud تغيّر مرّتين (335615010 → 1439809274 →\n"
            f"   118820581)، وكل مرّة أبطلت السرّ القديم وأنتجت `403` مبهماً. الخطوة\n"
            f"   تكتب الـrunbook حيث يراه من ينظر إلى العلامة الحمراء."
        )


def _check_required_ci(path: Path, jobs: dict[str, dict[str, Any]], errors: list[str]) -> None:
    required = jobs.get("required-ci")
    if required is None:
        return
    needs = required.get("needs")
    declared = [needs] if isinstance(needs, str) else list(needs or [])
    for job_name in declared:
        if any(token in str(job_name) for token in FORBIDDEN_IN_REQUIRED_CI):
            errors.append(
                f"❌ {_rel(path)} · `required-ci` يعتمد على `{job_name}`.\n"
                f"   ⛔ D-234: تعطُّلُ خدمةٍ خارجية أو انتهاءُ صلاحية رمزٍ يجب ألّا يجعل\n"
                f"   المستودع غير قابل للدمج."
            )


def _check_single_qodana_secret(files: list[Path], errors: list[str]) -> None:
    found: dict[str, list[str]] = {}
    for path in files:
        for match in _QODANA_SECRET.finditer(path.read_text(encoding="utf-8")):
            found.setdefault(match.group(0), []).append(_rel(path))
    if len(found) > 1:
        names = ", ".join(sorted(found))
        errors.append(
            f"❌ أكثر من اسم سرٍّ لـQodana في الشجرة: {names}.\n"
            f"   اسمٌ واحد ومصدرٌ واحد (D-192). سلسلة `secrets.A || secrets.B` تلتقط قيمةً\n"
            f"   قديمة كلّما فرغت الأولى — والقيم القديمة هي ما كلّف أربع تشغيلات حمراء."
        )


def main() -> int:
    errors: list[str] = []
    files = _yaml_files()
    if not files:
        print("❌ لا ملفّات سير عمل — البوّابة بلا مرمى (فارضٌ بلا مرمى مرفوض).")
        return 1

    for path in files:
        text = path.read_text(encoding="utf-8")
        _check_action_versions(path, text, errors)

        doc = _load(path, errors)
        if doc is None:
            continue

        jobs = _jobs(doc)
        _check_required_ci(path, jobs, errors)
        for name, job in jobs.items():
            _check_token_guard(path, name, job, errors)
            _check_third_party_write(path, name, job, errors)
            _check_qodana_diagnostic(path, name, job, errors)

    _check_single_qodana_secret(files, errors)

    if errors:
        print("\n".join(errors))
        print(f"\n💥 {len(errors)} خرقاً في سباكة CI.")
        return 1
    print(
        f"✅ ci workflow hygiene: {len(files)} ملفّاً — الإصدارات فوق الأرضية، "
        "ورموز الخدمات محروسة ومنطوقة الغياب، ولا صلاحية كتابة لطرفٍ ثالث، "
        "ولا تكامل خارجي في required-ci."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
