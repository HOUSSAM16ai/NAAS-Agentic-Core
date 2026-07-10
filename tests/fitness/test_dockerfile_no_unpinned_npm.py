"""
Regression test — the container build MUST NEVER run an unpinned
`npm install -g npm@latest` (ISS-127 / D-161).

USER REPORT (2026-07-09, with full Codespaces creation.log):
> «انظر هذه الكارثة ظهرت عند فتح github codespaces — ظهرت في فرع main
>  و هذا الفرع الجديد في إثنين»
> (Codespace creation failed with error 1302 on BOTH main and the feature
>  branch simultaneously.)

ROOT CAUSE (evidence — creation.log lines 1979-2005):
    npm error code EBADENGINE
    npm error notsup Required: {"node":"^22.22.2 || ^24.15.0 || >=26.0.0"}
    npm error notsup Actual:   {"npm":"10.8.2","node":"v20.20.2"}
    "npm install -g npm@latest" did not complete successfully: exit code: 1

`npm install -g npm@latest` in the Dockerfile was a TIME BOMB: the moment
npm published v12.0.0 (which dropped Node 20 support), every Codespace
build on every branch failed with error 1302
(UnifiedContainersErrorFatalCreatingContainer) — with zero repo commits
involved. NodeSource's nodejs package already bundles a compatible npm
(10.8.2, full lockfileVersion-3 support), so the upgrade was pure risk
with no benefit.

INVARIANT (enforced by this test):
No build-critical file (Dockerfile*, .devcontainer scripts) may install
an unpinned `npm@latest`. Any future npm upgrade must be pinned to a
major version verified compatible with the image's Node runtime.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: الملفات الحرجة للبناء: أي `npm@latest` فيها يقتل إنشاء الحاوية على كل الفروع.
_BUILD_CRITICAL_GLOBS = ("Dockerfile*", ".devcontainer/**/*")

#: أنماط محظورة: ترقية npm عالمية غير مُثبَّتة الإصدار.
_FORBIDDEN = re.compile(r"npm\s+(?:install|i)\s+(?:-g|--global)\s+npm@latest")


def _build_critical_files() -> list[Path]:
    files: list[Path] = []
    for pattern in _BUILD_CRITICAL_GLOBS:
        for path in REPO_ROOT.glob(pattern):
            if path.is_file() and path.suffix not in (".md", ".png", ".jpg"):
                files.append(path)
    assert files, "no build-critical files found — glob patterns broken?"
    return files


def test_no_unpinned_global_npm_upgrade_anywhere_build_critical():
    """ISS-127: `npm install -g npm@latest` محظور في كل ملفات البناء."""
    offenders: list[str] = []
    for path in _build_critical_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            # التعليقات لا تُنفَّذ فلا تكسر البناء (توثيق D-161 نفسه يذكر النمط المحظور).
            if stripped.startswith("#"):
                continue
            if _FORBIDDEN.search(line):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: {stripped}")
    assert not offenders, (
        "unpinned `npm install -g npm@latest` found — this is the exact time bomb "
        "that broke every Codespace build with error 1302 (ISS-127/D-161). "
        "Pin the npm major or drop the upgrade:\n" + "\n".join(offenders)
    )


def test_dockerfile_node_step_has_no_npm_latest():
    """الخطوة التي فشلت حرفياً في creation.log لم تعد تحوي الترقية القاتلة."""
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "deb.nodesource.com/setup_20.x" in dockerfile, (
        "Node install step disappeared from Dockerfile — update this test "
        "alongside any intentional Node-version change (D-161)."
    )
    executable_lines = [
        ln for ln in dockerfile.splitlines() if ln.strip() and not ln.strip().startswith("#")
    ]
    assert all("npm@latest" not in ln for ln in executable_lines), (
        "npm@latest reappeared in an executable Dockerfile line — forbidden by D-161 (ISS-127)"
    )
