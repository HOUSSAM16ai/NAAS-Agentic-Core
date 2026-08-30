#!/usr/bin/env python3
"""رحلة طالبٍ حقيقية عبر WebSocket — تجريبٌ حيّ لا محاكاة (D-232).

يُقلِع مقابل خادمٍ **يعمل فعلاً** ويقيس ما وُضعت له الميزانيات (D-230):

  • زمن أوّل إطار (`conversation_init`) وأوّل محتوى وأوّل **كائنٍ تفاعلي**
  • إطارٌ نهائيّ **واحد** لكل دور (§6.5) — لا صفر ولا اثنان
  • ⛔ صفر نصّ نظامٍ مخزَّنٍ بدور الطالب (D-229 · ISS-146)
  • ⛔ صفر دورٍ صامت: محتوى فارغ + مكوّنٌ لا يُرسَم (ISS-145)

وتُبلَّغ ولا تحجب: كل مخالفةٍ يسمّي نصُّها بلاغاً **مؤجَّلاً بتصريح** في
`scripts/e2e/deferred_findings.py` — واليوم أحدُها: تسرّبُ نثرٍ لاتيني (ISS-150)،
وهو 🔴 مفتوحٌ بقرارٍ مكتوبٍ بتأجيله. تُطبَع بنصّها في كل تشغيل، ويتغيّر رمز الخروج
وحده. تفصيلُ السبب في رأس ذلك الملفّ (ISS-199).

البروتوكول ثابتٌ بالقانون (§6.6): المفتاح `question` (لا `content`)، والمصادقة عبر
`subprotocols=['jwt', TOKEN]` — ترويسة `Authorization` تُنتِج `NegotiationError`.

    python scripts/e2e/live_student_journey.py --base http://localhost:8000
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import websockets

# جذر المستودع على المسار قبل أي استيرادٍ محلّي. تشغيل `python scripts/e2e/x.py`
# يضع `scripts/e2e/` في `sys.path[0]` لا جذر المستودع، و`live-e2e.yml` لا يضبط
# `PYTHONPATH` — فبدون هذا السطر يموت السكربت بـ`ModuleNotFoundError: app` على
# العدّاء. نفس نمط `honcho_live_probe.py` — مصدرٌ واحد لثلاثتها.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

#: أسماء المكوّنات التي تعرف الواجهة رسمها — المصدر الوحيد هو عقد الخادم.
from app.contracts.streaming import KNOWN_UI_COMPONENTS

#: المصدر الوحيد لما يُبلَّغ ولا يحجب (ISS-199). ⛔ ولا قائمة ثانية هنا (D-186).
from scripts.e2e.deferred_findings import mark, render_deferred, split_problems
from shared.memory import is_system_authored
from shared.ux import FIRST_OBJECT_PAINT_MS, classify_latency

#: رحلة طالبٍ حقيقية — منسوخةٌ من المحادثة 763 في الإنتاج (الأسئلة نفسها).
JOURNEY: tuple[str, ...] = (
    "السلام عليكم",
    "اعطني تمرين الاحتمالات 2024",
    "لم أفهم",
    "كيف نحسب A",
)

_TERMINAL = {"assistant_final", "error", "assistant_error"}

#: ISS-150 هو تسرّبُ **نثرٍ إنجليزي** إلى ردٍّ عربي («WARM-UP: The instruction must be
#: rendered in a coalesced English form…» — ١٩٠٢ حرفاً وصلت طالباً في ضائقة). وليس
#: كلَّ حرفٍ لاتيني: الرياضيات تكتب `\dfrac`، والمحتوى المؤلَّف يحمل تسميةً ثنائية
#: («الاحتمالات (Exercise 1)») — وكلاهما مقصود.
#:
#: فالتوقيع المُميِّز هو **تتابعُ كلماتٍ لاتينية**، لا ورودُ حرفٍ لاتيني. أوّل تشغيلٍ
#: حيّ لهذا السكربت أنتج بلاغَين كاذبَين بالضبط لهذا السبب.
_LATIN_PROSE_WORDS = 3


@dataclass
class TurnResult:
    question: str
    first_frame_s: float | None = None
    first_content_s: float | None = None
    first_object_s: float | None = None
    total_s: float = 0.0
    terminal_frames: int = 0
    content: str = ""
    components: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def _latin_leak(text: str) -> str | None:
    """نثرٌ إنجليزي داخل ردٍّ عربي — ISS-150.

    تُنزَع الرياضيات أوّلاً (`$…$` · `\\(…\\)` · `\\command`) لأن `\\dfrac` تدوينٌ لا
    تسريب، ثمّ يُبحَث عن **تتابع كلماتٍ** لا عن حرفٍ مفرد.
    """
    import re

    if not re.search(r"[؀-ۿ]", text):
        return None  # ردٌّ غير عربي أصلاً — خارج النطاق

    stripped = re.sub(r"\$\$.*?\$\$|\$[^$]*\$", " ", text, flags=re.DOTALL)
    stripped = re.sub(r"\\\(.*?\\\)|\\\[.*?\\\]", " ", stripped, flags=re.DOTALL)
    stripped = re.sub(r"\\[A-Za-z]+", " ", stripped)  # أوامر LaTeX العارية

    match = re.search(
        rf"(?:\b[A-Za-z]{{2,}}\b[\s,:;-]+){{{_LATIN_PROSE_WORDS - 1},}}\b[A-Za-z]{{2,}}\b", stripped
    )
    return match.group(0).strip() if match else None


async def _login(base: str, email: str, password: str) -> str:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{base}/api/security/login", json={"email": email, "password": password}
        )
        response.raise_for_status()
        return str(response.json()["access_token"])


def _absorb_delta(result: TurnResult, payload: dict[str, Any], now: float) -> None:
    if result.first_content_s is None:
        result.first_content_s = now
    result.content += str(payload["content"])


def _absorb_object(result: TurnResult, payload: dict[str, Any], now: float) -> None:
    name = str(payload.get("component", ""))
    result.components.append(name)
    if result.first_object_s is None:
        result.first_object_s = now
    if name not in KNOWN_UI_COMPONENTS:
        result.problems.append(f"مكوّنٌ لا تعرف الواجهة رسمه: {name!r} (ISS-145)")


def _absorb_terminal(result: TurnResult, payload: dict[str, Any]) -> None:
    result.terminal_frames += 1
    if payload.get("content"):
        result.content = result.content or str(payload["content"])


def _absorb_frame(result: TurnResult, event: dict[str, Any], now: float) -> bool:
    """يستوعب إطاراً واحداً في نتيجة الدور. يُرجِع True حين يكون الإطار نهائياً."""
    etype = event.get("type", "")
    payload = event.get("payload") or {}

    if etype == "assistant_delta" and payload.get("content"):
        _absorb_delta(result, payload, now)
    elif etype == "ui_component":
        _absorb_object(result, payload, now)
    elif etype in _TERMINAL:
        _absorb_terminal(result, payload)
        return True
    return False


async def _run_turn(ws_url: str, token: str, question: str) -> TurnResult:
    result = TurnResult(question=question)
    started = time.perf_counter()

    async with websockets.connect(
        ws_url, subprotocols=["jwt", token], open_timeout=30, close_timeout=10
    ) as ws:
        await ws.send(json.dumps({"question": question}))
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=120.0)
            except TimeoutError:
                result.problems.append("انتهت المهلة بلا إطارٍ نهائي — دورٌ معلَّق")
                break

            now = time.perf_counter() - started
            if result.first_frame_s is None:
                result.first_frame_s = now

            try:
                event: dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                result.problems.append("إطارٌ ليس JSON — تسريبُ بنية إلى الدردشة")
                continue

            if _absorb_frame(result, event, now):
                break

    result.total_s = time.perf_counter() - started
    result.problems.extend(_turn_violations(result))
    return result


def _turn_violations(result: TurnResult) -> list[str]:
    """القواعد التي يجب أن يحترمها كل دور — مُجمَّعةً في موضعٍ واحد."""
    problems: list[str] = []
    if result.terminal_frames != 1:
        problems.append(f"إطاراتٌ نهائية = {result.terminal_frames} والعقد يوجب **واحداً** (§6.5)")
    leak = _latin_leak(result.content)
    if leak:
        problems.append(f"شظيّة لاتينية في ردٍّ عربي: {leak!r} (ISS-150)")
    if is_system_authored(result.content):
        problems.append("نصُّ نظامٍ وصل الطالب (D-117/D-229)")
    if not result.content.strip() and not result.components:
        problems.append("دورٌ صامت: لا نصَّ ولا كائن")
    return problems


def _seconds(value: float | None) -> str:
    return f"{value:6.2f}s" if value is not None else "     —"


def _print_turn(turn: TurnResult) -> None:
    components = f"  ({', '.join(turn.components)})" if turn.components else ""
    print(f"   أوّل إطار    {_seconds(turn.first_frame_s)}")
    print(f"   أوّل محتوى   {_seconds(turn.first_content_s)}")
    print(f"   أوّل كائن    {_seconds(turn.first_object_s)}{components}")
    print(f"   الدور كاملاً {_seconds(turn.total_s)}  → {classify_latency(turn.total_s).value}")
    print(f"   نصّ: {len(turn.content)} حرفاً · أطر نهائية: {turn.terminal_frames}")
    for problem in turn.problems:
        print(f"   {mark(problem)}")


def _print_verdict(results: list[TurnResult]) -> int:
    """الحكم النهائي على الرحلة — رمز الخروج هو ما تقرأه CI.

    المخالفة **الحاجبة** تُفشِل، والمؤجَّلة **بتصريح** تُطبَع ولا تُفشِل (ISS-199).
    ⛔ والمؤجَّلة تُذكَر في سطر الحصيلة دائماً — حتى في الرحلة الخضراء: خُضرةٌ لا
    تقول ما رأته تُقرأ «لم يحدث شيء»، وهو الصمت الذي يُقرأ نجاحاً (D-206 L11).
    """
    budget_s = FIRST_OBJECT_PAINT_MS / 1000
    with_object = [turn for turn in results if turn.components]
    fast = [t for t in with_object if t.first_object_s is not None and t.first_object_s <= budget_s]
    blocking, deferred = split_problems(p for turn in results for p in turn.problems)

    print("\n" + "═" * 62)
    print(
        f"أدوار: {len(results)} · تحمل كائناً: {len(with_object)} · "
        f"منها تحت ميزانية {FIRST_OBJECT_PAINT_MS}ms: {len(fast)}"
    )
    print(f"مخالفات حاجبة: {len(blocking)} · مؤجَّلة بتصريح: {len(deferred)}")
    if deferred:
        print("\n⚠️ مؤجَّلة بتصريح — تُبلَّغ ولا تحجب:")
        for line in render_deferred(deferred):
            print(line)
    if blocking:
        print("\n❌ حاجبة:")
        for problem in blocking:
            print(f"   • {problem}")
        return 1
    print("\n✅ كل دورٍ أنهى بإطارٍ نهائيٍّ واحد، بلا نصّ نظام، وبلا دورٍ صامت.")
    return 0


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--email", default="e2e.student@example.dz")
    parser.add_argument("--password", default="Str0ng!Passw0rd")
    args = parser.parse_args()

    token = await _login(args.base, args.email, args.password)
    ws_url = args.base.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_url}/api/chat/ws"

    results: list[TurnResult] = []
    for question in JOURNEY:
        print(f"\n▶ «{question}»", flush=True)
        turn = await _run_turn(ws_url, token, question)
        results.append(turn)
        _print_turn(turn)

    return _print_verdict(results)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
