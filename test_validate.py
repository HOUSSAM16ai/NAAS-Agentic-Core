import re

HUMAN_RE = re.compile(r"(?im)^\s*HUMAN:\s*$")
AGENT_RE = re.compile(r"(?im)^\s*AGENT:\s*$")
HEADING_RE = re.compile(r"(?m)^##\s+(.+?)\s*$")

def _strip_comments(body: str) -> str:
    return re.sub(r"<!--[\s\S]*?-->", "", body)

def _human_note(body: str) -> str | None:
    text = _strip_comments(body)
    start = HUMAN_RE.search(text)
    if not start:
        return None
    rest = text[start.end() :]
    stop = AGENT_RE.search(rest)
    return (rest[: stop.start()] if stop else rest).strip()

def _sections(body: str) -> dict[str, str]:
    text = _strip_comments(body)
    found: dict[str, str] = {}
    matches = list(HEADING_RE.finditer(text))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        found[match.group(1).strip()] = text[match.end() : end].strip()
    return found

with open('pr_body.txt', 'r') as f:
    body = f.read()

print("Sections:")
print(_sections(body).keys())
print("\nHUMAN note:")
print(repr(_human_note(body)))
