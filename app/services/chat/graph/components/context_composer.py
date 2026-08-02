import re
from typing import ClassVar

from app.core.interfaces import IContextComposer
from app.services.chat.graph.domain import WriterIntent
from shared.exercise_scope import ordinal_value


class FirewallContextComposer(IContextComposer):
    """
    Formats the retrieved search results into a clean Markdown context,
    applying the 'Context Firewall' to hide solutions when not requested.
    """

    FORBIDDEN_KEYS: ClassVar[set[str]] = {
        "solution",
        "answer",
        "marking_scheme",
        "correction",
        "key",
        "answer_key",
        "solution_md",
    }
    SOLUTION_NODE_TYPES: ClassVar[set[str]] = {
        "solution",
        "answer",
        "marking_scheme",
        "key",
        "correction",
    }

    # Aggressive patterns to detect solution blocks embedded in content
    SOLUTION_PATTERNS: ClassVar[list[str]] = [
        r"(?i)\n(#{1,3}\s*(Solution|Answer|Correction|Marking Scheme|Key|الحل|الإجابة|الجواب|تصحيح|مفتاح))[\s\S]+?(?=\n\s*\*{0,2}(#{1,3}|Exercise|Question|السؤال|تمرين|التمرين)|$)",
        r"(?i)\n(Solution|Answer|الحل|الجواب):\s*[\s\S]+?(?=\n\s*\*{0,2}(#{1,3}|Exercise|Question|السؤال|تمرين|التمرين)|$)",
        r"(?is)\n\[(sol|solution):[^\]]+\][\s\S]+?(?=\n\s*\[(ex|exercise):|$)",
        r"(?i)\n\s*\*{0,2}حل\s+التمرين[\s\S]+?(?=\n\s*\*{0,2}(#{1,3}|Exercise|Question|السؤال|تمرين|التمرين)|$)",
    ]
    SOLUTION_CAPTURE_PATTERNS: ClassVar[list[str]] = [
        r"(?is)\n\[(sol|solution):[^\]]+\][\s\S]+?(?=\n\s*\[(ex|exercise):|$)",
        r"(?is)\n\s*\*{0,2}حل\s+التمرين[\s\S]+?(?=\n\s*\*{0,2}(#{1,3}|Exercise|Question|السؤال|تمرين|التمرين)|$)",
    ]
    GRADING_PATTERNS: ClassVar[list[str]] = [
        r"(?is)\n\[(grading|marking|rubric):[^\]]+\][\s\S]+?(?=\n\s*\[(ex|exercise|sol|solution):|$)",
        r"(?i)\n(#{1,3}\s*(سلم التنقيط|سلم التصحيح|marking scheme|grading scheme))[\s\S]+?(?=\n\s*\*{0,2}(#{1,3}|Exercise|Question|السؤال|تمرين|التمرين)|$)",
    ]

    def compose(
        self,
        search_results: list[dict[str, object]],
        intent: WriterIntent,
        user_message: str,
    ) -> str:
        if not search_results:
            return ""

        allow_solution, allow_grading, show_hidden_marker = self._derive_intent_flags(intent)
        context_text = ""
        for item in search_results:
            node_type = str(item.get("type", "")).lower()
            if not allow_solution and node_type in self.SOLUTION_NODE_TYPES:
                continue

            full_content = str(item.get("content", ""))
            requested_content = self._extract_requested_segment(full_content, user_message)
            sanitized_content = self._sanitize_content(
                requested_content, show_hidden_marker=show_hidden_marker
            )

            solution_display = self._compose_solution_display(
                item=item,
                content=full_content,
                allow_solution=allow_solution,
                allow_grading=allow_grading,
                show_solution_banner=show_hidden_marker,
            )
            context_text += self._render_context_entry(
                sanitized_content=sanitized_content, solution_display=solution_display
            )

        return context_text

    def _derive_intent_flags(self, intent: WriterIntent) -> tuple[bool, bool, bool]:
        """يشتق أعلام التحكم الرئيسية من نية المستخدم."""
        allow_solution = intent in (WriterIntent.SOLUTION_REQUEST, WriterIntent.GRADING_REQUEST)
        allow_grading = intent == WriterIntent.GRADING_REQUEST
        show_hidden_marker = intent == WriterIntent.GENERAL_INQUIRY
        return allow_solution, allow_grading, show_hidden_marker

    def _sanitize_content(self, content: str, show_hidden_marker: bool) -> str:
        """
        إزالة مقاطع الحلول المضمّنة داخل المحتوى باستخدام التعبيرات النمطية.
        """
        sanitized = content
        replacement = (
            "\n\n🔒 [HIDDEN: Potential Solution Segment Redacted from Content]\n"
            if show_hidden_marker
            else "\n\n"
        )

        for pattern in self.SOLUTION_PATTERNS:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.DOTALL)

        return sanitized

    def _compose_solution_display(
        self,
        item: dict[str, object],
        content: str,
        allow_solution: bool,
        allow_grading: bool,
        show_solution_banner: bool,
    ) -> str:
        """يبني عرض الحل بناءً على نية المستخدم."""
        if not allow_solution:
            return (
                "🔒 [SOLUTION HIDDEN: Student has NOT requested the solution yet.]"
                if show_solution_banner
                else ""
            )
        solution_data: dict[str, str] = {}
        for key in self.FORBIDDEN_KEYS:
            if val := item.get(key):
                solution_data[key] = str(val)
        if not solution_data:
            embedded_solutions = self._extract_solution_blocks(content)
            if embedded_solutions:
                solution_data["embedded_solution"] = "\n\n".join(embedded_solutions)
        grading_block = ""
        if allow_grading:
            grading_blocks = self._extract_grading_blocks(content)
            if grading_blocks:
                grading_block = "\n\n".join(grading_blocks)
        if solution_data:
            combined_sols = "\n\n".join(
                [f"**{k.title()}**:\n{v}" for k, v in solution_data.items()]
            )
            grading_section = (
                f"\n\n### سلم التنقيط (Marking Scheme):\n{grading_block}" if grading_block else ""
            )
            return f"### الحل النموذجي (Official Solution):\n{combined_sols}{grading_section}"
        if grading_block:
            return f"### سلم التنقيط (Marking Scheme):\n{grading_block}"
        return "⚠️ [No official solution record found in database]"

    def _render_context_entry(self, sanitized_content: str, solution_display: str) -> str:
        """يعيد تمثيل نصي موحّد لكل سياق تمرين."""
        solution_section = f"\n\n{solution_display}" if solution_display else ""
        return f"**Exercise Context:**\n{sanitized_content}{solution_section}\n\n---\n"

    def _extract_solution_blocks(self, content: str) -> list[str]:
        """
        استخراج كتل الحلول المضمّنة داخل المحتوى عندما لا تتوفر حقول حل صريحة.
        """
        extracted: list[str] = []
        for pattern in self.SOLUTION_CAPTURE_PATTERNS:
            for match in re.finditer(pattern, content, flags=re.DOTALL):
                block = match.group(0).strip()
                if block and block not in extracted:
                    extracted.append(block)

        return extracted

    def _extract_grading_blocks(self, content: str) -> list[str]:
        """
        استخراج كتل سلم التنقيط المضمّنة داخل المحتوى.
        """
        extracted: list[str] = []
        for pattern in self.GRADING_PATTERNS:
            for match in re.finditer(pattern, content, flags=re.DOTALL):
                block = match.group(0).strip()
                if block and block not in extracted:
                    extracted.append(block)
        return extracted

    def _extract_requested_segment(self, content: str, user_message: str) -> str:
        """
        يقتطع جزءاً محدداً من التمرين عند طلب سؤال بعينه.
        """
        requested_index = _extract_requested_index(user_message)
        if requested_index is None:
            return content

        extracted = _extract_section_by_index(content, requested_index)
        return extracted or content


def _extract_requested_index(user_message: str) -> int | None:
    """
    استخراج رقم السؤال المطلوب من رسالة المستخدم إن وُجد.
    """
    pattern = re.compile(
        r"(السؤال|التمرين|question|exercise)\s*(?:رقم\s*)?"
        r"(\d+|[٠-٩]+|الأول|أول|اول|الثاني|ثاني|الثالث|ثالث|الرابع|رابع|الخامس|خامس|"
        r"السادس|سادس|السابع|سابع|الثامن|ثامن|التاسع|تاسع|العاشر|عاشر|"
        r"first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)",
        re.IGNORECASE,
    )
    match = pattern.search(user_message)
    if not match:
        return None
    return _normalize_index_token(match.group(2))


def _extract_section_by_index(content: str, index: int) -> str | None:
    """
    استخراج مقطع محدد من المحتوى اعتماداً على رقم السؤال.
    """
    heading_pattern = re.compile(
        r"(?im)^(?:#{1,6}\s*)?(السؤال|التمرين|question|exercise)\s*(?:رقم\s*)?"
        r"(\d+|[٠-٩]+|الأول|أول|اول|الثاني|ثاني|الثالث|ثالث|الرابع|رابع|الخامس|خامس|"
        r"السادس|سادس|السابع|سابع|الثامن|ثامن|التاسع|تاسع|العاشر|عاشر|"
        r"first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\b"
    )

    matches = list(heading_pattern.finditer(content))
    if not matches:
        return None

    sections: list[tuple[int, int, int]] = []
    for idx, match in enumerate(matches, start=1):
        start = match.start()
        end = matches[idx].start() if idx < len(matches) else len(content)
        token_value = _normalize_index_token(match.group(2)) or idx
        sections.append((token_value, start, end))

    for token_value, start, end in sections:
        if token_value == index:
            return content[start:end].strip()

    if index <= len(sections):
        _, start, end = sections[index - 1]
        return content[start:end].strip()
    return None


def _normalize_index_token(token: str | None) -> int | None:
    """
    تحويل تمثيل الرقم (عربي/إنجليزي) إلى قيمة عددية.
    """
    if not token:
        return None
    normalized = token.strip().lower()

    arabic_digits = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
    numeric_candidate = normalized.translate(arabic_digits)
    if numeric_candidate.isdigit():
        return int(numeric_candidate)

    # D-206 (L6): الترتيبيّات من المصدر القانوني — كانت هنا خريطةٌ محلّية من ٢٠ صيغة.
    # المفارقة التي تُلخّص ISS-144: هذه الخريطة **كانت تعرف** النكرة («اول» · «ثاني»)
    # بينما جهلتها خريطةُ `exercise_retrieval` — كاشفان لنيّةٍ واحدة، كلٌّ يعرف ما
    # يجهله الآخر، والطالب يدفع الثمن حين يقع طلبُه على الكاشف الأعمى.
    arabic_ordinal = ordinal_value(normalized)
    if arabic_ordinal is not None:
        return arabic_ordinal

    english_ordinals = {
        "first": 1,
        "second": 2,
        "third": 3,
        "fourth": 4,
        "fifth": 5,
        "sixth": 6,
        "seventh": 7,
        "eighth": 8,
        "ninth": 9,
        "tenth": 10,
    }
    return english_ordinals.get(normalized)
