"""وكيل الحوار الاجتماعي — وثيقة المشروع §4 وكيل 11 (مخرجه §8-11).

يلخّص ملاحظات الأطراف المعنية (عمال/أصحاب عمل/نقابات/حكومة/معلمون/مواطنون)
ويصنّفها حتمياً حسب الموضوع (وظائف/تأهيل/حوكمة/عدالة/أجور) — التصنيف
بالكلمات المفتاحية لا LLM، والمحرك اللغوي يسرد فقط.
"""

from __future__ import annotations

from microservices.transition_service.src.schemas import (
    DialogueRequest,
    StandardResponse,
)

AGENT_NAME = "dialogue"

THEME_KEYWORDS: dict[str, tuple[str, ...]] = {
    "jobs_security": ("وظائف", "استقرار", "فصل", "أمان وظيفي", "jobs", "employment", "layoffs"),
    "reskilling": ("تدريب", "تأهيل", "مهارات", "دورة", "training", "reskilling", "skills"),
    "governance": ("حوكمة", "خوارزمية", "انحياز", "رقابة", "governance", "bias", "algorithmic"),
    "equity": ("عدالة", "فئات", "مساواة", "منطقة", "مرأة", "equity", "fairness", "women"),
    "wages": ("أجر", "راتب", "دخل", "wage", "salary", "income"),
    "education": ("تعليم", "منهج", "معلم", "طالب", "education", "curriculum", "teacher"),
}


def _classify(text: str) -> list[str]:
    lowered = text.lower()
    matched = [theme for theme, kws in THEME_KEYWORDS.items() if any(kw in lowered for kw in kws)]
    return matched if matched else ["general"]


async def dialogue(request: DialogueRequest) -> StandardResponse:
    themes = _classify(request.feedback_text)
    sentiment_score = sum(
        1
        for kw in ("جيد", "ممتاز", "مفيد", "إيجابي", "شكراً", "شكرا", "good", "great", "helpful")
        if kw in request.feedback_text.lower()
    ) - sum(
        1
        for kw in ("سيء", "فشل", "خطأ", "مرفوض", "خائف", "قلق", "bad", "fail", "worried", "afraid")
        if request.feedback_text.lower()
    )

    result: dict[str, object] = {
        "stakeholder": request.stakeholder,
        "themes_detected": themes,
        "sentiment_score": sentiment_score,
        "feedback_digest": request.feedback_text[:500],
        "routed_to": {
            "jobs_security": "لجنة سوق العمل",
            "reskilling": "مراكز التأهيل المهني",
            "governance": "لجنة الحوكمة البشرية",
            "equity": "لجنة العدالة والوصول",
            "wages": "لجنة الأجور والحماية الاجتماعية",
            "education": "لجنة تطوير المناهج",
            "general": "الأمانة العامة للحوار الاجتماعي",
        },
        "participation_record": {
            "stakeholder": request.stakeholder,
            "themes": themes,
            "acknowledged": True,
        },
        "evidence_base": [
            "وثيقة المشروع §3 — المشاركة الاجتماعية شرط شرعية المنظومة",
            "ILO Tripartite Declaration — الحوار الاجتماعي الثلاثي أساس سياسات العمل",
        ],
        "decision_note": "تغذية راجعة مسجلة ومؤرشفة — الاستجابة التصرفية بيد اللجان البشرية المختصة",
    }
    return StandardResponse(agent=AGENT_NAME, result=result)
