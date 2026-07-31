#!/usr/bin/env python3
"""verify_iss140_e2e — تحقّق حيّ من إغلاق ISS-140 ج/د/د-2 (D-191) عبر WebSocket الحقيقي.

## لماذا هذا السكربت

D-190 دفع ثمن درسٍ منهجي: **بطارية لا تفحص الصلة تُصادق على كارثة.** بطاريةٌ فحصت
البنية (إطار نهائي واحد · عربي · صفر انهيار) أعطت **8/8 كاذبة** بينما كان سؤال الفيزياء
يتلقّى قائمة تشخيص الاحتمالات. لذلك كل تأكيد هنا يفحص **صلة المحتوى بالسؤال**:

* تمرين الطالب يُشرَح بأرقام **الطالب** — وأرقام التمرين المخزَّن ممنوعة (ISS-140 د).
* «لم أفهم» على تمرينه تبقى على تمرينه — لا تصفير للموضوع (ISS-140 د-2).
* كل موضوع يُجاب في مادته — لا اختطاف للاحتمالات (ISS-140 أ · D-190).
* «يجيب على كل سؤال»: إطار نهائي واحد لكل دور، وجوابٌ غير فارغ.

## التشغيل

    export E2E_BACKEND=http://localhost:8000
    export E2E_EMAIL=... E2E_PASSWORD=...        # لا تُطبَع القيم أبداً
    python scripts/verify_iss140_e2e.py

يفشل بمخرَج غير صفري عند أوّل خرقٍ للصلة — لا «تحذير» يمرّ.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from typing import Any

BACKEND = os.environ.get("E2E_BACKEND", "http://localhost:8000")
EMAIL = os.environ.get("E2E_EMAIL", "")
PASSWORD = os.environ.get("E2E_PASSWORD", "")

#: تمرين يكتبه الطالب بنفسه — أرقامه ليست أرقام التمرين المخزَّن.
STUDENT_EXERCISE = (
    "كيس يحتوي على 12 كرة: 5 حمراء و4 خضراء و3 صفراء. "
    "نسحب 3 كرات في آن واحد. ما احتمال أن تكون الكرات الثلاث من نفس اللون؟"
)

#: بصمات التمرين المخزَّن (بكالوريا 2024). ظهورها على تمرين الطالب = ISS-140 د.
CANONICAL_FINGERPRINTS: tuple[str, ...] = ("بيضاء", "165", "11×10×9", "C_{11}")

#: ردود التصفير التي يحرّمها D-184 («البؤرة لاصقة»).
TOPIC_RESET_MARKERS: tuple[str, ...] = (
    "لم تُقدِّم سؤالاً محدداً",
    "لم تقدم سؤالاً محدداً",
    "لم تقدم سؤالا محددا",
)

#: بطارية الصلة الموضوعية: (السؤال، كلماتٌ يجب أن تظهر إحداها، كلماتٌ ممنوعة).
RELEVANCE_BATTERY: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("اشرح لي قانون أوم", ("أوم", "التيار", "الجهد", "المقاومة"), ("كرات", "كيس", "165")),
    ("اشرح لي مبدأ أرخميدس", ("أرخميدس", "طفو", "سائل", "دافعة"), ("كرات", "كيس", "165")),
    ("ما الفرق بين الحمض والقاعدة", ("حمض", "قاعدة", "pH"), ("كرات", "كيس", "165")),
    ("احسب تكامل الدالة f(x) = x^2 + 3x من 0 إلى 2", ("تكامل", "x", "∫"), ("كرات", "كيس")),
    ("السلام عليكم", ("سلام", "مرحب", "أهل"), ("كرات", "165")),
)


def _ok(message: str) -> None:
    print(f"✅ {message}")


def _fail(message: str) -> None:
    print(f"❌ {message}")


def _login() -> str:
    """يسجّل الدخول ويُرجع رمز JWT (لا تُطبَع القيمة أبداً)."""
    import httpx

    response = httpx.post(
        f"{BACKEND}/api/security/login",
        json={"email": EMAIL, "password": PASSWORD},
        timeout=30.0,
    )
    response.raise_for_status()
    return str(response.json()["access_token"])


class Session:
    """جلسة محادثة تحفظ ``conversation_id`` بين الأدوار — وهو **شرط صحّة البطارية**.

    درسٌ دُفِع ثمنه في هذه الجولة: أوّل نسخة من هذا السكربت لم تُعِد إرسال
    ``conversation_id``، فأنشأ الخادم محادثةً جديدة لكل دور (رسالتان في كلٍّ منها)،
    فوصل الدور الثاني **بلا تاريخ**. فحُكِم على المنتج بأنه يُسرّب أرقام التمرين
    المخزَّن بينما الخلل في أداة القياس. وهو نفس درس D-190 بمفتاحٍ جديد: بطاريةٌ لا
    تتحقّق من **مقدّماتها** لا تُثبت شيئاً. الواجهة الحقيقية تُعيد إرساله
    (``useAgentSocket.js:400``) — فالمحاكاة يجب أن تفعل مثلها.
    """

    def __init__(self, websocket: Any) -> None:
        self.websocket = websocket
        self.conversation_id: int | None = None

    async def turn(self, question: str) -> tuple[str, list[str], list[dict]]:
        """يرسل سؤالاً ويجمع النصّ حتى الإطار النهائي. يُرجع (النصّ، الأطر، مكوّنات UI)."""
        payload_out: dict[str, object] = {
            "question": question,
            "client_request_id": str(uuid.uuid4()),
        }
        if self.conversation_id is not None:
            payload_out["conversation_id"] = self.conversation_id
        await self.websocket.send(json.dumps(payload_out))
        chunks: list[str] = []
        frames: list[str] = []
        components: list[dict] = []
        while True:
            raw = await asyncio.wait_for(self.websocket.recv(), timeout=180.0)
            event = json.loads(raw)
            etype = str(event.get("type", ""))
            frames.append(etype)
            payload = event.get("payload") or {}
            incoming = payload.get("conversation_id")
            if isinstance(incoming, int):
                self.conversation_id = incoming
            if etype == "assistant_delta":
                chunks.append(str(payload.get("content", "")))
            elif etype == "ui_component":
                components.append(payload)
            elif etype in {"assistant_final", "complete", "error"}:
                final = str(payload.get("content", ""))
                if final and not chunks:
                    chunks.append(final)
                break
        return "".join(chunks), frames, components


def _terminal_count(frames: list[str]) -> int:
    return sum(1 for f in frames if f in {"assistant_final", "complete", "error"})


async def _open(token: str) -> Session:
    import websockets

    url = f"{BACKEND.replace('http', 'ws')}/api/chat/ws?token={token}&session_id={uuid.uuid4()}"
    websocket = await websockets.connect(url, ping_interval=None, open_timeout=30)
    session = Session(websocket)
    init = json.loads(await asyncio.wait_for(websocket.recv(), timeout=30.0))
    incoming = (init.get("payload") or {}).get("conversation_id")
    if isinstance(incoming, int):
        session.conversation_id = incoming
    return session


async def check_student_own_exercise(token: str) -> bool:
    """ISS-140 د + د-2: تمرين الطالب يُشرَح بأرقامه، والبؤرة تصمد أمام «لم أفهم»."""
    passed = True
    session = await _open(token)
    websocket = session.websocket
    try:
        _, frames, _ = await session.turn(STUDENT_EXERCISE)
        if _terminal_count(frames) != 1:
            _fail(f"الدور الأول: {_terminal_count(frames)} إطاراً نهائياً (المطلوب 1)")
            passed = False

        for question in ("لماذا نضرب 12×11×10", "لم أفهم", "مفهمتش", "كيف حسبنا 5"):
            text, frames, _ = await session.turn(question)
            leaks = [f for f in CANONICAL_FINGERPRINTS if f in text]
            resets = [m for m in TOPIC_RESET_MARKERS if m in text]
            if _terminal_count(frames) != 1:
                _fail(f"{question!r}: {_terminal_count(frames)} إطاراً نهائياً")
                passed = False
            elif not text.strip():
                _fail(f"{question!r}: جوابٌ فارغ — «يجيب على كل سؤال» مخروق")
                passed = False
            elif leaks:
                _fail(f"{question!r}: تسريب أرقام التمرين المخزَّن {leaks} (ISS-140 د)")
                passed = False
            elif resets:
                _fail(f"{question!r}: تصفير الموضوع {resets} (ISS-140 د-2 · D-184)")
                passed = False
            else:
                _ok(f"{question!r} → {len(text)} حرفاً على تمرين الطالب، بلا تسريب")
    finally:
        await websocket.close()
    return passed


async def check_no_promise_without_payload(token: str) -> bool:
    """ISS-140 ج: وعدٌ بشرح بصري لا يُبَثّ بلا حمولة."""
    session = await _open(token)
    try:
        await session.turn(STUDENT_EXERCISE)
        text, _, components = await session.turn("لم أفهم اشرح لي بصرياً")
    finally:
        await session.websocket.close()
    promised = "🪄" in text
    if promised and not components:
        _fail(f"وعدٌ بصري ({len(text)} حرفاً) بلا أيّ `ui_component` — ISS-140 ج")
        return False
    if promised:
        _ok(f"الوعد البصري مصحوبٌ بحمولة ({components[0].get('component')})")
    else:
        _ok(f"لا وعد بصري بلا حمولة — شرحٌ نصّي بدله ({len(text)} حرفاً)")
    return True


async def check_relevance(token: str) -> bool:
    """كل موضوع يُجاب في مادته — لا اختطاف (ISS-140 أ · D-190)."""
    passed = True
    for question, expected, forbidden in RELEVANCE_BATTERY:
        session = await _open(token)  # محادثة جديدة: صفر حالة سابقة
        try:
            text, frames, _ = await session.turn(question)
        finally:
            await session.websocket.close()
        hijack = [f for f in forbidden if f in text]
        if _terminal_count(frames) != 1:
            _fail(f"{question!r}: {_terminal_count(frames)} إطاراً نهائياً")
            passed = False
        elif not text.strip():
            _fail(f"{question!r}: جوابٌ فارغ")
            passed = False
        elif hijack:
            _fail(f"{question!r}: اختطاف الموضوع — ظهر {hijack}")
            passed = False
        elif not any(word in text for word in expected):
            _fail(f"{question!r}: لا صلة — غابت كل {expected}\n   {text[:160]!r}")
            passed = False
        else:
            _ok(f"{question!r} → {len(text)} حرفاً في مادته")
    return passed


async def main() -> int:
    if not EMAIL or not PASSWORD:
        print("❌ E2E_EMAIL / E2E_PASSWORD غير مضبوطين (تُقرأ من البيئة حصراً).")
        return 2
    token = _login()
    results = {
        "student-own-exercise (ISS-140 د/د-2)": await check_student_own_exercise(token),
        "promise-requires-payload (ISS-140 ج)": await check_no_promise_without_payload(token),
        "topical-relevance (ISS-140 أ · D-190)": await check_relevance(token),
    }
    print("\n── الخلاصة ──")
    for name, ok in results.items():
        print(f"{'✅' if ok else '❌'} {name}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
