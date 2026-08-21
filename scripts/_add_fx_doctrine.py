#!/usr/bin/env python3
"""Append doctrine-related D-273 entries: registry rows + README index (additive only)."""
import json
import sys

REPO = "/home/ubuntu/NAAS-Agentic-Core"


def registry_row():
    """Add the doctrine companion row to CONSTITUTION_REGISTRY.json constitutions."""
    path = f"{REPO}/docs/governance/CONSTITUTION_REGISTRY.json"
    with open(path, encoding="utf-8") as f:
        registry = json.load(f)
    const = registry["constitutions"]
    if any(r.get("id") == "D-273" for r in const):
        print("Registry: D-273 row already present")
    else:
        const.append({
            "id": "D-273",
            "title": "دستور التقنية العميقة — عتبة الدخول والعملة الصعبة وإضافة لا حذف",
            "doc": "docs/DEEP_TECH_CONSTITUTION.md",
            "companion": "docs/FOREIGN_CURRENCY_DOCTRINE.md",
            "enforcer": "scripts/fitness/check_deep_tech_constitution.py",
            "status": "active",
            "added": "2026-08-21",
            "note": "Additive-only strategic constitution mandated by the owner; companion FX doctrine documents Algeria's legal hard-currency channels (system 21-01, instruction 06-2021, finance law 2026).",
        })
        with open(path, "w", encoding="utf-8") as f:
            json.dump(registry, f, ensure_ascii=False, indent=2)
        print("Registry: D-273 row added")


def readme_index():
    """Add the truth file to the truth section of .memory/README.md (additive only)."""
    path = f"{REPO}/.memory/README.md"
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    marker = "| `fx_doctrine_truth`"
    if any(marker in ln for ln in lines):
        print("README index: already present")
        return
    # find the truth table section: lines starting with '| deep_tech_constitution_truth'
    idx = None
    for i, ln in enumerate(lines):
        if ln.startswith("| `deep_tech_constitution_truth`"):
            idx = i + 1
            break
    if idx is None:
        print("README index: truth table not found — manual check needed", file=sys.stderr)
        sys.exit(1)
    new_row = (
        "| `fx_doctrine_truth.md` | **حالة** عقيدة العملة الصعبة (D-273) — ٤ مسارات رسمية (تصدير رقمي + مزايا جبائية + قناة دفع بديلة + مضاعفة البنية التحتية) · ٤ محرمات (K1–K4) · ١٠ مراجع §99. القانون في `docs/FOREIGN_CURRENCY_DOCTRINE.md` |\n"
    )
    lines.insert(idx, new_row)
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print("README index: fx_doctrine_truth row added")


if __name__ == "__main__":
    registry_row()
    readme_index()
