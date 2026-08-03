#!/usr/bin/env python3
"""يمنع نموّ منطق النطاق داخل مُوجِّهات FastAPI — ratchet (D-192 · roadmap §6.5.د D6).

**لماذا هذه البوّابة موجودة:**

سؤال حدودٍ مفتوح في خارطة الطريق: هل `app/` **بوّابة** أم **نواة منصّة**؟ المسح أعطى
جواباً غير مريح: `app/api/routers/customer_chat.py:chat_stream_ws` دالّةٌ واحدة بطول
**662 سطراً** تفتح جلسات قاعدة بيانات بنفسها، وتفكّ قرار السياسة التربوية، وتبني سلاسل
التدخّل، وتستدعي `TutorStateService(...).record_turn(...)` بتسع وسائط نطاق — أي أن
المُوجِّه صار عقلاً تربوياً. ومثله `admin.py:chat_stream_ws` (440 سطراً).

**قرار هذه الجولة:** الحدّ يُسمّى ويُسيَّج، **ولا يُفكَّك الآن**. تفكيك أخطر مسارٍ حيّ
على المنصّة (WebSocket الطالب) في جولةٍ تحمل أصلاً إصلاحاً تربوياً وأمنياً هو مقامرة؛
والقاعدة القائمة (§6.5: كاتبٌ واحد · إطار نهائي واحد) تحرس سلوكه بالفعل. فالمطلوب هنا
منع **النموّ**: الأرقام الحالية مُجمَّدة وتتقلّص فقط، على نمط D-105/D-187/D-189.

**ما يُعَدّ «منطق نطاق» في مُوجِّه:** فتح جلسة قاعدة بيانات · بناء استعلام ORM · استدعاء
خدمة حالة الطالب مباشرةً. هذه الثلاثة هي ما يجعل المُوجِّه مالكاً لقواعد العمل بدل أن
يكون ناقلاً لها.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ast_util import parse_source, run_gate

REPO_ROOT = Path(__file__).resolve().parents[2]
ROUTERS_DIR = REPO_ROOT / "app/api/routers"
DEBT_FILE = Path(__file__).with_name("router_domain_debt.json")

#: استدعاءات تدلّ على منطق نطاق داخل طبقة النقل.
DOMAIN_CALLS = ("async_session_factory", "TutorStateService", "select")


def _count_domain_calls(path: Path) -> int:
    # ISS-149 (F1): يرفع — صفرُ نداءات عن ملفٍّ لم يُقرأ يُقلّص الدَّين زوراً.
    tree = parse_source(path)
    total = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = (
            func.id
            if isinstance(func, ast.Name)
            else func.attr
            if isinstance(func, ast.Attribute)
            else ""
        )
        if name in DOMAIN_CALLS:
            total += 1
    return total


def _scan() -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in sorted(ROUTERS_DIR.rglob("*.py")):
        found = _count_domain_calls(path)
        if found:
            counts[path.relative_to(REPO_ROOT).as_posix()] = found
    return counts


def main() -> int:
    current = _scan()

    if "--update" in sys.argv:
        DEBT_FILE.write_text(
            json.dumps(dict(sorted(current.items())), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"✅ baseline written: {len(current)} routers, {sum(current.values())} domain calls")
        return 0

    if not DEBT_FILE.is_file():
        print(f"❌ ملفّ الدَّين مفقود: {DEBT_FILE.name}. شغّل `--update` مرّة لتثبيت الأساس.")
        return 1
    frozen: dict[str, int] = json.loads(DEBT_FILE.read_text(encoding="utf-8"))

    errors: list[str] = []
    for rel, found in sorted(current.items()):
        allowed = frozen.get(rel, 0)
        if found > allowed:
            errors.append(
                f"❌ {rel}: {found} استدعاء نطاق بينما المسموح {allowed}.\n"
                f"   المُوجِّه طبقة نقل: انقل المنطق إلى `app/services/` "
                f"(نمط `customer_chat_support/`) بدل تنميته هنا."
            )
    for rel, allowed in sorted(frozen.items()):
        if current.get(rel, 0) < allowed:
            errors.append(
                f"❌ {rel}: صار {current.get(rel, 0)} بينما الدَّين المُجمَّد {allowed}.\n"
                f"   حدِّث الرقم (`--update`) — الخريطة تتبع الواقع أو تتقادم بصمت (D-188)."
            )

    if errors:
        print("\n".join(errors))
        print("\n📌 D-192 (roadmap D6): حدّ `app/` مُسمّى ومُسيَّج — منطق النطاق لا ينمو في المُوجِّهات.")
        return 1

    print(
        f"✅ router boundary: {sum(current.values())} استدعاء نطاق مُجمَّد "
        f"في {len(current)} مُوجِّهاً — لا نموّ."
    )
    return 0


if __name__ == "__main__":
    sys.exit(run_gate(main))
