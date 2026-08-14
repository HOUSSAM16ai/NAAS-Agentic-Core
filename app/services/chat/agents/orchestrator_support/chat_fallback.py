"""شريحة المحادثة الاحتياطية (D-253).

فُكِّكت من `OrchestratorAgent._handle_chat_fallback` (B(10))
و`_extract_marking_scheme_blocks` (A(5)) إلى دوال نقية بلا حالة.
**صفر تغيير سلوكي**: الأنماط والعتبات والنصوص مطابقة حرفًا.
"""

from __future__ import annotations

import re

MARKING_SCHEME_BLOCK_CHAR_LIMIT = 1500

MARKING_SCHEME_PATTERNS: tuple[str, ...] = (
    r"(?is)\n\[(grading|marking|rubric):[^\]]+\][\s\S]+?(?=\n\s*\[(ex|exercise|sol|solution):|$)",
    r"(?i)\n(#{1,3}\s*(سلم التنقيط|سلم التصحيح|marking scheme|grading scheme))[\s\S]+?(?=\n\s*\*{0,2}(#{1,3}|Exercise|Question|السؤال|تمرين|التمرين)|$)",
)

GRADING_REQUEST_DELIMITER = "\n\n### سلم التنقيط (Marking Scheme):\n"
GRADING_MISSING_WARNING = "\n\n⚠️ لم يتم العثور على سلم التنقيط في نص المحتوى."

FALLBACK_STRICT_INSTRUCTION = (
    "\nأنت معلم ذكي ومحترف (Smart Tutor)."
    "\nالقواعد الصارمة:"
    "\n1. إذا توفر محتوى تمرين في السياق (SIAQ)، التزم به حرفياً."
    "\n2. إذا لم يتوفر تمرين، اشرح المفهوم العلمي/الرياضي بشكل عام (General Concept) وشامل."
    "\n3. ممنوع منعاً باتاً اختراع تمارين أو أرقام من خيالك. قل 'لا يوجد تمرين محدد، لكن الفكرة هي...'."
    "\n4. اشرح 'لماذا' و 'كيف' دائماً لتبسيط التعقيدات."
)


def extract_marking_scheme_blocks(content: str) -> list[str]:
    """استخراج كتل سلم التنقيط من النص الخام إذا كانت مضمّنة (نفس الأنماط الأصلية)."""
    extracted: list[str] = []
    for pattern in MARKING_SCHEME_PATTERNS:
        for match in re.finditer(pattern, content, flags=re.DOTALL):
            block = match.group(0).strip()
            if block and block not in extracted:
                extracted.append(block)
    return extracted


def truncate_marking_scheme_block(block: str) -> str:
    """يقتصر طول كتلة سلم التنقيط على حد العرض الأصلي."""
    if len(block) > MARKING_SCHEME_BLOCK_CHAR_LIMIT:
        return block[:MARKING_SCHEME_BLOCK_CHAR_LIMIT] + "..."
    return block


def format_marking_scheme_delivery(blocks: list[str]) -> tuple[str, ...]:
    """يحوّل الكتل إلى دلتات عرض (أو تحذير عدم الوجود) — نفس الترميز الأصلي."""
    if not blocks:
        return (GRADING_MISSING_WARNING,)
    return (GRADING_REQUEST_DELIMITER, "\n\n".join(blocks))
