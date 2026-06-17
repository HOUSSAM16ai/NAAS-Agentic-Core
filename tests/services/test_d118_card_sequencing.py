"""D-118 — تسلسل بطاقات التتبّع بعد الإطار النهائي للمحتوى.

الكارثة (transcript حي): بطاقة إتقان BKT (`bkt_hint_display`) وبطاقة المسار
التعلّمي (`learning_path_card`) كانتا تُبثّان من background task متزامن
(`asyncio.create_task(_evaluate_and_emit_bkt)`) **في منتصف** بثّ نص التمرين،
فتُقطّعانه لفقاعات مكسورة («خمس كرات خضراء... 0، 1» يُفصَل عن «، 1، 3، 4»).

الإصلاح (D-118): فصل التقييم عن الإصدار. `_evaluate_bkt_cards` يُقيّم ويُرجِع
حمولات البطاقات فقط (بلا بثّ/حفظ)؛ المنسّق يُصدِرها **بعد** `_emit_terminal_frames`
عبر `_locked_send_json` (D-096 محفوظ) → بطاقات نظيفة أسفل المحتوى، صفر تشظٍّ.

stdlib + source-inspection — يعمل في الـ sandbox بلا pydantic/DB.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CHAT_SRC = (REPO_ROOT / "app/api/routers/customer_chat.py").read_text(encoding="utf-8")


# ── 1. التقييم منفصل عن الإصدار ────────────────────────────────────────────────
class TestEvalSeparatedFromEmit:
    def test_eval_function_renamed_and_returns_cards(self) -> None:
        # الاسم القديم المُصدِر mid-stream يجب أن يختفي؛ الجديد يُرجِع list (بلا بثّ).
        assert "async def _evaluate_and_emit_bkt" not in CHAT_SRC
        assert "async def _evaluate_bkt_cards(" in CHAT_SRC
        seg = CHAT_SRC[CHAT_SRC.index("async def _evaluate_bkt_cards(") :]
        seg = seg[: seg.index("\n\n\n")] if "\n\n\n" in seg else seg
        assert "-> list[dict[str, object]]:" in seg
        # لا websocket/send_lock في توقيع التقييم، ولا بثّ في جسده.
        head = seg[: seg.index('"""')]
        assert "websocket" not in head and "send_lock" not in head
        body = seg
        assert "_locked_send_json" not in body
        assert "websocket.send_json" not in body
        # لا حفظ داخل التقييم (الحفظ يقع بعد المحتوى في المنسّق).
        assert "_persist_ui_component_cards" not in body

    def test_eval_returns_both_card_payloads(self) -> None:
        seg = CHAT_SRC[CHAT_SRC.index("async def _evaluate_bkt_cards(") :]
        seg = seg[: seg.index("\n\n\n")] if "\n\n\n" in seg else seg
        assert '"component": "bkt_hint_display"' in seg
        assert '"component": "learning_path_card"' in seg
        # append إلى قائمة تُرجَع (لا emit)
        assert "cards.append(" in seg
        assert "return cards" in seg


# ── 2. الإصدار يقع بعد الإطار النهائي (لا تشظٍّ) ────────────────────────────────
class TestEmitAfterTerminal:
    def test_task_created_for_eval_only(self) -> None:
        # المهمة المتزامنة تستدعي التقييم فقط (لا الإصدار) — لا TTFT impact.
        assert "asyncio.create_task(\n                _evaluate_bkt_cards(" in CHAT_SRC
        assert "asyncio.create_task(\n                _evaluate_and_emit_bkt(" not in CHAT_SRC

    def test_cards_emitted_after_terminal_frames(self) -> None:
        term_idx = CHAT_SRC.index("await _emit_terminal_frames(")
        await_idx = CHAT_SRC.index("await _bkt_task")
        assert await_idx > term_idx, (
            "D-118: BKT cards must be awaited/emitted AFTER the content terminal frame."
        )

    def test_post_terminal_block_persists_then_emits_via_lock(self) -> None:
        post = CHAT_SRC[CHAT_SRC.index("await _bkt_task") :]
        # الحفظ ثم الإصدار عبر القفل (D-096)، مع فحص حالة الـ WS.
        assert "_persist_ui_component_cards(" in post
        assert "_locked_send_json(" in post
        assert '"type": "ui_component", "payload": _card' in post
        assert "WebSocketState.CONNECTED" in post

    def test_emit_isolated_failopen(self) -> None:
        # الكتلة معزولة — لا تكسر إنهاء الدور (D-074: BKT لا يكسر الدردشة).
        post = CHAT_SRC[CHAT_SRC.index("await _bkt_task") :]
        block = post[: post.index("# Close path-aware span")]
        assert "except Exception" in block or "contextlib.suppress" in block
        assert "(WebSocketDisconnect, RuntimeError)" in block


# ── 3. منع عودة الإصدار المتزامن mid-stream ────────────────────────────────────
class TestNoMidStreamEmit:
    def test_no_concurrent_card_emit_during_stream(self) -> None:
        # دالة التقييم المتزامنة لا تُصدِر إطار ui_component على الـ WS (eval only).
        # (الـ docstring قد يذكر «ui_component» للتوثيق — نفحص إطار الإصدار الفعلي.)
        eval_seg = CHAT_SRC[CHAT_SRC.index("async def _evaluate_bkt_cards(") :]
        eval_seg = eval_seg[: eval_seg.index("\n\n\n")] if "\n\n\n" in eval_seg else eval_seg
        assert '"type": "ui_component"' not in eval_seg, (
            "D-118: eval function must not emit a ui_component wire frame — eval only."
        )
