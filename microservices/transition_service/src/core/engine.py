"""المحرك الحتمي للمنظومة — حسابات مؤشرات رصينة بلا LLM.

كل مؤشرات المنظومة (التعرض، التعزيز، فجوة المهارات، قرب الانتقال، الإنذار) تُحسب
حتمياً هنا من بيانات `data.occupations` — المحرك اللغوي يستعمل النتائج للسرد
والشرح فقط، ولا يحق له تعديل أي رقم. هذا يقابل فصل «القدرة النظرية / الاستخدام
المرصود» في Anthropic (2026) ومقياس β في Eloundou et al. (2023).
"""

from __future__ import annotations

from microservices.transition_service.src.data.occupations import (
    OBSERVED_WEIGHT,
    OCCUPATIONS,
    SKILLS,
    Occupation,
    TrainingUnit,
)


def occupation(code: str) -> Occupation:
    if code not in OCCUPATIONS:
        raise KeyError(f"occupation not in atlas: {code}")
    return OCCUPATIONS[code]


def _theoretical_beta(task_category: str) -> float:
    """β النظري — معيار Eloundou et al. (2023): 1 / 0.5 / 0."""
    return {"auto_full": 1.0, "auto_tools": 0.5, "augment": 0.1, "human_only": 0.0}.get(
        task_category, 0.0
    )


def theoretical_exposure(occ: Occupation) -> float:
    """التعرض النظري للمهنة (β المرجَّح بأجزاء الزمن) — Science 2023 convention."""
    total_time = sum(t.time_fraction for t in occ.tasks)
    if total_time <= 0:
        return 0.0
    return sum(_theoretical_beta(t.category) * t.time_fraction for t in occ.tasks) / total_time


def observed_exposure(occ: Occupation) -> float:
    """التعرض المرصود (β × وزن الاستخدام) — Anthropic Economic Index convention.

    يوضح لماذا تفشل مقاييس القدرة النظرية وحدها في التنبؤ (درس التعهيد الخارجي)،
    ولماذا تحتاج منظومة الإنذار المبكر إشارتيّ الطلب والتغطية معاً.
    """
    total_time = sum(t.time_fraction for t in occ.tasks)
    if total_time <= 0:
        return 0.0
    return (
        sum(
            _theoretical_beta(t.category) * OBSERVED_WEIGHT[t.category] * t.time_fraction
            for t in occ.tasks
        )
        / total_time
    )


def augmentation_index(occ: Occupation) -> float:
    """مؤشر التعزيز — حصة المهام التي يصبح فيها الإنسان أكثر إنتاجية لا أقل."""
    total_time = sum(t.time_fraction for t in occ.tasks)
    if total_time <= 0:
        return 0.0
    return sum(t.time_fraction for t in occ.tasks if t.category == "augment") / total_time


def human_core_index(occ: Occupation) -> float:
    """مؤشر النواة الإنسانية — حصة المهام غير القابلة للاستبدال."""
    total_time = sum(t.time_fraction for t in occ.tasks)
    if total_time <= 0:
        return 0.0
    return sum(t.time_fraction for t in occ.tasks if t.category == "human_only") / total_time


def risk_band(score: float) -> str:
    """تصنيف نطاق المخاطرة للانتقال — وثيقة المشروع §4 (مستويات مخاطرة)."""
    if score >= 0.6:
        return "critical"  # تدخل عاجل: إعادة تأهيل مكثفة
    if score >= 0.35:
        return "elevated"  # مراقبة نشطة + تأهيل استباقي
    if score >= 0.15:
        return "watch"  # رصد دوري
    return "stable"  # نمو/ثبات — استثمار


def skills_gap(current: tuple[str, ...], future: tuple[str, ...]) -> dict[str, object]:
    """فجوة المهارات: المطلوبة - المتوفرة.

    المستوى الفردي: مدخلات worker؛ المستوى القطاعي/الوطني: مجموعات مهن
    (يُجمَّع خارج هذه الدالة حتمياً — لا LLM يقرر التجميع).
    """
    required = {s for s in future if s in SKILLS}
    possessed = {s for s in current if s in SKILLS}
    missing = sorted(required - possessed)
    excess = sorted(possessed - required)
    overlapping = sorted(required & possessed)
    gap_ratio = len(missing) / len(required) if required else 0.0
    return {
        "required_skills": sorted(required),
        "possessed_skills": sorted(possessed),
        "missing_skills": missing,
        "excess_skills": excess,
        "overlapping_skills": overlapping,
        "gap_ratio": round(gap_ratio, 3),
        "gap_severity": "high" if gap_ratio >= 0.6 else ("medium" if gap_ratio >= 0.3 else "low"),
    }


def _skill_distance(a: str, b: str) -> float:
    """مسافة مهارية بسيطة: نفس = 0، نفس النوع = 0.4، مختلف النوع = 1.0."""
    if a == b:
        return 0.0
    sa, sb = SKILLS.get(a), SKILLS.get(b)
    if sa is None or sb is None:
        return 1.0
    if sa.kind == sb.kind:
        return 0.4
    return 1.0


def transition_distance(source: Occupation, target: Occupation) -> float:
    """مسافة انتقال مهارية بين مهنتين (0 = نفس المهارات، 1 = لا علاقة).

    مستندة إلى مبدأ القرب المهني (Pomsland et al., NBER 2025 — تكيفية العمال
    ترتبط بقرب المهنة من مصدر الاضطراب). المتوسط المرجَّح: المهارات المطلوبة
    في المهنة الهدف التي يملكها المصدر تخفض المسافة.
    """
    target_skills = [s for s in target.current_skills if s in SKILLS]
    if not target_skills:
        return 1.0
    distances = [
        _skill_distance(t, s) for t in target_skills for s in source.current_skills if s in SKILLS
    ]
    if not distances:
        return 1.0
    # أفضل تغطية مهارية متوفرة للمهن المطلوبة في الهدف
    per_target = {}
    for t in target_skills:
        cands = [_skill_distance(t, s) for s in source.current_skills if s in SKILLS]
        per_target[t] = min(cands) if cands else 1.0
    return round(sum(per_target.values()) / len(per_target), 3)


def recommended_paths(
    source: Occupation, candidates: tuple[Occupation, ...]
) -> list[dict[str, object]]:
    """مسارات الانتقال الموصى بها مرتبة بالقرب المهارية (الأكبر قرباً أولاً)."""
    scored = []
    for target in candidates:
        dist = transition_distance(source, target)
        scored.append(
            {
                "occupation": target.code,
                "label_ar": target.label_ar,
                "demand_signal": target.demand_signal,
                "skill_distance": dist,
                "transition_feasibility": round(
                    max(0.0, min(1.0, 1.0 - dist + target.demand_signal * 0.15)), 3
                ),
                "rationale": (
                    f"نمو الطلب {'مرتفع' if target.demand_signal > 0.4 else ('متوسط' if target.demand_signal > 0 else 'منخفض')}"
                    f" وقرب مهاري {dist:.2f}"
                ),
            }
        )
    scored.sort(key=lambda r: (-r["transition_feasibility"], r["skill_distance"]))
    return scored


def training_coverage(source: Occupation, target: Occupation) -> list[dict[str, object]]:
    """وحدات التدريب القصيرة التي تسد فجوة الانتقال من المصدر إلى الهدف."""
    source_skills = set(source.current_skills) & set(SKILLS)
    target_skills = set(target.current_skills) & set(SKILLS)
    missing = sorted(target_skills - source_skills)
    result: list[dict[str, object]] = []
    for unit in TrainingUnit.all().values():
        covers = [s for s in unit.skills if s in set(missing)]
        if covers:
            result.append(
                {
                    "unit": unit.code,
                    "label_ar": unit.label_ar,
                    "duration_weeks": unit.duration_weeks,
                    "skills_covered": sorted(covers),
                    "remaining_after": sorted(set(missing) - set(covers)),
                }
            )
    # الأصغر مدةً أولاً مع تغطية أعلى
    result.sort(key=lambda r: (-len(r["skills_covered"]), r["duration_weeks"]))
    return result


def early_warning_score(occ: Occupation) -> dict[str, object]:
    """مؤشر الإنذار المبكر المركب: تعرض نظري + مرصود + اتجاه الطلب."""
    theo = theoretical_exposure(occ)
    obs = observed_exposure(occ)
    return {
        "occupation": occ.code,
        "theoretical_exposure": round(theo, 3),
        "observed_exposure": round(obs, 3),
        "demand_signal": occ.demand_signal,
        "theoretical_observed_gap": round(theo - obs, 3),
        "composite_risk": round((0.35 * theo + 0.35 * obs - 0.3 * occ.demand_signal), 3),
        "risk_band": risk_band(0.35 * theo + 0.35 * obs - 0.3 * occ.demand_signal),
    }
