import asyncio
from scripts.e2e.universal_answerability_live import main
import sys

async def run():
    sys.exit(await main())

if __name__ == "__main__":
    asyncio.run(run())
