import re

HUMAN_RE = re.compile(r"(?im)^\s*HUMAN:\s*$")
AGENT_RE = re.compile(r"(?im)^\s*AGENT:\s*$")

def _human_note(body: str) -> str | None:
    start = HUMAN_RE.search(body)
    if not start:
        return None
    rest = body[start.end() :]
    stop = AGENT_RE.search(rest)
    return (rest[: stop.start()] if stop else rest).strip()

body = """
HUMAN:
I have verified this fix locally.
"""
print(len(_human_note(body)))
print(_human_note(body))
