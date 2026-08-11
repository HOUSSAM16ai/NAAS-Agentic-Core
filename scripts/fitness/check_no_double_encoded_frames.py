#!/usr/bin/env python3
"""الإطار يُرمَّز مرّةً واحدة — والمُنتِج لا يُسلسل (ISS-156).

## لماذا هذه البوّابة موجودة

`OrchestratorAgent._make_json_event` كانت تُعيد `json.dumps({...}) + "\\n"` — إطاراً
**مُسلسَلاً جاهزاً** — ومُستهلِكها الوحيد (`agent_chat_customer_stream`) يُسلسل ما
يستقبله عبر `_serialize_stream_frame`. فصار كل إطارٍ مُرمَّزاً مرّتين.

والنتيجة على مكدّسٍ كامل بـPostgres حقيقي، مُثبَتةً قبل الإصلاح:

* **32 إطاراً من 34** تحمل إطاراً كاملاً داخل `payload.content` — الطالب يرى JSON خاماً
  بدل جوابه؛
* و`customer_messages` تُخزِّن المظروف حرفياً: صفُّ المساعد كان
  `{"type": "assistant_delta", "payload": {"content": "\\u0627\\u0644"}}` — **تسمّمٌ
  دائم لقاعدة البيانات**، لا خللَ عرضٍ عابر.

ولم يمسك العطبَ **1296 اختباراً أخضر**، لأن البديل في الاختبارات كان يُنتج نصّاً خاماً
لا إطاراً — أي أنّ المرجع جمّد شكلاً لا يُنتجه الوكيل أبداً. كشفه التشغيل الحيّ وحده.

## العقد

قانونان، وكلاهما مفروضٌ ببنية الشيفرة لا بالنيّة:

1. **المُنتِج لا يُسلسل.** أيّ دالّة في خدمة الأوركستريتور تُعيد أو تُنتِج
   `json.dumps({... "type": ...})` تبني إطاراً مُسلسَلاً — والتسلسل مسؤولية طبقة النقل
   وحدها (`stream_serialization.py`). مستثناةٌ صراحةً: طبقة النقل نفسها.
2. **حارس الحدود قائم.** `_classify_agent_chunk` يجب أن يستدعي `_already_a_frame`.
   الدفاع في العمق لا يُحذَف بصمت: مُنتِجٌ يعود غداً فيُسلسل قبل التسليم يجب أن
   يُكتشَف عند الحدّ، لا أن يصل الطالب.

Python 3.12+ مطلوبة: `parse_source` ترفع بدل أن تشهد بنظافة ملفٍّ لم تقرأه
(D-208 · البند ٦) — بوّابةٌ تبتلع `SyntaxError` تُبلِّغ «نظيف» عن ملفٍّ لم تفتحه.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ast_util import parse_source, run_gate

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICE_DIR = REPO_ROOT / "microservices/orchestrator_service/src"

#: طبقة النقل — الموضع الشرعي الوحيد للتسلسل.
TRANSPORT_ALLOWED: frozenset[str] = frozenset({"stream_serialization.py"})

#: حارس الحدود الذي يجب أن يبقى موصولاً.
BOUNDARY_FILE = SERVICE_DIR / "api/agent_chat_customer_stream.py"
BOUNDARY_CALLER = "_classify_agent_chunk"
BOUNDARY_GUARD = "_already_a_frame"


def _is_json_dumps(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "dumps"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "json"
    )


def _builds_a_frame(call: ast.Call) -> bool:
    """صحيحٌ إن كان أوّل وسيطٍ قاموساً حرفياً يحمل مفتاح `type` — أي إطاراً."""
    if not call.args:
        return False
    first = call.args[0]
    if not isinstance(first, ast.Dict):
        return False
    return any(isinstance(key, ast.Constant) and key.value == "type" for key in first.keys if key)


def _serializes_a_frame(value: ast.expr) -> bool:
    """صحيحٌ إن كانت القيمة `json.dumps({...type...})` — وحدها أو مع `+ "\\n"`."""
    candidates: list[ast.AST] = [value]
    if isinstance(value, ast.BinOp):
        candidates += [value.left, value.right]
    return any(
        _is_json_dumps(node) and _builds_a_frame(node)  # type: ignore[arg-type]
        for node in candidates
    )


def _file_violations(path: Path) -> list[str]:
    rel = path.relative_to(REPO_ROOT).as_posix()
    return [
        f"❌ {rel}:{node.lineno} يُعيد/يُنتِج إطاراً **مُسلسَلاً**.\n"
        f"   أعِد القاموس نفسه — التسلسل مسؤولية `stream_serialization.py` وحدها.\n"
        f"   (ISS-156: هذا بالضبط ما جعل الطالب يرى JSON خاماً وسمّم `customer_messages`.)"
        for node in ast.walk(parse_source(path))
        if isinstance(node, ast.Return | ast.Yield)
        and node.value is not None
        and _serializes_a_frame(node.value)
    ]


def _serialized_frame_violations() -> list[str]:
    """القانون 1: مُنتِجٌ يُسلسل إطاراً = انتهاك."""
    out: list[str] = []
    for path in sorted(SERVICE_DIR.rglob("*.py")):
        if path.name not in TRANSPORT_ALLOWED:
            out += _file_violations(path)
    return out


def _boundary_guard_violations() -> list[str]:
    """القانون 2: حارس الحدود لم يُحذَف."""
    tree = parse_source(BOUNDARY_FILE)
    rel = BOUNDARY_FILE.relative_to(REPO_ROOT).as_posix()
    classifier = next(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            and node.name == BOUNDARY_CALLER
        ),
        None,
    )
    if classifier is None:
        return [f"❌ {rel}: لم تُعثَر الدالّة {BOUNDARY_CALLER!r} — حارس الحدود مفقود."]
    calls = {
        node.func.id
        for node in ast.walk(classifier)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    if BOUNDARY_GUARD not in calls:
        return [
            f"❌ {rel}: {BOUNDARY_CALLER} لم يعد يستدعي {BOUNDARY_GUARD!r}.\n"
            f"   الدفاع في العمق لا يُحذَف بصمت — مُنتِجٌ يُسلسل قبل التسليم يجب أن\n"
            f"   يُكتشَف عند الحدّ لا أن يصل الطالب (ISS-156)."
        ]
    return []


def main() -> int:
    errors = _serialized_frame_violations() + _boundary_guard_violations()
    if errors:
        print("\n".join(errors))
        print(
            "\n📌 القاعدة: المُنتِج يبني إطاراً، وطبقة النقل وحدها تُسلسله. "
            "مُثبَتٌ حيّاً — 32/34 إطاراً و صفٌّ مسموم في قاعدة إنتاجٍ حقيقية."
        )
        return 1
    print("✅ frame encoding: مُنتِجٌ واحد لا يُسلسل، وحارس الحدود موصول — ترميزٌ واحد.")
    return 0


if __name__ == "__main__":
    sys.exit(run_gate(main))
