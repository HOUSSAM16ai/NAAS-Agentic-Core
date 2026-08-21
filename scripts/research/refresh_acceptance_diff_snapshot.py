"""Refresh the non-circular git change snapshot in the current acceptance packet."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKET = ROOT / "docs/changes/CURRENT_CODE_ACCEPTANCE_PACKET.json"
PACKET_REL = "docs/changes/CURRENT_CODE_ACCEPTANCE_PACKET.json"


def run(args: list[str]) -> str:
    completed = subprocess.run(args, cwd=ROOT, check=True, capture_output=True, text=True)
    return completed.stdout


def normalize(path: str) -> str:
    return path.strip().removeprefix("./")


def current_paths() -> list[str]:
    base = os.environ.get("CODE_ACCEPTANCE_BASE_SHA", "").strip()
    names: set[str] = set()
    if base:
        output = run(["git", "diff", "--name-only", "--diff-filter=ACMRTUXB", f"{base}...HEAD"])
        names.update(normalize(line) for line in output.splitlines() if line.strip())
    else:
        for args in (
            ["git", "diff", "--name-only", "--diff-filter=ACMRTUXB"],
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMRTUXB"],
        ):
            output = run(args)
            names.update(normalize(line) for line in output.splitlines() if line.strip())
        porcelain = run(["git", "status", "--porcelain=v1", "--untracked-files=all"])
        for line in porcelain.splitlines():
            if line.startswith("?? "):
                names.add(normalize(line[3:]))
            elif len(line) >= 4 and line[0] in "MADRCU" or len(line) >= 4 and line[1] in "MADRCU":
                names.add(normalize(line[3:]))
    return sorted(name for name in names if name)


def content_fingerprint(paths: list[str]) -> str:
    digest = hashlib.sha256()
    for relative in paths:
        if relative == PACKET_REL:
            continue
        path = ROOT / relative
        if path.is_file():
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        elif path.is_dir():
            for child in sorted(child for child in path.rglob("*") if child.is_file()):
                child_rel = str(child.relative_to(ROOT))
                digest.update(child_rel.encode("utf-8"))
                digest.update(b"\0")
                digest.update(child.read_bytes())
                digest.update(b"\0")
    return digest.hexdigest()


def main() -> None:
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    paths = current_paths()
    snapshot_paths = [path for path in paths if path != PACKET_REL]
    packet["git_change_snapshot"] = {
        "base_ref": os.environ.get("CODE_ACCEPTANCE_BASE_SHA", "WORKTREE"),
        "changed_paths_excluding_packet": snapshot_paths,
        "content_sha256_excluding_packet": content_fingerprint(snapshot_paths),
        "refreshed_on": "2026-08-21",
        "refresh_command": "python3 scripts/research/refresh_acceptance_diff_snapshot.py",
    }
    PACKET.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"changed_paths_excluding_packet": len(snapshot_paths), "content_sha256_excluding_packet": packet["git_change_snapshot"]["content_sha256_excluding_packet"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
