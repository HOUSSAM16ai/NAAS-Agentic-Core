"""مانيفست المركّب (D-164/D-173/D-252/D-255/D-256) — يركّب القشرة + حزمة الشرائح
في مصدرٍ واحد (D-258 — تفكيك hotspot `tests/conftest.py` — CodeScene X-Ray).

**لماذا هذه البوابة موجودة:** كان `tests/conftest.py` hotspotًا بتردد تغييرٍ عالٍ
(client=22 · user_factory=13 · db_lifecycle=12/63/Bumpy Road · test_app=12 ·
db_session=10 · admin_user=8 · register_and_login_test_user=54 سطرًا) وقوّة
ارتباطٍ داخلية مرتفعة. فُكِّك إلى قشرةٍ تفويضٍ نصّية + حزمة شرائح `conftest_support/`
— صفر تغيير سلوكي، وكل حارسٍ نصي يتغذى من `read_conftest_source()` — لا تراجع
صامت للحرس النصي.
"""

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

_SUPPORT_DIR = pathlib.Path(__file__).parent
_SHELL_SOURCE = _SUPPORT_DIR.parent / "conftest.py"


def read_conftest_source() -> str:
    """يقرأ القشرة + كل شرائح الحزمة في وثيقة مصدرٍ واحدة (الحارس النصي يتغذى منها)."""
    parts: list[str] = [
        f"# === SHELL: {_SHELL_SOURCE.name} ===\n" + _SHELL_SOURCE.read_text(encoding="utf-8"),
    ]
    for shard in sorted(
        p for p in _SUPPORT_DIR.glob("*.py") if p.name not in {"__init__.py", "_sources.py"}
    ):
        parts.append(f"\n# === SHARD: {shard.name} ===\n" + shard.read_text(encoding="utf-8"))
    return "\n".join(parts)
