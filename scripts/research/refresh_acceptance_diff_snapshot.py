"""Refresh the non-circular git change snapshot in the current acceptance packet.

⚠️ **Mode matters, and the default cannot satisfy a PR check.** With
``CODE_ACCEPTANCE_BASE_SHA`` set, the snapshot is taken from ``git diff base...HEAD`` —
which is exactly what ``ci.yml`` gives ``check_code_acceptance.py`` on a pull request.
Without it, the snapshot is taken from the **working tree**, so once the work is
committed the recorded set no longer matches what CI computes and the gate reports a
stale snapshot.

Running this tool the documented way and still getting a red PR is the trap D-270 L7
names: a local enforcer that disagrees with CI is worse than none, because it turns
following the docs into a failure. The default is left unchanged (other flows depend on
it) but it can no longer be silent — see ``_warn_if_worktree_mode``.

    CODE_ACCEPTANCE_BASE_SHA=origin/main python3 scripts/research/refresh_acceptance_diff_snapshot.py
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKET = ROOT / "docs/changes/CURRENT_CODE_ACCEPTANCE_PACKET.json"
PACKET_REL = "docs/changes/CURRENT_CODE_ACCEPTANCE_PACKET.json"


def run(args: list[str]) -> str:
    completed = subprocess.run(args, cwd=ROOT, check=True, capture_output=True, text=True)
    return completed.stdout


def normalize(path: str) -> str:
    return path.strip().removeprefix("./")


def _paths_from_diff(args: list[str]) -> set[str]:
    output = run(args)
    return {normalize(line) for line in output.splitlines() if line.strip()}


def _paths_from_porcelain(output: str) -> set[str]:
    names: set[str] = set()
    for line in output.splitlines():
        if line.startswith("?? ") or (
            len(line) >= 4 and (line[0] in "MADRCU" or line[1] in "MADRCU")
        ):
            names.add(normalize(line[3:]))
    return names


def _base_paths(base: str) -> set[str]:
    return _paths_from_diff(
        ["git", "diff", "--name-only", "--diff-filter=ACMRTUXB", f"{base}...HEAD"]
    )


def _working_tree_paths() -> set[str]:
    names = _paths_from_diff(["git", "diff", "--name-only", "--diff-filter=ACMRTUXB"])
    names.update(
        _paths_from_diff(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMRTUXB"])
    )
    porcelain = run(["git", "status", "--porcelain=v1", "--untracked-files=all"])
    names.update(_paths_from_porcelain(porcelain))
    return names


def current_paths() -> list[str]:
    base = os.environ.get("CODE_ACCEPTANCE_BASE_SHA", "").strip()
    names = _base_paths(base) if base else _working_tree_paths()
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


def _warn_if_worktree_mode(base_ref: str) -> None:
    """Say out loud that a WORKTREE snapshot will not satisfy the PR-mode check.

    Silence here is what makes the trap: the tool succeeds, prints a fingerprint, and
    the gate then fails in CI with a number the author never saw locally.
    """
    if base_ref != "WORKTREE":
        return
    print(
        "⚠️  WORKTREE mode: this snapshot describes the working tree, not "
        "`base...HEAD`.\n"
        "    CI runs check_code_acceptance.py with CODE_ACCEPTANCE_BASE_SHA set, so "
        "this snapshot\n"
        "    will be reported stale on a pull request once the work is committed.\n"
        "    For a PR, re-run as:\n"
        "      CODE_ACCEPTANCE_BASE_SHA=origin/main python3 "
        "scripts/research/refresh_acceptance_diff_snapshot.py",
        file=sys.stderr,
    )


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
    _warn_if_worktree_mode(packet["git_change_snapshot"]["base_ref"])
    print(
        json.dumps(
            {
                "changed_paths_excluding_packet": len(snapshot_paths),
                "content_sha256_excluding_packet": packet["git_change_snapshot"][
                    "content_sha256_excluding_packet"
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
