#!/usr/bin/env python3
"""بوّابة تكافؤ المواضيع: السجلّ القانوني == العقد المُعلَن (D-201).

لماذا هذه البوّابة
------------------
`shared/messaging/topics.py` هو المصدر القانوني، و`docs/contracts/asyncapi/
learning-events.yaml` هو ما يقرؤه المستهلك الخارجي. نسختان من نفس الحقيقة تتباعدان
حتماً — وهذا **بالضبط** ما وثّقه D-192: عقدٌ مُعلَن بنصفه، ورقمٌ يحمل قيمتين في قسمين.

الاتجاهان محروسان:
* موضوعٌ في الكود بلا قناة في العقد ⇒ مستهلكٌ خارجي لا يعرف بوجوده.
* قناةٌ في العقد بلا موضوع في الكود ⇒ عقدٌ يعِد بما لا يُنشَر (أسوأ: يبدو صحيحاً).

وكذلك الاحتفاظ والأقسام: عقدٌ يذكر موضوعاً بمواصفاتٍ لا تُطابق الكود يوجّه من يُنشئ
المواضيع يدوياً إلى إعدادٍ خاطئ.

الاستعمال:
    python scripts/fitness/check_topic_contract_parity.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TOPICS_FILE = REPO_ROOT / "shared/messaging/topics.py"
CONTRACT_FILE = REPO_ROOT / "docs/contracts/asyncapi/learning-events.yaml"
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"


def _declared_topics() -> set[str]:
    """
    قيم `Topic` من المصدر القانوني — عبر AST لا استيراد.

    الاستيراد يجرّ تبعيات ويجعل البوّابة تفشل لأسبابٍ لا علاقة لها بالمواضيع.
    """
    tree = ast.parse(TOPICS_FILE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Topic":
            return {
                statement.value.value
                for statement in node.body
                if isinstance(statement, ast.Assign)
                and isinstance(statement.value, ast.Constant)
                and isinstance(statement.value.value, str)
            }
    return set()


def _contract_channels() -> set[str]:
    """عناوين القنوات من عقد AsyncAPI — قراءة نصّية كي تبقى البوّابة dep-free."""
    addresses: set[str] = set()
    for line in CONTRACT_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("address:"):
            addresses.add(stripped.split(":", 1)[1].strip())
    return addresses


def _compose_topics() -> set[str]:
    """المواضيع التي يُنشئها compose صراحةً — `auto.create` ممنوع (ADR-007)."""
    text = COMPOSE_FILE.read_text(encoding="utf-8")
    return {
        token.strip('"')
        for line in text.splitlines()
        for token in line.split()
        if token.strip('"').startswith("cogniforge.") and token.strip('"').endswith(".v1")
    }


def main() -> int:
    declared = _declared_topics()
    if not declared:
        print("❌ لم يُعثَر على أيّ موضوع في السجلّ القانوني — قراءة AST فشلت.")
        return 1

    problems: list[str] = []

    contract = _contract_channels()
    for missing in sorted(declared - contract):
        problems.append(f"موضوع {missing} في الكود بلا قناة في العقد — مستهلكٌ خارجي لا يعرفه.")
    for extra in sorted(contract - declared):
        problems.append(f"قناة {extra} في العقد بلا موضوع في الكود — عقدٌ يعِد بما لا يُنشَر.")

    compose = _compose_topics()
    for missing in sorted(declared - compose):
        problems.append(
            f"موضوع {missing} غير مُنشأ في docker-compose — و`auto.create` ممنوع (ADR-007)."
        )

    if problems:
        print("❌ تكافؤ المواضيع مخروق (D-201):")
        for problem in problems:
            print(f"   • {problem}")
        return 1

    print(f"✅ topic parity: {len(declared)} موضوعاً — السجلّ == العقد == compose.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
