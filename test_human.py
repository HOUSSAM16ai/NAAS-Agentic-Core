import re

body = """
HUMAN: I have verified that all behavior originally tested in the deprecated `static_handler.py` (like path traversal prevention, API route 404s, and root index serving) has been functionally replaced and continues to pass in the new middleware tests locally.
AGENT: Acknowledged.
"""

HUMAN_RE = re.compile(r"^[*\s]*HUMAN:[*\s]*\n?", re.IGNORECASE | re.MULTILINE)
AGENT_RE = re.compile(r"^[*\s]*AGENT:[*\s]*\n?", re.IGNORECASE | re.MULTILINE)

start = HUMAN_RE.search(body)
if start:
    print("Found HUMAN:")
    print(start)
    rest = body[start.end() :]
    stop = AGENT_RE.search(rest)
    print("Found AGENT:")
    print(stop)
    print("Human note is:")
    print((rest[: stop.start()] if stop else rest).strip())
else:
    print("Not found")
