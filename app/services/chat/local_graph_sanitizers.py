"""مُطهِّرات ردّ الرسم المحلي (D-170 Stage D — مُستخرَجة حرفياً من local_graph).

استبدال foreign-script + إزالة meta-narration السقراطي + حُرّاس التكرار/الدقة —
دوال نقيّة (string ops، صفر تبعية module). `local_graph` يعيد تصديرها (re-export
خلفي) فكل مستدعٍ داخلي بلا تغيير. الفصل يعزل «تنظيف النصّ» عن «تشغيل الرسم» (SRP).
"""

from __future__ import annotations

import re as _re_sanitize

# الكلمات المختلطة (Russian/Norwegian/Spanish/etc) → استبدالها بالعربية المتوقَّعة
_FOREIGN_REPLACEMENTS = {
    # روسي
    "линейный": "خطي",
    "линейная": "خطية",
    "линейное": "خطية",
    "функция": "دالة",
    "уравнение": "معادلة",
    # نرويجي/دانماركي
    "også": "أيضاً",
    "auch": "أيضاً",
    # إسباني
    "aparece": "يظهر",
    "aparecen": "تظهر",
    # إنجليزي meta في رد عربي
    "wishes": "أمنيات",
    "invitation": "دعوة",
    # CJK punctuation → علامات عربية
    "。": ".",
    "（": "(",
    "）": ")",
    "「": '"',
    "」": '"',
    "『": '"',
    "』": '"',
    "、": "،",
    "〜": "~",
}

# meta-narration بالإنجليزية في بداية ردود chat
_CHAT_META_PATTERNS = [
    _re_sanitize.compile(r"^Okay,\s+the user[^.\n]*\.\s*", _re_sanitize.IGNORECASE),
    _re_sanitize.compile(
        r"^First,?\s+I\s+(should|must|need|will)[^.\n]*\.\s*", _re_sanitize.IGNORECASE
    ),
    _re_sanitize.compile(
        r"^The user (greeted|said|asked|wrote)[^.\n]*\.\s*", _re_sanitize.IGNORECASE
    ),
    _re_sanitize.compile(r"^I need to (respond|answer|reply)[^.\n]*\.\s*", _re_sanitize.IGNORECASE),
    _re_sanitize.compile(
        r"^Let me (think|respond|answer|consider)[^.\n]*\.\s*", _re_sanitize.IGNORECASE
    ),
    _re_sanitize.compile(
        r"^Alright,\s+(the\s+)?(user|question|so)[^.\n]*\.\s*", _re_sanitize.IGNORECASE
    ),
]


def _normalize_for_dedup(text: str) -> str:
    """يُطبّع الفقرة لأغراض كشف التكرار دون تغيير النص الأصلي."""
    collapsed = _re_sanitize.sub(r"\s+", " ", text).strip()
    # توحيد بسيط للترقيم العربي/اللاتيني لتقليل false negatives
    return collapsed.replace("—", "-").replace("–", "-")


def _token_signature(text: str) -> frozenset[str]:
    """يبني بصمة كلمات مستقرة لكشف التكرار شبه المتطابق."""
    return frozenset(tok for tok in _re_sanitize.findall(r"\w+", text.lower()) if len(tok) >= 2)


def _is_long_educational_scaffold(norm: str, raw: str) -> bool:
    """يحدد إن كانت الكتلة قالباً تعليمياً طويلاً قابلاً للتكرار الكارثي."""
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    has_steps = bool(_re_sanitize.search(r"(^|\n)\s*(\d+[).]|[-*•])\s*", raw))
    return len(norm) >= 140 and len(lines) >= 4 and has_steps


def _is_near_duplicate(
    sig_a: frozenset[str], sig_b: frozenset[str], threshold: float = 0.82
) -> bool:
    """مقارنة تشابه Jaccard لكشف نسخة مكررة بصياغة سطحية مختلفة."""
    if not sig_a or not sig_b:
        return False
    inter = len(sig_a & sig_b)
    union = len(sig_a | sig_b)
    if union == 0:
        return False
    return (inter / union) >= threshold


def _build_precision_guardrail(question: str, intent: str) -> str:
    """يبني حارس دقة موجزاً مرتبطاً بسؤال الطالب للحد من الانحراف/الهلوسة."""
    if intent not in ("educational", "general"):
        return ""
    q = question.strip()
    if not q:
        return ""
    numbers = _re_sanitize.findall(r"\b\d+\b", q)
    arabic_colors = [c for c in ("بيضاء", "حمراء", "خضراء", "زرقاء", "سوداء", "صفراء") if c in q]
    key_terms = [t for t in ("احتمالات", "شجرة", "بدون إرجاع", "احتمال شرطي", "تمرين") if t in q]
    constraints: list[str] = [
        "- لا تخترع معطيات جديدة غير موجودة في سؤال الطالب.",
        "- إذا كان هناك نقص أو تناقض في المعطيات، صرّح بالفرضية قبل الحساب.",
        "- لا تكرر نفس الفقرة/القائمة بصياغة مختلفة.",
    ]
    if numbers:
        constraints.append(
            f"- الأعداد المذكورة في السؤال (مرجع إلزامي): {', '.join(numbers[:12])}."
        )
    if arabic_colors:
        constraints.append(
            f"- الألوان المذكورة في السؤال (مرجع إلزامي): {', '.join(arabic_colors)}."
        )
    if key_terms:
        constraints.append(f"- المفاهيم المطلوبة: {', '.join(key_terms)}.")
    if "شجرة" in q:
        constraints.append("- عند طلب شجرة احتمالات: قدّم سحباً متتالياً بفروع واحتمال كل فرع.")
    return "## حارس الدقة المرتبط بالسؤال\n" + "\n".join(constraints)


def _strip_unrequested_color_lines(question: str, answer: str, intent: str) -> str:
    """يحذف سطور ألوان مخترعة في مسائل الاحتمالات إذا لم تَرِد في السؤال."""
    try:
        from app.services.skills import (
            ExerciseAlignmentInput,
            get_exercise_alignment_skill,
        )

        aligned = get_exercise_alignment_skill().align(
            ExerciseAlignmentInput(question=question, answer=answer, intent=intent)
        )
        return aligned.aligned_answer
    except Exception:
        return answer


def _dedupe_repeated_blocks(text: str) -> str:
    """يحذف الفقرات/السطور المتطابقة المتجاورة لمنع تكرار الردود الكارثي.

    يعتمد على قاعدة بسيطة وحتمية:
    - تقسيم النص إلى blocks بواسطة سطر فارغ.
    - إسقاط أي block متطابق مع آخر block مُحتفَظ به (بعد التطبيع).
    """
    blocks = [b.strip() for b in text.split("\n\n")]
    kept: list[str] = []
    last_norm = ""
    last_tail_norm = ""
    seen_long_scaffolds: list[frozenset[str]] = []
    for block in blocks:
        if not block:
            continue
        norm = _normalize_for_dedup(block)
        if norm and (norm == last_norm or (last_tail_norm and norm == last_tail_norm)):
            continue
        if _is_long_educational_scaffold(norm, block):
            sig = _token_signature(norm)
            if any(_is_near_duplicate(sig, seen_sig) for seen_sig in seen_long_scaffolds):
                continue
            seen_long_scaffolds.append(sig)
        kept.append(block)
        last_norm = norm
        lines = block.splitlines()
        last_tail_norm = _normalize_for_dedup("\n".join(lines[1:])) if len(lines) >= 2 else ""
    if not kept:
        return text
    return "\n\n".join(kept).strip()


def _sanitize_local_graph_response(text: str, intent: str) -> str:
    """ISS-075 (D-063): ينظف foreign-script + chat meta-narration من ردود local_graph.

    يعالج كارثة التحية التي شاهدها المستخدم: «السلام عليكم» يُولِّد رداً
    etymological مع كلمات نرويجية (`også`) وإنجليزية (`wishes`) ونقاط CJK (`。`).

    الـ greeting الآن يُصنَّف كـ chat (بعد regex fix) فيُمر هنا للتنظيف الأخير.
    """
    if not text:
        return text
    out = text
    # 1. استبدالات foreign → عربي
    for foreign, arabic in _FOREIGN_REPLACEMENTS.items():
        out = out.replace(foreign, arabic)
    # 2. حذف Cyrillic كامل (روسي/أوكراني)
    out = _re_sanitize.sub(r"[Ѐ-ӿ]+", "", out)
    # 3. حذف Chinese CJK Han
    out = _re_sanitize.sub(r"[一-鿿]+", "", out)
    # 4. حذف Hiragana/Katakana (ياباني)
    out = _re_sanitize.sub(r"[぀-ゟ゠-ヿ]+", "", out)
    # 5. للـ chat فقط — احذف meta-narration بالإنجليزية في البداية
    if intent == "chat":
        for _ in range(5):  # multi-pass
            prev = out
            for rx in _CHAT_META_PATTERNS:
                out = rx.sub("", out, count=1)
            out = out.lstrip()
            if out == prev:
                break
    # 6. إزالة التكرار المتجاور الذي يظهر أحياناً في الإجابات الطويلة
    return _dedupe_repeated_blocks(out)
