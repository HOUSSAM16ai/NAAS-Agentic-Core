"""شرائح الشرح التربوي (D-253).

فُكِّكت من `OrchestratorAgent._generate_explanation` (تعقيد B(8)) إلى دوال
نقية صغيرة بلا حالة — دالة واحدة مسؤولة عن كل بناء رسالة، والـagent يركّبها.
**صفر تغيير سلوكي**: النصوص والأنماط والأولويات مطابقة حرفيًا للسلوك الأصلي.
"""

from __future__ import annotations

SMART_TUTOR_SYSTEM_PROMPT = (
    "أنت 'Overmind'، المعلم الذكي فائق القدرات (Smart Tutor)."
    "\nمهمتك: تقديم شرح فاخر (Luxury)، عميق، ومبسط للتمرين المسترجع."
    "\n\nالتعليمات الصارمة:"
    "\n1. التزم كلياً بـ 'الحل الرسمي' (Official Solution) الموجود في السياق أدناه. هو المصدر الوحيد للحقيقة."
    "\n2. لا تكتفِ بسرد الحل؛ اشرح 'لماذا' و 'كيف' وصلنا لهذه النتيجة."
    "\n3. بسّط المفاهيم المعقدة لتناسب طالباً ذا قدرات محدودة، لكن بأسلوب راقٍ واحترافي."
    "\n4. إذا لم يوجد حل رسمي، استخدم خبرتك لشرح المفهوم دون اختراع أرقام."
    "\n5. الهدف: جعل الطالب يفهم أعمق التفاصيل بسهولة تامة."
)

EXERCISE_TEXT_PREFIX = "نص التمرين (Exercise):"
SOLUTION_TEXT_PREFIX = "الحل الرسمي (Official Solution - STRICTLY ADHERE TO THIS):"
NO_SOLUTION_NOTE = "ملاحظة: لا يوجد حل رسمي مسجل. اشرح المفهوم العام فقط.\n\n"
EXPLANATION_ASK = "المطلوب: اشرح الحل للطالب بأسلوب 'Smart Tutor' (عميق، مبسط، واحترافي)."

SMART_TUTOR_FALLBACK_STRICT = (
    "\nأنت معلم ذكي ومحترف (Smart Tutor)."
    "\nالقواعد الصارمة:"
    "\n1. إذا توفر محتوى تمرين في السياق (SIAQ)، التزم به حرفياً."
    "\n2. إذا لم يتوفر تمرين، اشرح المفهوم العلمي/الرياضي بشكل عام (General Concept) وشامل."
    "\n3. ممنوع منعاً باتاً اختراع تمارين أو أرقام من خيالك. قل 'لا يوجد تمرين محدد، لكن الفكرة هي...'."
    "\n4. اشرح 'لماذا' و 'كيف' دائماً لتبسيط التعقيدات."
)

EXERCISE_CONTENT_REQUEST = "SIAQ (History):"


def build_explanation_system_prompt(personalization_context: str) -> str:
    """النص النظامي لشرح التمرين على الحل الرسمي (نفس السلوك الأصلي حرفيًا)."""
    system_prompt = SMART_TUTOR_SYSTEM_PROMPT
    if personalization_context:
        system_prompt += f"\n\nمرجع الجودة التعليمية الموحد:\n{personalization_context}"
    return system_prompt


def build_explanation_user_message(
    question: str,
    content: str,
    solution: str | None,
) -> str:
    """رسالة المستخدم لشرح تمرينٍ مع الحل الرسمي كمصدر حقيقة."""
    user_message = f"سؤال الطالب: {question}\n\n"
    user_message += f"{EXERCISE_TEXT_PREFIX}\n{content}\n\n"

    if solution:
        user_message += f"{SOLUTION_TEXT_PREFIX}\n{solution}\n\n"
    else:
        user_message += NO_SOLUTION_NOTE

    user_message += EXPLANATION_ASK
    return user_message


def build_chat_fallback_messages(
    *,
    base_prompt: str,
    strict_instruction: str,
    personalization_context: str,
    system_context: str,
    history_text: str,
    question: str,
) -> list[dict[str, str]]:
    """رسائل المحادثة الاحتياطية (Smart Tutor عام بلا تمرين محمَّل)."""
    personalization_block = ""
    if personalization_context:
        personalization_block = f"\nمرجع الجودة:\n{personalization_context}"
    final_prompt = f"{base_prompt}\n{strict_instruction}{personalization_block}\n{system_context}\n{history_text}"
    return [
        {"role": "system", "content": final_prompt},
        {"role": "user", "content": question},
    ]


def build_fallback_history_text(history_messages: list[object] | None) -> str:
    """نص التاريخ (آخر 10 رسائل) لمحادثة احتياطية — نفس السلوك الأصلي حرفيًا."""
    if not history_messages:
        return ""
    recent = history_messages[-10:]
    return "\nSIAQ (History):\n" + "\n".join(
        [f"{m.get('role')}: {m.get('content')}" for m in recent]  # type: ignore[union-attr]
    )
