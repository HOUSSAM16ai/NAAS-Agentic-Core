#!/usr/bin/env python3
"""رحلة طالبٍ حقيقية عبر WebSocket — تجريبٌ حيّ لا محاكاة (D-232).

يُقلِع مقابل خادمٍ **يعمل فعلاً** ويقيس ما وُضعت له الميزانيات (D-230):

  • زمن أوّل إطار (`conversation_init`) وأوّل محتوى وأوّل **كائنٍ تفاعلي**
  • إطارٌ نهائيّ **واحد** لكل دور (§6.5) — لا صفر ولا اثنان
  • ⛔ صفر تسريبٍ لاتيني في ردٍّ عربي (ISS-150)
  • ⛔ صفر نصّ نظامٍ مخزَّنٍ بدور الطالب (D-229 · ISS-146)
  • ⛔ صفر دورٍ صامت: محتوى فارغ + مكوّنٌ لا يُرسَم (ISS-145)

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
from typing import Any

import httpx
import websockets

#: أسماء المكوّنات التي تعرف الواجهة رسمها — المصدر الوحيد هو عقد الخادم.
from app.contracts.streaming import KNOWN_UI_COMPONENTS
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


def _absorb_frame(result: TurnResult, event: dict[str, Any], now: float) -> bool:
    """يستوعب إطاراً واحداً في نتيجة الدور. يُرجِع True حين يكون الإطار نهائياً."""
    etype = event.get("type", "")
    payload = event.get("payload") or {}

    if etype == "assistant_delta" and payload.get("content"):
        if result.first_content_s is None:
            result.first_content_s = now
        result.content += str(payload["content"])
        return False

    if etype == "ui_component":
        name = str(payload.get("component", ""))
        result.components.append(name)
        if result.first_object_s is None:
            result.first_object_s = now
        if name not in KNOWN_UI_COMPONENTS:
            result.problems.append(f"مكوّنٌ لا تعرف الواجهة رسمه: {name!r} (ISS-145)")
        return False

    if etype in _TERMINAL:
        result.terminal_frames += 1
        if payload.get("content"):
            result.content = result.content or str(payload["content"])
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

    if result.terminal_frames != 1:
        result.problems.append(
            f"إطاراتٌ نهائية = {result.terminal_frames} والعقد يوجب **واحداً** (§6.5)"
        )
    leak = _latin_leak(result.content)
    if leak:
        result.problems.append(f"شظيّة لاتينية في ردٍّ عربي: {leak!r} (ISS-150)")
    if is_system_authored(result.content):
        result.problems.append("نصُّ نظامٍ وصل الطالب (D-117/D-229)")
    if not result.content.strip() and not result.components:
        result.problems.append("دورٌ صامت: لا نصَّ ولا كائن")

    return result


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

        def fmt(value: float | None) -> str:
            return f"{value:6.2f}s" if value is not None else "     —"

        print(f"   أوّل إطار    {fmt(turn.first_frame_s)}")
        print(f"   أوّل محتوى   {fmt(turn.first_content_s)}")
        print(
            f"   أوّل كائن    {fmt(turn.first_object_s)}"
            + (f"  ({', '.join(turn.components)})" if turn.components else "")
        )
        print(f"   الدور كاملاً {fmt(turn.total_s)}  → {classify_latency(turn.total_s).value}")
        print(f"   نصّ: {len(turn.content)} حرفاً · أطر نهائية: {turn.terminal_frames}")
        for problem in turn.problems:
            print(f"   ❌ {problem}")

    print("\n" + "═" * 62)
    failures = [p for t in results for p in t.problems]
    objects = sum(1 for t in results if t.components)
    budget_s = FIRST_OBJECT_PAINT_MS / 1000
    fast_objects = sum(
        1 for t in results if t.first_object_s is not None and t.first_object_s <= budget_s
    )
    print(
        f"أدوار: {len(results)} · تحمل كائناً: {objects} · "
        f"منها تحت ميزانية {FIRST_OBJECT_PAINT_MS}ms: {fast_objects}"
    )
    if failures:
        print(f"❌ مخالفات: {len(failures)}")
        return 1
    print("✅ كل دورٍ أنهى بإطارٍ نهائيٍّ واحد، بلا تسريبٍ لاتيني، وبلا دورٍ صامت.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
