#!/usr/bin/env python3
"""
يستبدل نموذج LLM معطّلاً بنموذج جديد في جميع ملفات المشروع.
يتجاهل التعليقات ويُبلِّغ عن كل استبدال.

الاستخدام:
    python3 replace_model.py --old "inclusionai/ring-2.6-1t:free" \
                              --new "nvidia/nemotron-3-nano-30b-a3b:free"
    python3 replace_model.py --dry-run  # عرض فقط بدون تعديل
"""

import argparse
from pathlib import Path

# الملفات التي يجب فحصها (بالترتيب)
TARGET_FILES = [
    "app/core/ai_config.py",
    "app/services/chat/local_graph.py",
    "app/services/chat/agents/orchestrator.py",
    "app/services/chat/agents/socratic_tutor.py",
    "microservices/reasoning_agent/src/ai_client.py",
    "microservices/reasoning_agent/src/core/config.py",
    "microservices/reasoning_agent/src/services/reasoning_service.py",
    "microservices/reasoning_agent/src/services/strategies/mcts.py",
    "microservices/research_agent/src/search_engine/super_search.py",
    "microservices/research_agent/src/search_engine/query_refiner.py",
    "microservices/planning_agent/settings.py",
    "microservices/orchestrator_service/src/core/ai_config.py",
    "microservices/orchestrator_service/src/services/llm/client.py",
    "microservices/orchestrator_service/src/services/overmind/agents/orchestrator.py",
    "microservices/orchestrator_service/src/services/overmind/graph/main.py",
    "microservices/conversation_service/src/conversation_graph.py",
    "microservices/auditor_service/src/ai.py",
]


def is_comment_line(line: str) -> bool:
    """تحقق من أن السطر تعليق Python."""
    return line.lstrip().startswith("#")


def replace_in_file(path: Path, old: str, new: str, dry_run: bool) -> int:
    """يستبدل النموذج في ملف واحد. يُعيد عدد الاستبدالات."""
    if not path.exists():
        return 0

    content = path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)
    new_lines = []
    count = 0

    for line in lines:
        if old in line and not is_comment_line(line):
            new_line = line.replace(old, new)
            new_lines.append(new_line)
            count += 1
            print(f"  [{path}] line {lines.index(line) + 1}:")
            print(f"    - {line.rstrip()}")
            print(f"    + {new_line.rstrip()}")
        else:
            new_lines.append(line)

    if count > 0 and not dry_run:
        path.write_text("".join(new_lines), encoding="utf-8")

    return count


def scan_for_remaining(old: str, root: Path) -> list[tuple[Path, int, str]]:
    """يبحث عن أي استخدام متبقٍّ للنموذج القديم كقيمة نشطة."""
    remaining = []
    for py_file in root.rglob("*.py"):
        if "__pycache__" in str(py_file) or "test_" in py_file.name:
            continue
        try:
            for i, line in enumerate(py_file.read_text(encoding="utf-8").splitlines(), 1):
                if old in line and not is_comment_line(line):
                    remaining.append((py_file, i, line.strip()))
        except Exception:
            pass
    return remaining


def main() -> None:
    parser = argparse.ArgumentParser(description="Replace broken LLM model across all services")
    parser.add_argument("--old", default="inclusionai/ring-2.6-1t:free")
    parser.add_argument("--new", default="nvidia/nemotron-3-nano-30b-a3b:free")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without applying")
    parser.add_argument("--root", default=".", help="Project root directory")
    args = parser.parse_args()

    root = Path(args.root)
    mode = "DRY RUN" if args.dry_run else "APPLYING"
    print(f"=== Model Replacement ({mode}) ===")
    print(f"OLD: {args.old}")
    print(f"NEW: {args.new}")
    print()

    total = 0
    for rel_path in TARGET_FILES:
        path = root / rel_path
        count = replace_in_file(path, args.old, args.new, args.dry_run)
        if count:
            total += count
            print(f"  → {count} replacement(s) in {rel_path}")

    print(f"\nTotal replacements: {total}")

    # فحص نهائي
    print("\n=== Final Scan for Remaining Active Uses ===")
    remaining = scan_for_remaining(args.old, root)
    if remaining:
        print(f"⚠️  {len(remaining)} active use(s) still found:")
        for path, line_no, line in remaining:
            print(f"  {path}:{line_no}: {line}")
    else:
        print("✅ No active uses of old model found")

    if not args.dry_run and total > 0:
        print("\n✅ Done. Restart affected services to apply changes.")
        print("   See SKILL.md §4 for restart commands.")


if __name__ == "__main__":
    main()
