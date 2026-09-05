import re

CODE_BLOCK_RE = re.compile(r"```[\s\S]{10,}?```")

text = """
```bash
uv run pytest tests/services/test_iss101_ws_proxy.py
```
"""
print(bool(CODE_BLOCK_RE.search(text)))
