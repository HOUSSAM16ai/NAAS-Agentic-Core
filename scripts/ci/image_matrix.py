"""قارئ مصفوفة بناء الصور لوظيفة CI — D-205.

وجودُه لسببين:

1. **الحقن غير مُمثَّل.** البديل كان تمرير `smoke_env` عبر مصفوفة GitHub ثم بناء
   `-e K=V` في الصدفة. القيم لنا اليوم — والقاعدة أن يبقى الأمان بنيوياً لا
   بحسن النيّة (D-187). هنا تُكتَب في ملفّ `--env-file` ولا تمرّ بصدفة أبداً.
2. **مسار الـDockerfile يُحسَب مرّةً واحدة.** المصفوفة تُخزّنه نسبةً إلى سياق
   البناء، بينما `docker/build-push-action` يريده نسبةً إلى جذر مساحة العمل —
   و`notation-service` يبني من الجذر بينما البقيّة من مجلّد الخدمة. حساب هذا
   داخل YAML يعني حسابه في موضعين.

الاستعمال:
    python scripts/ci/image_matrix.py --names          # JSON list للمصفوفة
    python scripts/ci/image_matrix.py --resolve NAME   # سطور KEY=VALUE للـGITHUB_OUTPUT
    python scripts/ci/image_matrix.py --env-file NAME PATH
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX_FILE = REPO_ROOT / "config/image_build_matrix.json"


def load_images() -> list[dict[str, object]]:
    return list(json.loads(MATRIX_FILE.read_text(encoding="utf-8"))["images"])


def find(name: str) -> dict[str, object]:
    for entry in load_images():
        if entry["name"] == name:
            return entry
    raise SystemExit(f"unknown image: {name}")


def workspace_dockerfile(entry: dict[str, object]) -> str:
    """مسار الـDockerfile نسبةً إلى جذر مساحة العمل، أياً كان سياق البناء."""
    context = str(entry["context"]).rstrip("/") or "."
    dockerfile = str(entry["dockerfile"])
    if context in {".", "./"}:
        return dockerfile
    return f"{context}/{dockerfile}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--names", action="store_true")
    parser.add_argument("--resolve", metavar="NAME")
    parser.add_argument("--env-file", nargs=2, metavar=("NAME", "PATH"))
    args = parser.parse_args()

    if args.names:
        print(json.dumps([str(e["name"]) for e in load_images()]))
        return 0

    if args.resolve:
        entry = find(args.resolve)
        print(f"context={entry['context']}")
        print(f"dockerfile={workspace_dockerfile(entry)}")
        print(f"smoke={entry.get('smoke') or ''}")
        return 0

    if args.env_file:
        name, path = args.env_file
        env = find(name).get("smoke_env") or {}
        assert isinstance(env, dict)
        # `--env-file` يقرأ KEY=VALUE سطراً سطراً بلا تفسير صدفة.
        Path(path).write_text("".join(f"{k}={v}\n" for k, v in env.items()), encoding="utf-8")
        return 0

    parser.error("one of --names / --resolve / --env-file is required")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
