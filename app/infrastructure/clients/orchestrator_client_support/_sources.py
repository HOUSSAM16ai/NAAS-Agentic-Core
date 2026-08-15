"""مانيفست المركّب (D-164/D-173/D-252) — يركّب القشرة + حزمة الشرائح في مصدرٍ واحد.

كل حارسٍ نصي يتغذى من `read_orchestrator_client_source()` — لا تراجع صامت
للحرس النصي بعد D-256 (تفكيك hotspot `orchestrator_client.py` — CodeScene job 72).
"""

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

_SUPPORT_DIR = pathlib.Path(__file__).parent
_SHELL_SOURCE = _SUPPORT_DIR.parent / "orchestrator_client.py"


def read_orchestrator_client_source() -> str:
    """يقرأ القشرة + كل شرائح الحزمة في وثيقة مصدرٍ واحدة (الحارس النصي يتغذى منها)."""
    parts: list[str] = [
        f"# === SHELL: {_SHELL_SOURCE.name} ===\n" + _SHELL_SOURCE.read_text(encoding="utf-8"),
    ]
    for shard in sorted(
        p for p in _SUPPORT_DIR.glob("*.py") if p.name not in {"__init__.py", "_sources.py"}
    ):
        parts.append(f"\n# === SHARD: {shard.name} ===\n" + shard.read_text(encoding="utf-8"))
    return "\n".join(parts)
