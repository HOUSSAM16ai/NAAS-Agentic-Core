import asyncio
from scripts.e2e.universal_answerability_live import _login, _run_turn, Probe
import httpx
async def main():
    token = await _login("http://127.0.0.1:8000", "houssamannaba963@gmail.com", "1111")
    ws_url = "ws://127.0.0.1:8000/api/chat/ws"

    probe = Probe("السلام عليكم", "—", note="التحية: مسارٌ حتمي قبل أيّ LLM (D-067)")
    print(f"Testing: {probe.question}")
    turn = await _run_turn(ws_url, token, probe)
    print(f"Content: {turn.content}")
    print(f"Problems: {turn.problems}\n")

    probe2 = Probe("اعطني تمرين الاحتمالات 2024", "mathematics")
    print(f"Testing: {probe2.question}")
    turn2 = await _run_turn(ws_url, token, probe2)
    print(f"Content: {turn2.content}")
    print(f"Problems: {turn2.problems}")
asyncio.run(main())
