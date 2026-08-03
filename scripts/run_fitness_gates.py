#!/usr/bin/env python3
"""يُشغّل **كل** بوّابات اللياقة التي تُشغّلها وظيفة `guardrails` في CI — مقروءةً منها (ISS-148).

## لماذا هذا السكربت موجود

`make guardrails` كان يُشغّل `scripts/ci_guardrails.py` وحده — **واحدة** من ~٢٩ فحصاً
تُشغّلها وظيفة CI الحاملة الاسمَ نفسه. و`README.md` يعرض أربعة أسطر يصفها بأنها «تُطابق
وظائف required-ci»، و`CONTRIBUTING.md` يذكر ثلاثة سكربتات. ثلاث وثائق، ثلاث مجموعات
مختلفة، ولا واحدة منها كاملة.

فالمساهم يقرأ أيّها شاء، يراه أخضر، ثمّ يُفاجأ بأحمر بعد الدفع. وهذه أسوأ حالة لبوّابة:
لا هي تحمي (لأنها لا تعمل محلّياً)، ولا هي محايدة (لأنها تُعطي طمأنينةً كاذبة) — فيتعلّم
الناس تجاهلها.

## كيف يتجنّب هذا التقادم

لا يحمل قائمةً خاصّةً به. يقرأ `.github/workflows/ci.yml` ويستخرج كل سطر
`python scripts/fitness/*.py` من وظيفة `guardrails`. فإضافةُ بوّابة إلى CI تجعلها تعمل
هنا **تلقائياً** — القائمة الثانية التي كان يمكن أن تتفرّق غير موجودة أصلاً.

## التشغيل

    make gates          # أو
    python scripts/run_fitness_gates.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = REPO_ROOT / ".github/workflows/ci.yml"

_GATE_LINE = re.compile(r"^\s+python (scripts/fitness/[\w./-]+\.py)\s*$")
_JOB_LINE = re.compile(r"^  ([\w-]+):\s*$")

#: الوظيفة المقروءة. البوّابات المرتبطة ببناءٍ (`check_bundle_budget` تحتاج
#: `frontend/.next`) تعيش في وظائف أخرى وتبقى خارج هذا المُشغِّل **بسببٍ منطوق**:
#: أمرٌ محلّي يتطلّب `npm run build` قبله ليس أمراً يُشغَّل قبل كل دفع.
_TARGET_JOB = "guardrails"


def _gates_from_ci() -> list[str]:
    """بوّابات اللياقة داخل وظيفة `guardrails` — بترتيب ورودها، بلا تكرار."""
    seen: list[str] = []
    in_target = False
    for line in CI_WORKFLOW.read_text(encoding="utf-8").splitlines():
        job = _JOB_LINE.match(line)
        if job:
            in_target = job.group(1) == _TARGET_JOB
            continue
        if not in_target:
            continue
        match = _GATE_LINE.match(line)
        if match and match.group(1) not in seen:
            seen.append(match.group(1))
    return seen


#: ISS-149 (F2) — أدنى إصدار Python **مُشتَقّاً** من `pyproject.toml`، لا مكتوباً هنا.
#: المشروع يستعمل صيغة PEP 695 (`class BaseSkill[InT, OutT]`) وهي 3.12+، و`ruff`
#: يُصرِّح ذلك بـ`target-version`. فالقيمة موجودة ومصدرُها واحد — الناقص كان **فرضها**.
_PYPROJECT = REPO_ROOT / "pyproject.toml"
_TARGET_VERSION = re.compile(r'^target-version\s*=\s*"py(\d)(\d+)"', re.MULTILINE)


def _required_python() -> tuple[int, int] | None:
    """أدنى إصدار مدعوم كما يُصرِّحه `pyproject.toml` — لا رقمٌ ثانٍ يتقادم (D-192)."""
    match = _TARGET_VERSION.search(_PYPROJECT.read_text(encoding="utf-8"))
    return (int(match.group(1)), int(match.group(2))) if match else None


def _check_interpreter() -> int:
    """يرفض التشغيل على مفسّرٍ أقدم من المُصرَّح — بدل عطبٍ صامت.

    ISS-149 (F2): على Python 3.11 لا يُحلَّل ملفٌّ يستعمل PEP 695. أربعُ بوّابات
    تسقط عندها بـ`SyntaxError` غامض، و**ثمانٍ** تبتلع الخطأ وتُبلِّغ صفر انتهاكات —
    أي أنها تمرّ **خضراءَ كاذبة** على شجرةٍ لم تقرأها (F1). فمساهمٌ على 3.11 يرى
    مشروعاً «سليماً» وهو أعمى تماماً. رسالةٌ صريحة أنفع من خمسين نتيجةً كاذبة.
    """
    required = _required_python()
    if required is None:
        print("❌ pyproject.toml بلا `target-version` — أدنى إصدار Python غير مُصرَّح.")
        return 1
    if sys.version_info[:2] < required:
        current = ".".join(str(part) for part in sys.version_info[:2])
        wanted = ".".join(str(part) for part in required)
        print(
            f"❌ Python {current} أقدم من المطلوب {wanted}+ (pyproject.toml:target-version).\n"
            f"   المشروع يستعمل صيغة PEP 695، فالملفّات التي تحملها **لا تُحلَّل** على\n"
            f"   {current}: بوّابات تسقط بخطأ غامض وأخرى تُبلِّغ صفر انتهاكات عن شجرةٍ\n"
            f"   لم تقرأها. شغّل البوّابات بمفسّر {wanted} أو أحدث."
        )
        return 1
    return 0


def main() -> int:
    if _check_interpreter():
        return 1

    gates = _gates_from_ci()
    if not gates:
        print("❌ لم تُقرأ أي بوّابة من ci.yml — تغيّر شكل الوظيفة؟")
        return 1

    print(f"🚦 {len(gates)} بوّابة، مقروءةً من {CI_WORKFLOW.name}\n")
    failed: list[str] = []
    for gate in gates:
        # argv ثابتة مقروءة من ملفّ المستودع، و`shell=False` — لا حقن (D-187).
        result = subprocess.run(
            [sys.executable, gate],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            print(f"  ✅ {gate}")
            continue
        failed.append(gate)
        print(f"  ❌ {gate}")
        for line in (result.stdout + result.stderr).strip().splitlines()[:12]:
            print(f"       {line}")

    print()
    if failed:
        print(f"❌ {len(failed)} من {len(gates)} بوّابة فشلت:")
        for gate in failed:
            print(f"  • {gate}")
        return 1
    print(f"✅ كل البوّابات الـ{len(gates)} خضراء.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
