import asyncio
from scripts.e2e.universal_answerability_live import _login, _run_turn, Probe
import httpx
async def main():
    token = await _login("http://127.0.0.1:8000", "houssamannaba963@gmail.com", "1111")
    ws_url = "ws://127.0.0.1:8000/api/chat/ws"

    # testing the one that failed earlier
    probe = Probe("ما معنى الرمز Ω في الفيزياء", "physics")
    print(f"Testing: {probe.question}")
    turn = await _run_turn(ws_url, token, probe)
    print(f"Content: {turn.content}")
    print(f"Problems: {turn.problems}\n")
asyncio.run(main())
