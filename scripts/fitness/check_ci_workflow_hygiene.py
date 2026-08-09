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

**والأداة الثالثة محكومة بنفس القانون:** ``.coderabbit.yaml`` يجب أن يوجد، وأن يُوجِّه
المُراجِع إلى ``CLAUDE.md`` بأنماطٍ **تقابل ملفّات موجودة**، وألّا يحجب الدمج. السبب
مقيسٌ لا مُفترَض: ``dict[str, Any]`` مرّ على Qodana وCodeScene وCodeRabbit ثلاثتهم
ورفضته ``check_no_new_any`` — فالمُراجِع الخارجي يعرف **اللغة** ويجهل **قانون هذا
المستودع** ما لم يُعطَه. وإحالةٌ إلى ملفٍّ أُعيدت تسميته تُخفِّضه إلى الافتراضات بلا
أيّ إشارة (D-208 §8).

**الدَّين المُجمَّد فارغ ويتقلّص فقط.** الشجرة نظيفة بعد D-235، فتبقى كذلك.

**صدق البوّابة (D-208 §6):** ملفٌّ لا يُحلَّل **يُبلَّغ عنه فشلاً** ولا يُعَدّ نظيفاً —
بوّابة لا تقرأ ملفاً لا تشهد بأنه سليم.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
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
    "actions/download-artifact": 8,
}

#: رموز خدمات خارجية. كل واحدٍ منها **يجب** أن يُقرأ عبر ``env`` على مستوى الوظيفة
#: (سياق ``secrets`` غير متاح في ``if:``) وأن تحرسه خطوةٌ بشرط حضور — وإلّا فشلت كل
#: PR من fork بدل أن تتخطّى، أو — الأسوأ — تخطّت **بصمت** كما فعلت CodeScene شهراً.
SAAS_TOKEN_ENV: tuple[str, ...] = ("QODANA_TOKEN", "CS_ACCESS_TOKEN")

#: ⛔ D-234: لا Qodana ولا CodeScene في ``required-ci``. تعطُّلُ خدمةٍ خارجية أو انتهاءُ
#: صلاحية رمزٍ يجب ألّا يجعل المستودع غير قابل للدمج.
FORBIDDEN_IN_REQUIRED_CI: tuple[str, ...] = ("codescene-coverage", "qodana")

#: إعدادات المُراجِع الخارجي. ⛔ **الدستور نفسه يجب أن يكون ضمن ما يقرأه** — وإلّا وافق
#: على كودٍ ترفضه بوّابات المستودع، وهو ما حدث **مقيساً** لا افتراضاً: `dict[str, Any]`
#: مرّ على Qodana وCodeScene وCodeRabbit ثلاثتهم، ورفضته `check_no_new_any` (D-192).
CODERABBIT_CONFIG = REPO_ROOT / ".coderabbit.yaml"
CODERABBIT_REQUIRED_GUIDELINES: tuple[str, ...] = ("CLAUDE.md",)

#: الدَّين المُجمَّد — **فارغ**، ويتقلّص فقط (سابقة D-105).
FROZEN_DEBT: frozenset[str] = frozenset()

#: كل مرجع ``uses:`` مهما كان شكله. الالتقاط على ``@vN`` وحده كان يترك
#: ``actions/checkout@main`` و``@<sha>`` يمرّان فوق الأرضية بلا فحص — أرضيةٌ
#: تُتجاوَز بمرجعٍ متحرّك ليست أرضية.
_ACTION_REF = re.compile(r"uses:\s*([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@(\S+)")
_MAJOR_TAG = re.compile(r"^v(\d+)(?:\.\d+)*$")
_QODANA_SECRET = re.compile(r"secrets\.QODANA_TOKEN[A-Za-z0-9_]*")


@dataclass(frozen=True)
class _FileCtx:
    """ما يخصّ الملفّ الواحد، مُمرَّراً كوحدة.

    كل فاحص كان يأخذ ``path`` و``errors`` وصلاحيات الملفّ منفصلةً، فبلغت التواقيع
    خمسة وسائط — وهو ما رصدته CodeScene على هذا الملفّ نفسه. تجميعها يُبقي التوقيع
    ثلاثة ويجعل «سياق الملفّ» شيئاً مُسمّى بدل قائمة معاملات تنمو مع كل قاعدة.
    """

    path: Path
    workflow_permissions: Any
    errors: list[str]


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
    if isinstance(data, dict):
        return data
    errors.append(
        f"❌ {_rel(path)}: جذر YAML ليس تخطيطاً (mapping) بل {type(data).__name__}.\n"
        f"   البوّابة تتخطّى كل الفحوص البنيوية لمثل هذا الملفّ — والتخطّي الصامت\n"
        f"   يُقرأ نظافةً، وهو بالضبط ما وُجدت هذه البوّابة لتمنعه."
    )
    return None


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


def _check_action_versions(ctx: _FileCtx, text: str) -> None:
    for match in _ACTION_REF.finditer(text):
        action, ref = match.group(1), match.group(2).strip("\"'")
        floor = MIN_ACTION_MAJOR.get(action)
        if floor is None:
            continue
        line_no = text[: match.start()].count("\n") + 1
        tag = _MAJOR_TAG.match(ref)
        if tag is None:
            ctx.errors.append(
                f"❌ {_rel(ctx.path)}:{line_no}: `{action}@{ref}` ليس وسماً بإصدارٍ رئيسي.\n"
                f"   الأرضية تُفرَض على `v<major>` وحده — ومرجعٌ متحرّك (`@main`) أو\n"
                f"   `@<sha>` يعبر الفحص بلا أن يُقاس، فتصير الأرضية إعلاناً لا حَكَماً."
            )
            continue
        if int(tag.group(1)) >= floor:
            continue
        ctx.errors.append(
            f"❌ {_rel(ctx.path)}:{line_no}: `{action}@{ref}` أقدم من الأرضية `v{floor}`.\n"
            f"   D-141 يوجب إجراءات node24 وصفر warning — و`checkout@v3` كان يطبع\n"
            f"   `Node.js 20 is deprecated` في كل تشغيل. رفِّع الإصدار، ولا تُخفِّض الأرضية."
        )


def _token_envs(scope: dict[str, Any]) -> set[str]:
    env = scope.get("env")
    if not isinstance(env, dict):
        return set()
    return {key for key in env if key in SAAS_TOKEN_ENV}


def _step_scoped_tokens(job: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for step in _steps(job):
        tokens |= _token_envs(step)
    return tokens


def _report_step_scoped_token(ctx: _FileCtx, name: str, token: str) -> None:
    """رمزٌ يُقرأ داخل خطوةٍ فقط لا يمكن أن يحرسه ``if:`` — سياق ``env`` الخاصّ بالخطوة
    غير مرئيّ لشرطها، فمكانه مستوى الوظيفة."""
    ctx.errors.append(
        f"❌ {_rel(ctx.path)} · job `{name}`: `{token}` مُعرَّف على مستوى الخطوة فقط.\n"
        f"   انقله إلى `env:` على مستوى الوظيفة — شرطُ الخطوة لا يرى `env` الخاصّ بها،\n"
        f"   فبدون ذلك يستحيل الحارس وتفشل كل PR من fork."
    )


def _report_missing_run_guard(ctx: _FileCtx, name: str, token: str) -> None:
    ctx.errors.append(
        f"❌ {_rel(ctx.path)} · job `{name}`: لا خطوة محروسة بـ`if: env.{token} != ''`.\n"
        f"   بلا الحارس تفشل كل PR من fork (لا أسرار لها) بدل أن تتخطّى — D-234."
    )


def _report_silent_skip(ctx: _FileCtx, name: str, token: str) -> None:
    ctx.errors.append(
        f"❌ {_rel(ctx.path)} · job `{name}`: التخطّي عند غياب `{token}` **صامت**.\n"
        f"   أضف خطوة `if: env.{token} == ''` تكتب `::warning` + سطراً في\n"
        f"   `$GITHUB_STEP_SUMMARY`. وظيفةٌ خضراء لم تفعل شيئاً يجب أن تقول ذلك\n"
        f"   (§0 «لا فشل صامت» · L11 «الغياب لا يعني الغموض») — وهذا حرفياً ما\n"
        f"   أخفى أن CodeScene لم يرفع تقريراً واحداً منذ كُتبت الوظيفة."
    )


def _guarded_tokens(conditions: list[str], operator: str) -> set[str]:
    """الرموز التي يذكرها شرطُ خطوةٍ ما بالمقارنة المطلوبة (``!=`` أو ``==``)."""
    return {
        token
        for token in SAAS_TOKEN_ENV
        if any(f"env.{token} {operator} ''" in cond for cond in conditions)
    }


def _check_token_guard(ctx: _FileCtx, name: str, job: dict[str, Any]) -> None:
    job_tokens = _token_envs(job)
    for token in sorted(_step_scoped_tokens(job) - job_tokens):
        _report_step_scoped_token(ctx, name, token)

    conditions = [str(step.get("if", "")) for step in _steps(job)]
    for token in sorted(job_tokens - _guarded_tokens(conditions, "!=")):
        _report_missing_run_guard(ctx, name, token)
    for token in sorted(job_tokens - _guarded_tokens(conditions, "==")):
        _report_silent_skip(ctx, name, token)


def _third_party_uses(job: dict[str, Any]) -> list[str]:
    return [
        str(step["uses"])
        for step in _steps(job)
        if isinstance(step.get("uses"), str)
        and not str(step["uses"]).startswith(("actions/", "./", "docker/"))
    ]


def _check_third_party_write(ctx: _FileCtx, name: str, job: dict[str, Any]) -> None:
    third_party = _third_party_uses(job)
    if not third_party:
        return
    # صلاحيات الوظيفة تَرِث صلاحيات الملفّ حين لا تُصرِّح بنفسها. قراءةُ الوظيفة وحدها
    # كانت تُمرِّر `contents: write` معلَناً على مستوى الملفّ — وهو نفس المنح بالضبط.
    permissions = job.get("permissions", ctx.workflow_permissions)
    if isinstance(permissions, dict) and permissions.get("contents") == "write":
        ctx.errors.append(
            f"❌ {_rel(ctx.path)} · job `{name}`: `contents: write` في وظيفةٍ تستدعي إجراءً من\n"
            f"   طرفٍ ثالث ({third_party[0]}). الفحص الساكن يقرأ الشيفرة ويكتب checks — لا\n"
            f"   سبب لمنحه دفعاً إلى المستودع (D-187: القدرة ≠ الأمان)."
        )


def _check_qodana_diagnostic(ctx: _FileCtx, name: str, job: dict[str, Any]) -> None:
    uses_qodana = any(
        isinstance(step.get("uses"), str) and "qodana-action" in str(step["uses"])
        for step in _steps(job)
    )
    if not uses_qodana:
        return
    if not any("failure()" in str(step.get("if", "")) for step in _steps(job)):
        ctx.errors.append(
            f"❌ {_rel(ctx.path)} · job `{name}`: لا خطوة تشخيص `if: failure()`.\n"
            f"   مُعرَّف مشروع Qodana Cloud تغيّر مرّتين (335615010 → 1439809274 →\n"
            f"   118820581)، وكل مرّة أبطلت السرّ القديم وأنتجت `403` مبهماً. الخطوة\n"
            f"   تكتب الـrunbook حيث يراه من ينظر إلى العلامة الحمراء."
        )


def _check_required_ci(ctx: _FileCtx, jobs: dict[str, dict[str, Any]]) -> None:
    required = jobs.get("required-ci")
    if required is None:
        return
    needs = required.get("needs")
    declared = [needs] if isinstance(needs, str) else list(needs or [])
    for job_name in declared:
        if any(token in str(job_name) for token in FORBIDDEN_IN_REQUIRED_CI):
            ctx.errors.append(
                f"❌ {_rel(ctx.path)} · `required-ci` يعتمد على `{job_name}`.\n"
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


def _guideline_patterns(knowledge: dict[str, Any]) -> list[str]:
    """أنماط ملفّات الدستور المُعلَنة — تقبل السلسلة والكائن ``{files, applyTo}`` معاً."""
    guidelines = knowledge.get("code_guidelines")
    if not isinstance(guidelines, dict) or guidelines.get("enabled") is False:
        return []
    declared = guidelines.get("filePatterns")
    # ⚠️ سلسلةٌ مفردة بدل قائمة تُكرَّر حرفاً حرفاً فتُنتج أنماطاً بلا معنى **وتمرّ**.
    # نوعٌ غير متوقَّع يُعامَل «لا أنماط» فيُبلَّغ عنه أدناه، ولا يُبتلَع (D-208 §6).
    if not isinstance(declared, list):
        return []
    patterns: list[str] = []
    for entry in declared:
        if isinstance(entry, str):
            patterns.append(entry)
        elif isinstance(entry, dict) and isinstance(entry.get("files"), str):
            patterns.extend(part.strip() for part in entry["files"].split(","))
    return patterns


def _check_coderabbit_law(config: dict[str, Any], errors: list[str]) -> None:
    """المُراجِع الخارجي يقرأ الدستور — وإلّا عرف اللغةَ وجهل القانون."""
    patterns = _guideline_patterns(config.get("knowledge_base") or {})
    for required in CODERABBIT_REQUIRED_GUIDELINES:
        if required in patterns:
            continue
        errors.append(
            f"❌ .coderabbit.yaml: `{required}` غائب عن "
            f"`knowledge_base.code_guidelines.filePatterns`.\n"
            f"   مُراجِعٌ لا يقرأ الدستور يوافق على ما ترفضه بوّابات المستودع — مقيساً:\n"
            f"   `dict[str, Any]` مرّ على الأدوات الخارجية الثلاث ورفضته `check_no_new_any`."
        )
    for pattern in patterns:
        if "*" not in pattern and not (REPO_ROOT / pattern).exists():
            errors.append(
                f"❌ .coderabbit.yaml: نمط الدستور `{pattern}` لا يقابل ملفّاً موجوداً.\n"
                f"   إحالةٌ إلى العدم تُخفِّض المُراجِع إلى الافتراضات **بلا أيّ إشارة**\n"
                f"   (D-208 §8: خريطة السلطة لا تُحيل إلى العدم)."
            )


def _check_coderabbit_advisory(config: dict[str, Any], errors: list[str]) -> None:
    """⛔ D-234: لا يجعل تكاملٌ خارجي المستودعَ غير قابل للدمج."""
    reviews = config.get("reviews")
    reviews = reviews if isinstance(reviews, dict) else {}
    blocking = [
        key
        for key in ("fail_commit_status", "request_changes_workflow")
        if reviews.get(key) is True
    ]
    if "pre_merge_checks" in reviews:
        blocking.append("pre_merge_checks")
    if blocking:
        errors.append(
            f"❌ .coderabbit.yaml: {', '.join(blocking)} يجعل المُراجِع الخارجي حاجزَ دمج.\n"
            f"   ⛔ D-234 — نفس القانون الذي يُبقي Qodana وCodeScene خارج `required-ci`:\n"
            f"   تعطُّلُ خدمةٍ خارجية يجب ألّا يجعل المستودع غير قابل للدمج. المراجعة نصيحةٌ\n"
            f"   بدليل، والفارض هو `scripts/fitness/`."
        )


def _check_coderabbit(errors: list[str]) -> None:
    if not CODERABBIT_CONFIG.exists():
        errors.append(
            "❌ `.coderabbit.yaml` غير موجود.\n"
            "   بلا إعداد يعمل المُراجِع بالافتراضات: يعرف **اللغة** ويجهل **قانون هذا\n"
            "   المستودع**، فيوافق على ما ترفضه البوّابات. القياس في\n"
            "   `.memory/code_quality_truth.md` §3.5."
        )
        return
    config = _load(CODERABBIT_CONFIG, errors)
    if config is None:
        return
    _check_coderabbit_law(config, errors)
    _check_coderabbit_advisory(config, errors)


def main() -> int:
    errors: list[str] = []
    files = _yaml_files()
    if not files:
        print("❌ لا ملفّات سير عمل — البوّابة بلا مرمى (فارضٌ بلا مرمى مرفوض).")
        return 1

    for path in files:
        text = path.read_text(encoding="utf-8")
        doc = _load(path, errors)
        ctx = _FileCtx(
            path=path,
            workflow_permissions=None if doc is None else doc.get("permissions"),
            errors=errors,
        )
        _check_action_versions(ctx, text)
        if doc is None:
            continue

        jobs = _jobs(doc)
        _check_required_ci(ctx, jobs)
        for name, job in jobs.items():
            _check_token_guard(ctx, name, job)
            _check_third_party_write(ctx, name, job)
            _check_qodana_diagnostic(ctx, name, job)

    _check_single_qodana_secret(files, errors)
    _check_coderabbit(errors)

    if errors:
        print("\n".join(errors))
        print(f"\n💥 {len(errors)} خرقاً في سباكة CI.")
        return 1
    print(
        f"✅ ci workflow hygiene: {len(files)} ملفّاً — الإصدارات فوق الأرضية، "
        "ورموز الخدمات محروسة ومنطوقة الغياب، ولا صلاحية كتابة لطرفٍ ثالث، "
        "ولا تكامل خارجي في required-ci، والمُراجِع الخارجي يقرأ الدستور ولا يحجب الدمج."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
