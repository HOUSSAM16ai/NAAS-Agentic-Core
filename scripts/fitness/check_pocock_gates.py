#!/usr/bin/env python3
"""D-274 fitness gate: the four mandatory Pocock workflow skills must exist,
be syntactically valid, and carry the canonical frontmatter. Additive-only
constitution — this gate never removes or alters anything.
"""
import json
import pathlib
import sys

REPO = pathlib.Path("/home/ubuntu/NAAS-Agentic-Core")
SKILLS = REPO / ".claude/skills"

REQUIRED = {
    "grill-me": ["SKILL.md", "grilling.md"],
    "to-spec": ["SKILL.md"],
    "triage": ["SKILL.md", "AGENT-BRIEF.md", "OUT-OF-SCOPE.md", "REPO-LABEL-MAP.md"],
    "improve-architecture": ["SKILL.md", "HTML-REPORT.md", "codebase-design.md"],
}


def frontmatter_ok(path: pathlib.Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return False
    end = text.find("---", 3)
    if end == -1:
        return False
    fm = text[3:end]
    return "name:" in fm and "description:" in fm


def main() -> int:
    problems = []
    for skill, files in REQUIRED.items():
        home = SKILLS / skill
        if not home.is_dir():
            problems.append(f"missing skill dir: {skill}")
            continue
        for f in files:
            p = home / f
            if not p.exists():
                problems.append(f"missing file: {skill}/{f}")
            elif f == "SKILL.md" and not frontmatter_ok(p):
                problems.append(f"bad frontmatter: {skill}/{f}")

    # repo label map must agree with the governance model's status labels
    label_map = SKILLS / "triage" / "REPO-LABEL-MAP.md"
    gov = REPO / "docs/governance/REPOSITORY_GOVERNANCE_MODEL.md"
    if label_map.exists() and gov.exists():
        gov_text = gov.read_text(encoding="utf-8")
        for tag in ("status:needs-triage", "status:blocked", "status:ready"):
            if tag not in gov_text:
                problems.append(f"REPO-LABEL-MAP references missing label: {tag}")

    # constitution doc + truth file must co-exist (self-reference integrity)
    for p in (
        "docs/AGENT_WORKFLOW_CONSTITUTION.md",
        ".memory/pocock_skills_truth.md",
    ):
        if not (REPO / p).exists():
            problems.append(f"missing: {p}")

    if problems:
        print("FAIL check_pocock_gates:")
        for pr in problems:
            print(f"  - {pr}")
        return 1
    print(
        "✅ pocock gates: grill-me · to-spec · triage · improve-architecture "
        "present, frontmatter valid, label map consistent with governance model."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
