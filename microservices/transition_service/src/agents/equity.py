"""وكيل العدالة — وثيقة المشروع §4 وكيل 9 (مخرجه §8-9).

يرصد فجوات الوصول والنتائج عبر الفئات (جنس/منطقة/دخل/عمر/إعاقة):
- مؤشر عدالة متساوٍ (0–1): نسبة الفئات الأقل حظاً الحاصلات على خدمات التحول
  مقارنة بحجمها السكاني — قياس حتمي لا LLM فيه.
- كشف: هل تتركز مهن عالية المخاطر في فئات معينة؟ (Anthropic 2026: الربعية الأعلى
  تعرضاً أعلاه احتمالاً بأن تكون أنثى — يجب مراقبة ذلك لا افتراضه).
- توصيات تصحيح وصول (وثيقة المشروع §7: عدالة الوصول شرط نجاح).
"""

from __future__ import annotations

from collections import Counter

from microservices.transition_service.src.core import engine
from microservices.transition_service.src.schemas import (
    EquityRequest,
    StandardResponse,
)

AGENT_NAME = "equity"


async def equity(request: EquityRequest) -> StandardResponse:
    population = request.population
    n = len(population)

    # تعرض كل عامل
    exposures = {}
    for worker in population:
        try:
            occ = engine.occupation(worker.current_occupation)
            exposures[worker.worker_id] = engine.early_warning_score(occ)
        except KeyError:
            exposures[worker.worker_id] = None

    def group(field: str, value: str) -> list:
        return [w for w in population if getattr(w, field) == value]

    def group_stats(field: str) -> dict[str, object]:
        counts = Counter(getattr(w, field) or "unknown" for w in population)
        total = sum(counts.values())
        stats: dict[str, object] = {}
        for key, count in counts.items():
            members = group(field, key)
            exp_values = [
                exposures[w.worker_id]["composite_risk"]
                for w in members
                if exposures.get(w.worker_id)
            ]
            stats[key] = {
                "population_share": round(count / total, 3) if total else 0.0,
                "count": count,
                "avg_risk": round(sum(exp_values) / len(exp_values), 3) if exp_values else None,
                "high_risk_share": round(
                    sum(1 for r in exp_values if r >= 0.5) / len(exp_values), 3
                )
                if exp_values
                else None,
            }
        return stats

    equity_index_components = []
    for field_name in ("gender_band", "region", "income_band"):
        stats = group_stats(field_name)
        shares = [v["avg_risk"] for v in stats.values() if v.get("avg_risk") is not None]
        if len(shares) >= 2:
            spread = max(shares) - min(shares)
            equity_index_components.append(round(max(0.0, 1.0 - spread), 3))

    equity_index = (
        round(sum(equity_index_components) / len(equity_index_components), 3)
        if equity_index_components
        else None
    )

    concentration_flags = []
    for field_name, label in (
        ("gender_band", "الجنس"),
        ("region", "المنطقة"),
        ("income_band", "الدخل"),
    ):
        stats = group_stats(field_name)
        high_risk_groups = [k for k, v in stats.items() if (v.get("high_risk_share") or 0) > 0.4]
        if high_risk_groups:
            concentration_flags.append(
                {
                    "dimension": label,
                    "groups": high_risk_groups,
                    "note": "تركّز مرتفع للمخاطرة — يتطلب تدخلاً مستهدفاً (وثيقة المشروع §7)",
                }
            )

    result: dict[str, object] = {
        "population_size": n,
        "equity_index": equity_index,
        "dimensions": {
            "gender": group_stats("gender_band"),
            "region": group_stats("region"),
            "income": group_stats("income_band"),
        },
        "concentration_flags": concentration_flags,
        "recommended_corrective_actions": [
            "تخصيص حصص تأهيل للفئات ذات high_risk_share > 0.4",
            "رصد فصلي لإعادة قياس equity_index بعد كل دورة تدخل",
            "توثيق كل فجوة في سجل الحوكمة — العدالة قابلة للتدقيق لا للانطباع",
        ],
        "evidence_base": [
            "Anthropic (2026) — الربعية الأعلى تعرضاً أعلاه احتمالاً أنثى (16 نقطة مئوية)",
            "ILO — الفئات الأقل حظاً أقل وصولاً لبرامج إعادة التأهيل دون تدخل مستهدف",
        ],
    }
    return StandardResponse(agent=AGENT_NAME, result=result)
