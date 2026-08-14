"""شرائح استخلاص فلاتر البحث (D-253).

فُكِّكت من `OrchestratorAgent._ai_extract_search_params` (A(4))
و`_heuristic_extract_search_params` (B(8)) إلى دوال نقية بلا حالة.
**صفر تغيير سلوكي**: النص التوجيهي وخريطة المواضيع وعتبات التنظيف مطابقة حرفًا.
"""

from __future__ import annotations

import json

SEARCH_PARAM_EXTRACTION_PROMPT = (
    "You are a search query parser for an educational database. "
    "Extract parameters from the user's request into a JSON object. "
    "Fields: q (keywords - EXTRACT THE TOPIC), year (int), subject (Mathematics, Physics), "
    "branch (experimental_sciences, math_tech, etc), set_name, level, type (exercise, lesson). "
    "\n\nIMPORTANT RULES:"
    "\n1. 'q' MUST contain the actual TOPIC/SUBJECT being searched, NOT the full question!"
    "\n2. Topics examples:"
    "\n   - 'probability' (احتمالات), 'complex numbers' (أعداد مركبة), 'sequences' (متتاليات)"
    "\n   - 'functions' (دوال), 'derivatives' (مشتقات), 'integrals' (تكامل)"
    "\n   - 'limits' (نهايات), 'continuity' (استمرارية), 'geometry' (هندسة)"
    "\n3. 'Subject 1' -> set_name: 'subject_1', 'Subject 2' -> set_name: 'subject_2'."
    "\n4. 'Experimental Sciences' (علوم تجريبية) -> branch: 'experimental_sciences'."
    "\n5. If a field is not present, omit it."
    "\n\nEXAMPLES:"
    "\n- 'تمرين أعداد مركبة' -> {'q': 'complex numbers'}"
    "\n- 'احتمالات بكالوريا 2024' -> {'q': 'probability', 'year': 2024, 'level': 'baccalaureate'}"
    "\n- 'متتاليات علوم تجريبية' -> {'q': 'sequences', 'branch': 'experimental_sciences'}"
    "\n- 'دوال أسية' -> {'q': 'exponential functions'}"
    "\n- 'نهايات ودوال' -> {'q': 'limits functions'}"
    "\n- 'سحب كرة' -> {'q': 'probability'} (this is about drawing balls = probability)"
)

# D-105: هذه الخريطة تنكمش فقط — كل إضافة كلمة هنا يجب أن تُحكَم بدليلٍ حيّ.
HEURISTIC_TOPIC_MAP: dict[str, str] = {
    # Arabic topics
    "أعداد مركبة": "complex numbers",
    "اعداد مركبة": "complex numbers",
    "مركب": "complex numbers",
    "احتمال": "probability",
    "احتمالات": "probability",
    "سحب": "probability",  # سحب كرة = drawing = probability
    "كرة": "probability",
    "كرات": "probability",
    "متتالي": "sequences",
    "متتاليات": "sequences",
    "دوال": "functions",
    "دالة": "functions",
    "نهاي": "limits",
    "نهايات": "limits",
    "تكامل": "integrals",
    "مشتق": "derivatives",
    "استمرار": "continuity",
    "هندس": "geometry",
    "أسية": "exponential",
    "لوغاريتم": "logarithm",
    # English topics
    "complex": "complex numbers",
    "probability": "probability",
    "sequence": "sequences",
    "function": "functions",
    "limit": "limits",
    "integral": "integrals",
    "derivative": "derivatives",
    "continuity": "continuity",
    "geometry": "geometry",
}

HEURISTIC_STOP_WORDS: set[str] = {
    "أريد",
    "أعطني",
    "اعطني",
    "هات",
    "التمرين",
    "تمرين",
    "بدون",
    "حل",
    "فقط",
}


def build_search_param_messages(question: str) -> list[dict[str, str]]:
    """الرسائل المرسلة إلى النموذج لاستخلاص فلاتر البحث."""
    return [
        {"role": "system", "content": SEARCH_PARAM_EXTRACTION_PROMPT},
        {"role": "user", "content": question},
    ]


def parse_search_params(raw: str | None) -> dict[str, object] | None:
    """فك ترميز JSON فلاتر البحث؛ لا شيء عند فراغٍ أو فشلٍ."""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def heuristic_extract_search_params(question: str) -> dict[str, object]:
    """استخلاصٌ حتميٌ احتياطي لفلاتر البحث مع كشف الموضوع."""
    params: dict[str, object] = {"limit": 5}
    q_lower = question.lower()

    # Topic detection (more specific) — أول مطابقةٍ تكفي (نفس الترتيب الأصلي).
    for keyword, topic in HEURISTIC_TOPIC_MAP.items():
        if keyword in q_lower:
            params["q"] = topic
            break

    # If no topic found, use cleaned question
    if "q" not in params:
        # Remove common request words, keep content words
        words = [w for w in question.split() if w not in HEURISTIC_STOP_WORDS and len(w) > 2]
        params["q"] = " ".join(words[:3]) if words else question

    return params


def finalize_search_params(params: dict[str, object]) -> dict[str, object]:
    """القاعدة الموحدة: حدّ العرض 5 مرشحات (نفس سلوك السلالة الأصلية)."""
    params["limit"] = 5
    return params
