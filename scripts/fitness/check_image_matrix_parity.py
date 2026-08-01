"""يفرض أن كلّ صورة يستطيع المستودع بناءها مُعلَنة في مصفوفة البناء — D-205.

بوّابةُ بناءٍ تُغطّي ما تعرفه فقط. `docker-compose.yml` كان يصف ١٢ سياق بناء ولم
يُبنَ منها واحد في CI قطّ؛ ولو أُضيفت خدمة غداً بلا إدخال هنا لعادت التغطية تتآكل
بصمت — وهو نفس صنف العطب الذي وُلِدت له `check_topic_contract_parity`.

الاتّجاهان مفروضان:
  compose ⇒ مصفوفة   (سياق بناء بلا إدخال = فشل)
  ملفّات Dockerfile ⇒ مصفوفة   (خدمة لها صورة ولا تُبنى = فشل)
  مصفوفة ⇒ قرص      (إدخال يشير إلى ملفّ غير موجود = فشل)

ولا يُقبَل إدخالٌ بلا `smoke` إلّا بسببٍ منطوق (`smoke_skip_reason`): «البناء نجح»
ليس دليلاً على أنّ التطبيق يستورد (§0 — الحقيقة بالبرهان لا بالنيّة).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX_FILE = REPO_ROOT / "config/image_build_matrix.json"
DEFAULT_COMPOSE = REPO_ROOT / "docker-compose.yml"
MICROSERVICES_ROOT = REPO_ROOT / "microservices"

#: `build:` كتلة في compose — نلتقط السياق وملفّ الـDockerfile الاختياري بعده.
_BUILD_BLOCK = re.compile(
    r"^\s*build:\s*$\n\s*context:\s*(?P<context>\S+)\s*$"
    r"(?:\n\s*dockerfile:\s*(?P<dockerfile>\S+)\s*$)?",
    re.MULTILINE,
)


def _display(path: Path) -> str:
    """مسارٌ للقراءة. رسالةُ خطأٍ تنهار بـ`ValueError` تُخفي العطب الذي جاءت تُبلّغ عنه."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _normalise(context: str, dockerfile: str) -> tuple[str, str]:
    """يُوحِّد شكل المسار حتى تتطابق `.` و`./` و`./x/` على مفتاح واحد."""
    ctx = context.rstrip("/") or "."
    if ctx.startswith("./") and ctx != "./":
        ctx = ctx[2:]
    return (ctx or ".", dockerfile)


def _compose_build_targets() -> set[tuple[str, str]]:
    text = DEFAULT_COMPOSE.read_text(encoding="utf-8")
    return {
        _normalise(m.group("context"), m.group("dockerfile") or "Dockerfile")
        for m in _BUILD_BLOCK.finditer(text)
    }


def _dockerfiles_on_disk() -> list[Path]:
    """كلّ `microservices/*/Dockerfile` — بمساره المطلق.

    المقارنة بالمسار لا بالزوج (سياق، ملفّ): `notation-service` يبني من جذر
    المستودع (`context: .`) بينما البقيّة تبني من مجلّد الخدمة، فمقارنةُ الأزواج
    كانت تُبلّغ عنه «غير مبنيّ» وهو مبنيّ — إنذارٌ كاذب يُدرَّب الناس على تجاهله.
    """
    return sorted(MICROSERVICES_ROOT.glob("*/Dockerfile"))


def _matrix_entries() -> list[dict[str, object]]:
    return list(json.loads(MATRIX_FILE.read_text(encoding="utf-8"))["images"])


def main() -> int:
    entries = _matrix_entries()
    errors: list[str] = []

    declared: set[tuple[str, str]] = set()
    declared_dockerfiles: set[Path] = set()
    seen_names: set[str] = set()

    for entry in entries:
        name = str(entry.get("name", "<unnamed>"))
        if name in seen_names:
            errors.append(f"{name}: duplicate entry")
        seen_names.add(name)

        context = str(entry["context"])
        dockerfile = str(entry["dockerfile"])
        declared.add(_normalise(context, dockerfile))

        # المسار الفعلي للـDockerfile: نسبيّ للسياق إلّا إن كان سياقه الجذر.
        base = REPO_ROOT / context
        candidate = REPO_ROOT / dockerfile if context in {".", "./"} else base / dockerfile
        declared_dockerfiles.add(candidate.resolve())
        if not candidate.is_file():
            errors.append(f"{name}: dockerfile not found at {_display(candidate)}")
        if not base.is_dir():
            errors.append(f"{name}: build context {context} is not a directory")

        if not entry.get("smoke") and not entry.get("smoke_skip_reason"):
            errors.append(
                f"{name}: no smoke import and no smoke_skip_reason — building is not importing"
            )

    for target in sorted(_compose_build_targets() - declared):
        errors.append(f"docker-compose.yml builds {target[0]} ({target[1]}) with no matrix entry")

    for path in _dockerfiles_on_disk():
        if path.resolve() not in declared_dockerfiles:
            errors.append(f"{_display(path)} exists but is never built (no matrix entry)")

    if errors:
        print("❌ Image build matrix parity failed:")
        for item in errors:
            print(f" - {item}")
        return 1

    print(f"✅ Image build matrix parity passed ({len(entries)} images declared and buildable).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
