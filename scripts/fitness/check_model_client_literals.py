#!/usr/bin/env python3
"""عميل النماذج لا يحمل حرفية نموذج — ISS-157.

`services/llm/client.py` كان يُصلِّب `nvidia/nemotron-3-nano-30b-a3b:free`، وهو
النموذج الذي يمنع D-067 أن يكون PRIMARY (ISS-079). ولا نشرةَ تضبط
`ORCHESTRATOR_LLM_MODEL`، فكان المحظور هو ما يعمل فعلاً — بلا سلسلة سقوط.

و`check_model_chain_parity` لم تكن تراه: مرماها ملفَّا `ai_config.py` وحدهما،
بينما هذا ملفٌّ **ثالث يحمل نفس القرار**. صنفُ العطب نفسه الذي كلّف المستودع
ISS-148: **فارضٌ بمرمىً أضيق من القاعدة التي يحرسها.**

القاعدة: القرار الواحد له موطنٌ واحد (D-186) — العميل يقرأ من `ActiveModels`،
والحرفية تعيش في `ai_config.py` حيث تحرسها بوّابة التكافؤ.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ast_util import parse_source, run_gate

REPO_ROOT = Path(__file__).resolve().parents[2]

#: عملاء النماذج المحكومون بهذه القاعدة.
MODEL_CLIENTS: tuple[str, ...] = ("microservices/orchestrator_service/src/services/llm/client.py",)


def _looks_like_model_id(value: str) -> bool:
    """مُعرِّف نموذج OpenRouter: `provider/name:free` — بلا مسافات وقصير."""
    return "/" in value and ":free" in value and " " not in value and len(value) < 120


def _model_literals(rel_path: str) -> list[tuple[int, str]]:
    """كل حرفية تبدو مُعرِّف نموذجٍ في الملفّ، بسطرها."""
    tree = parse_source(REPO_ROOT / rel_path)
    return [
        (node.lineno, node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and _looks_like_model_id(node.value)
    ]


def main() -> int:
    errors: list[str] = []
    for rel_path in MODEL_CLIENTS:
        for lineno, value in _model_literals(rel_path):
            errors.append(f"❌ {rel_path}:{lineno} يُصلِّب نموذجاً: {value!r}")

    if errors:
        print("\n".join(errors))
        print(
            "\n📌 اقرأ من `ActiveModels` بدل الحرفية — القرار الواحد له موطنٌ واحد (D-186).\n"
            "   ISS-157: حرفيةٌ هنا جعلت النموذجَ المحظور بـD-067 هو الافتراضي الحيّ."
        )
        return 1

    print(f"✅ model clients: {len(MODEL_CLIENTS)} ملفّاً بلا حرفية نموذج — مصدرٌ واحد.")
    return 0


if __name__ == "__main__":
    sys.exit(run_gate(main))
