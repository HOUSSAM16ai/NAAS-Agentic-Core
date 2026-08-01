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


#: مواصفات كل موضوع من السجلّ القانوني: الاسم ⇒ (أقسام، احتفاظ بالأيام).
def _declared_specs() -> dict[str, tuple[int, int]]:
    """
    يقرأ `partitions` و`retention_days` من `TOPIC_SPECS` عبر AST.

    الاسم وحده لا يكفي: عددُ أقسامٍ مختلف بين السجلّ وما يُنشَأ فعلاً يكسر **ترتيب**
    أحداث الطالب الواحد بلا أن يُخطئ أحدٌ صراحةً — وهو عطبٌ لا يظهر إلّا كسلوكٍ غريب
    بعد أسابيع.
    """
    tree = ast.parse(TOPICS_FILE.read_text(encoding="utf-8"))
    specs: dict[str, tuple[int, int]] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "TopicSpec"):
            continue
        fields: dict[str, object] = {}
        for keyword in node.keywords:
            if keyword.arg == "topic" and isinstance(keyword.value, ast.Attribute):
                fields["topic"] = keyword.value.attr
            elif isinstance(keyword.value, ast.Constant):
                fields[str(keyword.arg)] = keyword.value.value
        member = fields.get("topic")
        partitions = fields.get("partitions")
        retention = fields.get("retention_days")
        if isinstance(member, str) and isinstance(partitions, int) and isinstance(retention, int):
            specs[member] = (partitions, retention)
    return specs


def _topic_values_by_member() -> dict[str, str]:
    """`Topic.PRODUCT_EVENTS` ⇒ `cogniforge.product.events.v1` — لربط السجلّ بالمواصفة."""
    tree = ast.parse(TOPICS_FILE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Topic":
            return {
                target.id: statement.value.value
                for statement in node.body
                if isinstance(statement, ast.Assign)
                and isinstance(statement.value, ast.Constant)
                and isinstance(statement.value.value, str)
                for target in statement.targets
                if isinstance(target, ast.Name)
            }
    return {}


def _compose_specs() -> dict[str, tuple[int, int]]:
    """
    ما يُنشئه compose فعلاً: الاسم ⇒ (أقسام، احتفاظ بالمللي-ثانية).

    الأسطر بصيغة `"<topic> <partitions> <retention_ms>"` داخل حلقة الـbootstrap.
    """
    specs: dict[str, tuple[int, int]] = {}
    for raw in COMPOSE_FILE.read_text(encoding="utf-8").splitlines():
        # آخر سطر في الحلقة ينتهي بـ`"; do` لا بعلامة اقتباس — وتجاهله يعني أنّ آخر
        # موضوع يبدو «غير مُنشأ» زوراً. (كشفته البوّابة على نفسها عند أوّل تشغيل.)
        stripped = raw.strip().rstrip("\\").strip().removesuffix("; do").strip()
        if not (stripped.startswith('"cogniforge.') and stripped.endswith('"')):
            continue
        parts = stripped.strip('"').split()
        if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
            specs[parts[0]] = (int(parts[1]), int(parts[2]))
    return specs


def _compose_topics() -> set[str]:
    """المواضيع التي يُنشئها compose صراحةً — `auto.create` ممنوع (ADR-007)."""
    return set(_compose_specs())


#: مللي-ثانية في اليوم — لتحويل `retention_days` إلى ما يكتبه `rpk`.
_MS_PER_DAY = 86_400_000


def _shape_problems() -> list[str]:
    """
    يقارن **شكل** كل موضوع: الأقسام والاحتفاظ، لا الاسم وحده.

    اسمٌ مطابق بشكلٍ مختلف هو أسوأ من اسمٍ مفقود: الموضوع موجود، والبوّابة خضراء،
    والترتيب مكسور.
    """
    values = _topic_values_by_member()
    declared_specs = _declared_specs()
    compose_specs = _compose_specs()

    problems: list[str] = []
    for member, (partitions, retention_days) in sorted(declared_specs.items()):
        topic = values.get(member)
        if topic is None:
            problems.append(f"TopicSpec يشير إلى Topic.{member} غير المُعرَّف في السجلّ.")
            continue
        actual = compose_specs.get(topic)
        if actual is None:
            continue  # يُبلَّغ عنه أصلاً كموضوعٍ غير مُنشأ
        if actual[0] != partitions:
            problems.append(
                f"موضوع {topic}: السجلّ يُعلن {partitions} قسماً وcompose يُنشئ {actual[0]} — "
                "اختلاف الأقسام يكسر ترتيب أحداث الطالب الواحد."
            )
        expected_ms = retention_days * _MS_PER_DAY
        if actual[1] != expected_ms:
            problems.append(
                f"موضوع {topic}: السجلّ يُعلن {retention_days} يوماً ({expected_ms}ms) "
                f"وcompose يُنشئ {actual[1]}ms."
            )
    return problems


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

    problems.extend(_shape_problems())

    if problems:
        print("❌ تكافؤ المواضيع مخروق (D-201):")
        for problem in problems:
            print(f"   • {problem}")
        return 1

    print(f"✅ topic parity: {len(declared)} موضوعاً — السجلّ == العقد == compose.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
