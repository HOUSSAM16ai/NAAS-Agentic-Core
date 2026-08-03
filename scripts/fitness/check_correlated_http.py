"""يمنع بناء ``httpx.AsyncClient`` مباشرةً خارج المصانع المصرَّح بها (D-189 · دَين D4).

**الجذر المُقاس:** ``.memory/roadmap.md §6.5.أ`` بند 4 — «`X-Correlation-ID` غير مضمون على
النداءات الصادرة» بدليل رقمي: عشرات البناءات المباشرة مقابل حقنٍ يدوي في ملفّات قليلة. أي
أن أغلب النداءات تعبر حدود الخدمات بلا هوية تتبّع، فتشخيص أي كارثة موزَّعة يصير تخميناً.

وكان العطب أعمق من نقصٍ في ترويسة: بعض مواضع الحقن كانت تُولِّد ``uuid4()`` **جديداً** لكل
نداء فتقطع سلسلة الأثر بدل أن تمدّها (``notation_skill.resolve_via_service`` — أُصلح في
D-189). ولذلك لا تكفي بوّابة تبحث عن نصّ الترويسة: **الوجود ليس صحّة**. الطريق الوحيد
لضمان الأثر هو أن يمرّ كل نداء من موضعٍ واحد يحقن المُعرَّف المحيط.

## العقد

- المصانع المصرَّح بها فقط تبني ``httpx.AsyncClient`` (الغلاف القانوني + مصانع التجميع).
- كل موضع آخر يستعمل ``shared.http_client.correlated_client`` (أو نسخته المُوَرَّدة داخل
  الخدمة — نمط D-185: مصدر واحد + مرآة محروسة، لا استيراد `shared` من خدمة مصغّرة).
- ما تبقّى **مُجمَّد ويتقلّص فقط** (سابقة D-105 وD-187): الدَّين مرئي ومحصور، لا مخفيّ.
  إضافة بناءٍ مباشر في ملفٍّ **جديد** ⇒ CI أحمر.

## لماذا الدَّين مُجمَّد لا مُصلَح دفعةً واحدة

الخدمات المصغّرة **لا تستورد `shared`** (صفر استيراد اليوم — الاتفاق هو التوريد المحروس
بتكافؤ حسب D-185). فإغلاق مواضعها يتطلّب نسخةً مُوَرَّدة + بوّابة تكافؤ لكل خدمة، وهذا
شوطٌ مستقلّ. وبعض المواضع تحتفظ بعميلٍ طويل العمر يُبنى مرّة عند الإنشاء، فحقن الترويسة
وقت البناء **يُجمِّد** المُعرَّف على أوّل دور — وهو خطأ أسوأ من غيابه. تلك تحتاج حقناً
لكل-طلب لا لكل-عميل.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ast_util import parse_source, run_gate

REPO_ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOTS = ("app", "microservices", "shared")

# المصانع المصرَّح بها: الغلاف القانوني نفسه + مصانع التجميع (تبني عملاء طويلي العمر
# مُجمَّعين، والمُعرَّف فيها يُحقن لكل-طلب لا لكل-عميل).
ALLOWED_FACTORIES = frozenset(
    {
        "shared/http_client/correlated.py",
        "app/core/http_client_factory.py",
        "microservices/orchestrator_service/src/core/http_client_factory.py",
    }
)

# الدَّين المُجمَّد: عدد البناءات المباشرة المسموح بها لكل ملفّ. **يتقلّص فقط.**
# القياس الأساس: 2026-07-29 (D-189) بعد هجرة الشوط الأول في المونوليث.
FROZEN_DEBT: dict[str, int] = {
    # ── المونوليث: عملاء طويلو العمر أو بوّابات تحتاج حقناً لكل-طلب ──
    "app/core/gateway/connection.py": 1,
    "app/gateway/gateway.py": 1,
    "app/gateway/registry.py": 1,
    "app/services/boundaries/observability_client.py": 1,
    "app/services/chat/tools/retrieval/remote_client.py": 1,
    # ── الخدمات المصغّرة: تحتاج نسخةً مُوَرَّدة + بوّابة تكافؤ (نمط D-185) ──
    "microservices/api_gateway/app/gateway.py": 1,
    "microservices/api_gateway/app/registry.py": 1,
    "microservices/api_gateway/proxy.py": 1,
    "microservices/auditor_service/src/ai.py": 1,
    "microservices/conversation_service/src/conversation_graph.py": 1,
    "microservices/conversation_service/src/math_pipeline.py": 1,
    "microservices/orchestrator_service/src/api/conversation_store.py": 1,
    "microservices/orchestrator_service/src/core/gateway/connection.py": 1,
    "microservices/orchestrator_service/src/infrastructure/clients/auditor_client.py": 2,
    "microservices/orchestrator_service/src/services/overmind/agents/memory.py": 1,
    "microservices/orchestrator_service/src/services/overmind/langgraph/research_agent_client.py": 2,
    "microservices/orchestrator_service/src/services/overmind/readiness.py": 1,
    # يُمرِّر correlation_id صراحةً بالفعل (مواطن صالح) — يبقى للاتساق حتى التوريد.
    "microservices/orchestrator_service/src/services/skills_pipeline.py": 1,
    "microservices/orchestrator_service/src/services/tools/retrieval/remote_client.py": 1,
    "microservices/reasoning_agent/src/ai_client.py": 1,
    "microservices/reasoning_agent/src/remote_retriever.py": 1,
    "microservices/research_agent/src/search_engine/super_search.py": 1,
}


def _is_async_client_call(node: ast.AST) -> bool:
    """يطابق ``httpx.AsyncClient(...)`` و``AsyncClient(...)`` المستوردة مباشرةً."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr == "AsyncClient"
    return isinstance(func, ast.Name) and func.id == "AsyncClient"


def _count_constructions(path: Path) -> int:
    """يعدّ بناءات ``AsyncClient`` في ملفٍّ عبر AST (لا grep — التعليقات لا تُحتسب)."""
    # ISS-149 (F1): يرفع — ملفٌّ لم يُقرأ لا يُبلَّغ عنه بصفر بناءات.
    tree = parse_source(path)
    return sum(1 for node in ast.walk(tree) if _is_async_client_call(node))


def _scan() -> dict[str, int]:
    """يمسح الشِّجَر المُراقَبة ويُرجع عدد البناءات لكل ملفّ إنتاجي."""
    found: dict[str, int] = {}
    for root in SCAN_ROOTS:
        for path in sorted((REPO_ROOT / root).rglob("*.py")):
            if "tests" in path.parts or path.name.startswith("test_"):
                continue
            count = _count_constructions(path)
            if count:
                found[path.relative_to(REPO_ROOT).as_posix()] = count
    return found


def main() -> int:
    """يفرض عقد التتبّع الصادر ويرجع 0 عند السلامة و1 عند أي انحراف."""
    found = _scan()
    failures: list[str] = []

    for rel_path, count in sorted(found.items()):
        if rel_path in ALLOWED_FACTORIES:
            continue
        allowed = FROZEN_DEBT.get(rel_path, 0)
        if count > allowed:
            failures.append(
                f"{rel_path}: {count} بناءً مباشراً لـ`httpx.AsyncClient` "
                f"(المسموح المُجمَّد {allowed}). استعمل "
                "`shared.http_client.correlated_client` — أو نسخةً مُوَرَّدة داخل الخدمة "
                "(نمط D-185) — فالنداء الصادر بلا `X-Correlation-ID` أثرٌ مثقوب."
            )

    # قاعدة «يتقلّص فقط»: مدخل مُجمَّد اختفى أو تقلّص ⇒ يجب تحديث الرقم كي لا يُعاد فتحه.
    for rel_path, allowed in sorted(FROZEN_DEBT.items()):
        actual = found.get(rel_path, 0)
        if actual < allowed:
            failures.append(
                f"{rel_path}: الدَّين تقلّص {allowed} → {actual}. "
                "خفّض الرقم في FROZEN_DEBT (أو احذف المدخل) — القاعدة: يتقلّص فقط ولا يُعاد فتحه."
            )

    if failures:
        print("❌ عقد التتبّع الصادر مخروق (D-189 · D4):")
        for failure in failures:
            print(f"   • {failure}")
        return 1

    debt_total = sum(FROZEN_DEBT.values())
    print(
        "✅ check_correlated_http: outbound HTTP goes through the correlated wrapper "
        f"or an allowed factory ({len(ALLOWED_FACTORIES)} factories, frozen debt {debt_total})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run_gate(main))
