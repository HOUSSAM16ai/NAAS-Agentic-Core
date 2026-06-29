import asyncio
from microservices.orchestrator_service.src.services.overmind.utils.intent_detector import IntentDetector, ChatIntent

async def test():
    detector = IntentDetector()
    q = "ما هي نقاط ضعفي في تمرين الاحتمالات؟"
    result = await detector.detect(q)
    print(f"Q: {q}")
    print(f"A: {result.intent.value}")

    q2 = "أعطني تمرين بكالوريا حول الدوال"
    result2 = await detector.detect(q2)
    print(f"Q: {q2}")
    print(f"A: {result2.intent.value}")

asyncio.run(test())
