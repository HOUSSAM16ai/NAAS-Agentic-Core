"""وكيل الحوكمة والامتثال الخوارزمي — وثيقة المشروع §4 وكيل 8 (مخرجه §8-8).

مخرجه تدقيق امتثال لنظام خوارزمي في سياق التوظيف أو إدارة العمال:
- تحديد إذا كان النظام «عالي المخاطر» وفق EU AI Act Art. 6 (التوظيف، إدارة العمال).
- متطلبات الالتزام (Art. 13 الشفافية، Art. 14 الإشراف البشري، Art. 26 مراقبة البشر).
- كشف إدارة خوارزمية مفرطة (OECD 2025: 90% من المديرين في الولايات المتحدة يستخدمون
  أداة واحدة على الأقل — فجوة حوكمة).
- توصيات آليات الاعتراض والاستئناف البشرية.

التصنيف حتمي من كلمات النظام؛ لا LLM يحكم على الخطورة.
"""

from __future__ import annotations

from microservices.transition_service.src.schemas import (
    GovernanceRequest,
    StandardResponse,
)

AGENT_NAME = "governance"

HIRING_CONTEXTS = ("hiring", "recruitment", "promotion", "termination")


async def governance(request: GovernanceRequest) -> StandardResponse:
    is_high_risk = request.system_type in HIRING_CONTEXTS or any(
        keyword in request.decision_description.lower()
        for keyword in ("توظيف", "فصل", "ترقية", "تقييم أداء", "أجر", "جدولة")
    )

    requirements = []
    if is_high_risk:
        requirements = [
            {
                "obligation": "تسجيل النظام ضمن أنظمة الذكاء الاصطناعي عالية المخاطر",
                "article": "EU AI Act Art. 6 (Annex III: employment)",
            },
            {
                "obligation": "شفافية للموظف/المرشح: ما يُحلَّل، وما يؤثر في القرار",
                "article": "Art. 13",
            },
            {"obligation": "إشراف بشري فعال مع صلاحية إيقاف/تعديل القرار", "article": "Art. 14"},
            {"obligation": "مراقبة بشرية مستمرة للأداء والانحياز", "article": "Art. 26"},
            {"obligation": "حفظ سجلات وبيانات تدريب للتدقيق", "article": "Art. 12"},
            {"obligation": "تقييم دقة وصلابة وانحياز قبل النشر وأثناءه", "article": "Art. 10"},
        ]
    else:
        requirements = [
            {
                "obligation": "إبلاغ المستخدم بأنه يتفاعل مع نظام ذكاء اصطناعي",
                "article": "Art. 50 (transparency)",
            },
            {"obligation": "مراجعة دورية للانحياز", "article": "OECD AI Recommendation: fairness"},
        ]

    oversight_excess_indicators = []
    if (
        "أتمت" in request.decision_description.lower()
        or "automat" in request.decision_description.lower()
    ):
        oversight_excess_indicators.append(
            "قرار مؤتمت بالكامل في سياق عمل — يجب توفير مسار اعتراض بشري فوري"
        )
    if request.system_type == "worker_management":
        oversight_excess_indicators.append(
            "إدارة خوارزمية للعمال: OECD 2025 — 90% من المديرين يستخدمون أداة AM واحدة على الأقل "
            "مع فجوات حوكمة واسعة — يلزم سياسة استخدام معلنة ومراجعة ربع سنوية"
        )

    appeal_mechanism = {
        "required": is_high_risk,
        "elements": [
            "قناة اعتراض مكتوبة يرد عليها خلال 14 يوم عمل",
            "مراجع بشري مستقل لم يكن طرفاً في القرار",
            "توثيق أسباب الرفض/القبول بلغة مفهومة",
            "حق إعادة النظر لمرة ثانية أمام لجنة أعلى",
        ],
    }

    result: dict[str, object] = {
        "system_type": request.system_type,
        "decision_summary": request.decision_description,
        "risk_classification": "high" if is_high_risk else "standard",
        "eu_ai_act_classification": "high-risk" if is_high_risk else "limited-risk",
        "obligations": requirements,
        "oversight_excess_flags": oversight_excess_indicators,
        "affected_groups": request.affected_groups,
        "appeal_mechanism": appeal_mechanism,
        "evidence_base": [
            "EU AI Act (2024) — أنظمة التوظيف وإدارة العمال عالية المخاطر",
            "OECD (2025) — فجوة حوكمة الإدارة الخوارزمية",
            "OECD AI Recommendation (2019, updated) — عدالة وشفافية ومساءلة",
        ],
        "decision_note": "التزامات إلزامية — التنفيذ والمسؤولية بيد الجهة المشغلة للجنة الحوكمة البشرية",
    }
    return StandardResponse(agent=AGENT_NAME, result=result)
