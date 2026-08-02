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


def main() -> int:
    gates = _gates_from_ci()
    if not gates:
        print("❌ لم تُقرأ أي بوّابة من ci.yml — تغيّر شكل الوظيفة؟")
        return 1

    print(f"🚦 {len(gates)} بوّابة، مقروءةً من {CI_WORKFLOW.name}\n")
    failed: list[str] = []
    for gate in gates:
        result = subprocess.run(  # noqa: S603 — argv ثابتة من ملفّ المستودع، بلا صدفة
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
