#!/usr/bin/env python3
"""مصفوفة «يجيب على كل سؤال» — تجريبٌ حيّ لا محاكاة (D-266 · ISS-159).

## لماذا هذا السكربت موجود

طلبُ المالك: «التأكد أن النظام يجيب على كل الأسئلة مهما كانت». والقياس قبله كان
`live_student_journey.py`: **أربعة** أسئلة، كلّها من تمرين احتمالات. أي أنّ المسار
الوحيد المُثبَت حياً هو المسار الذي وقعت فيه ISS-159 — بينما الفيزياء والعلوم
واللغات لم يقسها شيء.

هذا يقيس **العرض** لا العمق: أربع عشرة زاوية عبر ثلاث مواد وثلاث لغات، وكلٌّ منها
يفرض العقد نفسه على الدور.

## ما يفرضه على كل دور

| القاعدة | المصدر |
|---|---|
| إطارٌ نهائي **واحد** — لا صفر ولا اثنان | §6.5 (`_emit_terminal_frames`) |
| محتوى غير فارغ — لا دورَ صامت | ISS-145 · ISS-154 |
| صفر خطف موضوع: سؤال فيزياء لا يُجاب بمفردات الاحتمالات | **ISS-159** |
| صفر نثرٍ لاتيني في ردٍّ عربي | ISS-150 |
| صفر نصّ نظامٍ بدور الطالب | D-117 · D-229 · ISS-146 |
| صفر تسريب إجابة التمرين المرجعي | D-113 · ISS-148 |
| كائنٌ مُولَّد تعرف الواجهة رسمه | ISS-145 (`KNOWN_UI_COMPONENTS`) |

⛔ **الأسرار من البيئة حصراً** — لا مفتاح ولا كلمة مرور في هذا الملفّ (D-265 L8).

    python scripts/e2e/universal_answerability_live.py --base http://localhost:8000
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
import websockets

from app.contracts.streaming import KNOWN_UI_COMPONENTS
from shared.memory import is_system_authored

_TERMINAL = {"assistant_final", "error", "assistant_error"}

#: مفردات العقل الاحتمالي. ظهورُها في جواب سؤالٍ من مادةٍ أخرى **هو** ISS-159.
_PROBABILITY_VOCABULARY = (
    "فضاء العينة",
    "فضاء العيّنة",
    "الحالات الملائمة",
    "التوافيق",
    "كرات",
    "نسحب",
    "الحادثة A",
)

#: أرقام التمرين المرجعي. ظهورُها في أيّ دورٍ لم يسأل عنها تسريبٌ (D-113 · ISS-148).
_REFERENCE_EXERCISE_NUMBERS = ("165", "= 14", "4 + 10")

#: عدد الكلمات اللاتينية المتتابعة التي تُعتبر نثراً مُسرَّباً (منقولٌ من
#: `live_student_journey.py` — الرياضيات تكتب `\dfrac` والتسمية الثنائية مقصودة).
_LATIN_PROSE_WORDS = 3


@dataclass(frozen=True)
class Probe:
    """سؤالٌ واحد وما يجب أن **لا** يظهر في جوابه."""

    question: str
    #: المادة المتوقّعة — للتقرير، ولاشتقاق حظر مفردات الاحتمالات.
    subject: str
    #: هل يُمنع أن يحمل الجواب مفردات الاحتمالات؟ (كل ما ليس رياضيات احتمالية)
    forbid_probability_vocabulary: bool = False
    note: str = ""


#: المصفوفة. كلّ صفٍّ زاويةٌ مختلفة — لا تكرارٌ لنفس المسار بصياغةٍ أخرى (D-207).
MATRIX: tuple[Probe, ...] = (
    Probe("السلام عليكم", "—", note="التحية: مسارٌ حتمي قبل أيّ LLM (D-067)"),
    Probe("اعطني تمرين الاحتمالات 2024", "mathematics", note="الاسترجاع المُفهرَس"),
    Probe("لم أفهم", "mathematics", note="الحيرة: تشخيصٌ لا إعادة اشتقاق (D-113)"),
    Probe("كيف نحسب عدد الحالات الممكنة", "mathematics", note="سؤالٌ إجرائي (D-207)"),
    Probe("اشرح لي قانون أوم", "physics", True, "ISS-159: كان يُجاب بتمرين الكرات"),
    Probe("ما هو مبدأ أرخميدس", "physics", True, "ISS-159: الصنف لا الحالة"),
    Probe("ما الفرق بين الجهد والتيار", "physics", True, "ISS-159: «الفرق» تفتح البوّابة"),
    Probe("ما معنى الرمز Ω في الفيزياء", "physics", True, "ISS-159: الرمز داخل مادته"),
    Probe("ما هو التناضح الخلوي", "natural_sciences", True, "المادة معاملها ٦ (D-193)"),
    Probe("اشرح لي تركيب البروتين", "natural_sciences", True, "علوم الطبيعة"),
    Probe("اشرح لي الدالة الأسية", "mathematics", True, "رياضياتٌ غير احتمالية"),
    Probe("واش راهو الاشتقاق؟", "mathematics", True, "الدارجة الجزائرية"),
    Probe("Explique-moi la loi d'Ohm", "physics", True, "الفرنسية"),
    Probe("كيفاش نحسب مساحة الدائرة", "mathematics", True, "دارجة + خارج المنهاج المباشر"),
)


@dataclass
class TurnResult:
    probe: Probe
    total_s: float = 0.0
    terminal_frames: int = 0
    content: str = ""
    components: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def _latin_leak(text: str) -> str | None:
    """نثرٌ إنجليزي داخل ردٍّ عربي — ISS-150 (تُنزَع الرياضيات أوّلاً)."""
    if not re.search(r"[؀-ۿ]", text):
        return None  # ردٌّ غير عربي أصلاً (سؤال فرنسي) — خارج النطاق
    stripped = re.sub(r"\$\$.*?\$\$|\$[^$]*\$", " ", text, flags=re.DOTALL)
    stripped = re.sub(r"\\\(.*?\\\)|\\\[.*?\\\]", " ", stripped, flags=re.DOTALL)
    stripped = re.sub(r"\\[A-Za-z]+", " ", stripped)
    match = re.search(
        rf"(?:\b[A-Za-z]{{2,}}\b[\s,:;-]+){{{_LATIN_PROSE_WORDS - 1},}}\b[A-Za-z]{{2,}}\b", stripped
    )
    return match.group(0).strip() if match else None


def _turn_violations(result: TurnResult) -> list[str]:
    problems: list[str] = []
    if result.terminal_frames != 1:
        problems.append(f"إطاراتٌ نهائية = {result.terminal_frames} والعقد يوجب **واحداً** (§6.5)")
    if not result.content.strip() and not result.components:
        problems.append("دورٌ صامت: لا نصَّ ولا كائن (ISS-145)")
    leak = _latin_leak(result.content)
    if leak:
        problems.append(f"شظيّة لاتينية في ردٍّ عربي: {leak!r} (ISS-150)")
    if is_system_authored(result.content):
        problems.append("نصُّ نظامٍ وصل الطالب (D-117/D-229)")
    if result.probe.forbid_probability_vocabulary:
        hijacked = [word for word in _PROBABILITY_VOCABULARY if word in result.content]
        if hijacked:
            problems.append(
                f"خطفُ موضوع: مفردات الاحتمالات {hijacked} في سؤال {result.probe.subject} (ISS-159)"
            )
        leaked = [num for num in _REFERENCE_EXERCISE_NUMBERS if num in result.content]
        if leaked:
            problems.append(f"تسريب أرقام التمرين المرجعي {leaked} (D-113 · ISS-148)")
    for name in result.components:
        if name not in KNOWN_UI_COMPONENTS:
            problems.append(f"مكوّنٌ لا تعرف الواجهة رسمه: {name!r} (ISS-145)")
    return problems


async def _login(base: str, email: str, password: str) -> str:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{base}/api/security/login", json={"email": email, "password": password}
        )
        if response.status_code != 200:
            raise SystemExit(f"تعذّر تسجيل الدخول: {response.status_code} — {response.text[:200]}")
        return str(response.json()["access_token"])


async def _run_turn(ws_url: str, token: str, probe: Probe) -> TurnResult:
    result = TurnResult(probe=probe)
    started = time.perf_counter()
    try:
        async with websockets.connect(
            ws_url, subprotocols=["jwt", token], open_timeout=30, close_timeout=10
        ) as ws:
            await ws.send(json.dumps({"question": probe.question}))
            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=150.0)
                except TimeoutError:
                    result.problems.append("انتهت المهلة بلا إطارٍ نهائي — دورٌ معلَّق")
                    break
                try:
                    event: dict[str, Any] = json.loads(raw)
                except json.JSONDecodeError:
                    result.problems.append("إطارٌ ليس JSON — تسريبُ بنية إلى الدردشة")
                    continue
                etype = event.get("type", "")
                payload = event.get("payload") or {}
                if etype == "assistant_delta" and payload.get("content"):
                    result.content += str(payload["content"])
                elif etype == "ui_component":
                    result.components.append(str(payload.get("component", "")))
                elif etype in _TERMINAL:
                    result.terminal_frames += 1
                    if payload.get("content"):
                        result.content = result.content or str(payload["content"])
                    break
    except Exception as exc:
        result.problems.append(f"انقطاع الاتصال: {exc.__class__.__name__}: {exc}")
    result.total_s = time.perf_counter() - started
    result.problems.extend(_turn_violations(result))
    return result


def _print_turn(result: TurnResult) -> None:
    head = result.content.strip().replace("\n", " ")[:90]
    status = "❌" if result.problems else "✅"
    print(
        f"  {status} [{result.probe.subject:16s}] {result.total_s:6.2f}s · {len(result.content):5d} حرفاً"
    )
    print(f"     ↳ {head}…" if head else "     ↳ (بلا نصّ)")
    for problem in result.problems:
        print(f"     ❌ {problem}")


def _verdict(results: list[TurnResult]) -> int:
    failures = [(r.probe.question, p) for r in results for p in r.problems]
    print("\n" + "═" * 70)
    answered = sum(1 for r in results if r.content.strip() or r.components)
    print(f"أدوار: {len(results)} · أجابت: {answered} · مخالفات: {len(failures)}")
    if failures:
        print("\n❌ المخالفات:")
        for question, problem in failures:
            print(f"   • «{question}» — {problem}")
        return 1
    print("✅ كل سؤالٍ أُجيب بإطارٍ نهائيٍّ واحد، من مادته، بلا تسريبٍ ولا دورٍ صامت.")
    return 0


async def main() -> int:
    parser = argparse.ArgumentParser(description="مصفوفة «يجيب على كل سؤال» — D-266")
    parser.add_argument("--base", default=os.environ.get("E2E_BACKEND", "http://localhost:8000"))
    parser.add_argument("--email", default=os.environ.get("DIAG_EMAIL", ""))
    parser.add_argument("--password", default=os.environ.get("DIAG_PASSWORD", ""))
    args = parser.parse_args()

    if not args.email or not args.password:
        raise SystemExit("⛔ بيانات الدخول من البيئة حصراً: DIAG_EMAIL / DIAG_PASSWORD (D-265 L8).")

    token = await _login(args.base, args.email, args.password)
    ws_url = args.base.replace("http://", "ws://").replace("https://", "wss://") + "/api/chat/ws"

    print(f"▶ الخادم: {args.base} · أسئلة: {len(MATRIX)}\n")
    results: list[TurnResult] = []
    for probe in MATRIX:
        print(f"▶ «{probe.question}»  — {probe.note}", flush=True)
        result = await _run_turn(ws_url, token, probe)
        results.append(result)
        _print_turn(result)
    return _verdict(results)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
