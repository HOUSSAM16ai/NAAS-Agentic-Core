"""شريحة سياق التاريخ (D-253).

فُكِّكت من `OrchestratorAgent._resolve_contextual_reference`
و`_inject_recent_history_context` و`_extract_context_anchor`
و`_looks_like_pronoun_followup` و`_build_recent_history_brief`
(مجتمعة B(7)–C(12)) إلى دوال نقية بلا حالة.
**صفر تغيير سلوكي**: العلامات والنصوص والعتبات مطابقة حرفًا للنص الأصلي.
"""

from __future__ import annotations


def looks_like_pronoun_followup(question: str) -> bool:
    """يتحقق ما إذا كان السؤال يعتمد غالبًا على ضمير مرجعي يحتاج سياقًا سابقًا."""
    lowered = question.casefold()
    pronoun_markers = (
        "ها",
        "عاصمتها",
        "سكانها",
        "مساحتها",
        "موقعها",
        "علمها",
        "اقتصادها",
        "تاريخها",
    )
    if any(marker in lowered for marker in pronoun_markers):
        return True
    demonstratives = ("هذا", "هذه", "ذلك", "تلك", "هاته", "this", "that", "there")
    referential_nouns = (
        "الدولة",
        "البلد",
        "المدينة",
        "الكيان",
        "الدالة",
        "المعادلة",
        "التمرين",
        "السؤال",
        "function",
        "equation",
        "problem",
    )
    if any(word in lowered for word in demonstratives) and any(
        noun in lowered for noun in referential_nouns
    ):
        return True
    return lowered.startswith(("كيف جاءت", "كيف حصل", "كيف صارت", "لماذا جاءت"))


def extract_context_anchor(
    history_messages: list[object] | None,
    current_question: str,
) -> str | None:
    """يستخرج مرجعًا سياقيًا موثوقًا من history_messages مع استبعاد السؤال الحالي."""
    if not isinstance(history_messages, list):
        return None

    normalized_current = current_question.strip().casefold()
    skipped_current_user = False
    for item in reversed(history_messages):
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        if role not in {"user", "assistant"}:
            continue
        content = item.get("content")
        if not isinstance(content, str):
            continue
        cleaned = content.strip()
        if not cleaned:
            continue
        if role == "user" and not skipped_current_user and cleaned.casefold() == normalized_current:
            skipped_current_user = True
            continue
        return cleaned
    return None


def resolve_contextual_reference(question: str, context: dict[str, object]) -> str:
    """يربط السؤال بآخر مرجعٍ حيّ من التاريخ عند المتابعة الضمنية.

    يهدف هذا التابع لتقليل حالات "العمى السياقي" عندما يرسل المستخدم
    أسئلة مختصرة مثل: "ما هي عاصمتها؟" بعد ذكر كيان واضح في الرسالة السابقة.
    """
    trimmed_question = question.strip()
    if not trimmed_question:
        return trimmed_question
    if not looks_like_pronoun_followup(trimmed_question):
        return trimmed_question

    anchor_message = extract_context_anchor(
        history_messages=context.get("history_messages"),
        current_question=trimmed_question,
    )
    if not anchor_message:
        return trimmed_question

    return f"{trimmed_question}\n\nمرجع سياقي إلزامي من الرسائل السابقة: {anchor_message}"


def build_recent_history_brief(
    history_messages: list[object] | None,
    current_question: str,
) -> str:
    """يبني موجزًا مختصرًا من آخر الرسائل مع تجاهل السؤال الحالي."""
    if not isinstance(history_messages, list):
        return ""

    normalized_current = current_question.strip().casefold()
    items: list[str] = []
    skipped_current_user = False

    for item in reversed(history_messages):
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        if role not in {"user", "assistant"}:
            continue
        content = item.get("content")
        if not isinstance(content, str):
            continue
        cleaned = " ".join(content.split()).strip()
        if not cleaned:
            continue
        if role == "user" and not skipped_current_user and cleaned.casefold() == normalized_current:
            skipped_current_user = True
            continue
        role_label = "المستخدم" if role == "user" else "المساعد"
        items.append(f"- {role_label}: {cleaned[:220]}")
        if len(items) >= 4:
            break

    items.reverse()
    return "\n".join(items)


def inject_recent_history_context(question: str, context: dict[str, object]) -> str:
    """يحقن موجزًا من التاريخ الحديث لإبقاء وعي السياق فعالًا في كل الأسئلة."""
    history_brief = build_recent_history_brief(
        history_messages=context.get("history_messages"),
        current_question=question,
    )
    if not history_brief:
        return question
    if "سياق المحادثة السابق (موجز)" in question:
        return question
    return f"سياق المحادثة السابق (موجز):\n{history_brief}\n\nالسؤال الحالي: {question}"
