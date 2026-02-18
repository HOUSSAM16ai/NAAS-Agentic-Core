"""
Parsing and Text Processing Logic for Retrieval Tool.
Pure functional core.
"""

import re

from .constants import (
    _ARABIC_DIGIT_MAP,
    _ARABIC_LETTER_MAP,
    _BRANCH_SYNONYMS,
    _EXAM_CARD_MARKERS,
    _EXAM_REF_SYNONYMS,
    _EXERCISE_MARKERS_AR,
    _EXERCISE_MARKERS_EN_PATTERN,
    _EXERCISE_NUMBER_PATTERN,
    _EXERCISE_ORDINALS,
    _SECTION_STOP_MARKERS_AR_PATTERN,
    _SECTION_STOP_MARKERS_EN_PATTERN,
    _SOLUTION_MARKERS_AR_PATTERN,
    _SOLUTION_MARKERS_EN_PATTERN,
    _SOLUTION_NEGATION_PATTERN,
    _SUBJECT_SYNONYMS,
    _TOPIC_MAP,
)


def normalize_text(text: str) -> str:
    """
    يطبع النص عبر تحويله إلى أحرف صغيرة واستبدال الأرقام العربية بأرقام لاتينية.
    """
    normalized = text.lower().translate(_ARABIC_DIGIT_MAP)
    return " ".join(normalized.split())


def normalize_semantic_text(text: str) -> str:
    """
    يطبع النص دلاليًا عبر توحيد الحروف العربية وإزالة الفروقات الشائعة في الكتابة.
    """
    normalized = normalize_text(text)
    return normalized.translate(_ARABIC_LETTER_MAP)


def is_specific_request(query: str) -> bool:
    """يتحقق مما إذا كان الطلب يشير إلى تمرين أو موضوع محدد."""
    query_lower = normalize_semantic_text(query)

    # 1. Check for explicit exercise keywords/numbers
    if detect_exercise_number(query_lower) is not None:
        return True
    if has_exercise_marker(query_lower):
        return True

    # 2. Check for Topic Keywords (If user asks for 'Probability', they want THAT, not the whole exam)
    for keywords in _TOPIC_MAP.values():
        normalized_keywords = [normalize_semantic_text(keyword) for keyword in keywords]
        if any(k in query_lower for k in normalized_keywords):
            return True

    return False


def is_solution_request(query: str) -> bool:
    """يتحقق مما إذا كان المستخدم يطلب الحل بشكل صريح."""
    normalized = normalize_semantic_text(query)

    # Check for explicit negation FIRST (e.g. "without solution")
    if _SOLUTION_NEGATION_PATTERN.search(normalized):
        return False

    if _SOLUTION_MARKERS_AR_PATTERN.search(normalized):
        return True
    return _SOLUTION_MARKERS_EN_PATTERN.search(normalized) is not None


def extract_specific_exercise(content: str, query: str) -> str | None:
    """
    يستخرج تمرينًا محددًا من محتوى Markdown مع الحفاظ على رأس الملف (العنوان وبطاقة الامتحان).
    يدعم الاستخراج حسب رقم التمرين أو حسب الموضوع.
    """
    query_lower = normalize_semantic_text(query)

    # NEW LOGIC: Check for solution request
    if is_solution_request(query):
        sol_text = extract_solution_block(content)
        if not sol_text:
            return None
        # Prepend header for context
        lines = content.split("\n")
        header_text = extract_header_block(lines)
        if header_text:
            return f"{header_text}\n\n---\n\n{sol_text}"
        return sol_text

    target_exercise_num = detect_exercise_number(query_lower)
    target_topics = collect_target_topics(query_lower, target_exercise_num)

    if target_exercise_num is None and not target_topics:
        return None

    lines = content.split("\n")
    header_text = extract_header_block(lines)
    exercise_text = extract_exercise_block(lines, target_exercise_num, target_topics)

    if not exercise_text:
        return None
    if header_text:
        return f"{header_text}\n\n---\n\n{exercise_text}"
    return exercise_text


def extract_solution_block(content: str) -> str | None:
    """
    يستخرج قسم الحل من المحتوى.
    """
    lines = content.split("\n")
    extracted_lines = []
    capture = False
    header_pattern = re.compile(r"^(#{1,3})\s*(.*)")
    capture_level = 0

    for line in lines:
        match = header_pattern.match(line)
        if match:
            level = len(match.group(1))
            header_text = match.group(2)

            if is_solution_header(header_text):
                capture = True
                capture_level = level
                extracted_lines.append(line)
                continue

            # Stop capturing if we hit a new header of same or higher level
            if capture and level <= capture_level:
                capture = False

        if capture:
            extracted_lines.append(line)

    if not extracted_lines:
        return None
    return "\n".join(extracted_lines).strip()


def remove_solution_section(content: str) -> str:
    """
    يعيد المحتوى بعد حذف قسم الحل (إذا وجد).
    مفيد عند طلب 'الأسئلة فقط' من ملف كامل.
    """
    lines = content.split("\n")
    kept_lines = []
    header_pattern = re.compile(r"^(#{1,3})\s*(.*)")

    for line in lines:
        match = header_pattern.match(line)
        if match:
            header_text = match.group(2)
            # If we hit a solution header, stop (or skip until next section? Usually solution is at end)
            # For safety, we assume solution is the last major section or we just truncate there.
            if is_solution_header(header_text):
                break

        kept_lines.append(line)

    return "\n".join(kept_lines).strip()


def detect_exercise_number(query_lower: str) -> int | None:
    """
    يحدد رقم التمرين المطلوب من نص البحث إن وجد.
    """
    query_normalized = normalize_semantic_text(query_lower)
    direct_match = _EXERCISE_NUMBER_PATTERN.search(query_normalized)
    if direct_match:
        try:
            return int(direct_match.group(1))
        except ValueError:
            return None

    for number, ordinals in _EXERCISE_ORDINALS.items():
        for ordinal in ordinals:
            if f"التمرين {ordinal}" in query_normalized:
                return number

    return None


def collect_target_topics(query_lower: str, exercise_number: int | None) -> list[str]:
    """
    يجمع كلمات الموضوع ذات الصلة عندما لا يوجد رقم تمرين محدد.
    """
    if exercise_number is not None:
        return []

    topics: list[str] = []
    for keywords in _TOPIC_MAP.values():
        normalized_keywords = [normalize_semantic_text(keyword) for keyword in keywords]
        if any(keyword in query_lower for keyword in normalized_keywords):
            topics.extend(normalized_keywords)
    return list(dict.fromkeys(topics))


def extract_header_block(lines: list[str]) -> str:
    """
    يستخرج عنوان الملف وبطاقة الامتحان من القسم العلوي للمستند.
    """
    header_lines: list[str] = []
    capture_card = False

    for line in lines:
        stripped = line.strip()
        stripped_normalized = normalize_semantic_text(stripped)

        if stripped.startswith("#") and has_exercise_marker(stripped_normalized):
            break

        if line.startswith("# "):
            header_lines.append(line)
            continue

        if any(
            normalize_semantic_text(marker) in stripped_normalized for marker in _EXAM_CARD_MARKERS
        ):
            header_lines.append(line)
            capture_card = True
            continue

        if capture_card:
            if line.startswith("## ") or line.startswith("# ") or line.startswith("---"):
                capture_card = False
            else:
                header_lines.append(line)

    return "\n".join(header_lines).strip()


def extract_exercise_block(
    lines: list[str],
    target_exercise_num: int | None,
    target_topics: list[str],
) -> str | None:
    """
    يستخرج كتلة التمرين المطلوبة بالاعتماد على العناوين والأرقام أو الموضوعات.
    """
    extracted_lines: list[str] = []
    capture = False
    # FIXED: Support H1 (#) headers
    header_pattern = re.compile(r"^(#{1,3})\s*(.*)")
    number_patterns = build_number_patterns(target_exercise_num)
    capture_level = 0

    for line in lines:
        match = header_pattern.match(line)
        if match:
            level = len(match.group(1))
            header_text_match = match.group(2)
            header_text_normalized = normalize_semantic_text(header_text_match)
            is_match = is_exercise_header_match(
                header_text_normalized,
                target_exercise_num,
                number_patterns,
                target_topics,
            )

            if is_match:
                capture = True
                capture_level = level
                extracted_lines.append(line)
                continue

            if capture:
                # 1. Hierarchy Stop: If new header is same level or higher (e.g. H1 -> H1)
                if level <= capture_level:
                    capture = False

                # 2. Explicit Stop Markers (Solution)
                # Solution usually terminates the exercise block
                if is_solution_header(header_text_match):
                    capture = False

        if capture:
            extracted_lines.append(line)

    if not extracted_lines:
        return None
    return "\n".join(extracted_lines).strip()


def build_number_patterns(target_exercise_num: int | None) -> list[str]:
    """
    يبني قائمة أنماط مطابقة لرقم التمرين باللغة العربية والإنجليزية.
    """
    if not target_exercise_num:
        return []

    ordinals = _EXERCISE_ORDINALS.get(target_exercise_num, [])

    patterns = [
        normalize_semantic_text(f"التمرين {target_exercise_num}"),
        normalize_semantic_text(f"Exercise {target_exercise_num}"),
        normalize_semantic_text(f"التمرين ({target_exercise_num})"),
        normalize_semantic_text(f"Exercise ({target_exercise_num})"),
    ]
    patterns.extend(normalize_semantic_text(f"التمرين {ordinal}") for ordinal in ordinals)
    return list(dict.fromkeys(patterns))


def is_exercise_header_match(
    header_text: str,
    target_exercise_num: int | None,
    number_patterns: list[str],
    target_topics: list[str],
) -> bool:
    """
    يتحقق مما إذا كان العنوان يمثل التمرين المطلوب حسب الرقم أو الموضوع.
    """
    header_normalized = normalize_semantic_text(header_text)
    if target_exercise_num:
        # 1. Check explicit text patterns (Exercise 1, etc.)
        if any(pattern in header_normalized for pattern in number_patterns):
            return True

        # 2. Check for "N." or "N)" style headers
        # Matches: "1.", "1)", "1-", "1 " at the start of the line
        start_number_pattern = re.compile(rf"^{target_exercise_num}\s*[.)-]")
        if start_number_pattern.match(header_normalized):
            return True

    if target_topics and has_exercise_marker(header_normalized):
        return any(topic in header_normalized for topic in target_topics)

    return False


def is_solution_header(header_text: str) -> bool:
    """
    يتحقق مما إذا كان العنوان يمثل قسم الحل.
    """
    normalized = normalize_semantic_text(header_text)
    if _SOLUTION_MARKERS_AR_PATTERN.search(normalized):
        return True
    return _SOLUTION_MARKERS_EN_PATTERN.search(normalized) is not None


def is_new_section_header(header_text: str) -> bool:
    """
    يحدد ما إذا كان العنوان يمثل قسمًا جديدًا يجب إنهاء الالتقاط عنده.
    (Deprecated logic kept for reference, replaced by hierarchy logic in extract_exercise_block)
    """
    header_normalized = normalize_semantic_text(header_text)
    return has_section_stop_marker(header_normalized)


def expand_query_semantics(
    query: str,
    year: str | None,
    subject: str | None,
    branch: str | None,
    exam_ref: str | None,
) -> str:
    """
    يوسّع الاستعلام بإضافة مرادفات وتهيئة دلالية لزيادة فرص المطابقة.
    """
    normalized_query = normalize_semantic_text(query)
    terms: list[str] = [normalized_query]
    terms.extend(expand_topic_keywords(normalized_query))
    terms.extend(expand_metadata_keywords(year, subject, branch, exam_ref))
    return " ".join(unique_nonempty_terms(terms))


def expand_topic_keywords(query_normalized: str) -> list[str]:
    """
    يضيف كلمات موضوعية مترادفة عند كشفها في الاستعلام.
    """
    topics: list[str] = []
    for keywords in _TOPIC_MAP.values():
        normalized_keywords = [normalize_semantic_text(keyword) for keyword in keywords]
        if any(keyword in query_normalized for keyword in normalized_keywords):
            topics.extend(normalized_keywords)
    return topics


def expand_metadata_keywords(
    year: str | None,
    subject: str | None,
    branch: str | None,
    exam_ref: str | None,
) -> list[str]:
    """
    يضيف مرادفات البيانات الوصفية لضمان تطابق صيغ متعددة لنفس المعنى.
    """
    terms: list[str] = []
    for value in (year, subject, branch, exam_ref):
        if value:
            terms.append(normalize_semantic_text(value))

    if subject:
        subject_key = normalize_semantic_text(subject)
        terms.extend(lookup_semantic_synonyms(_SUBJECT_SYNONYMS, subject_key))

    if branch:
        branch_key = normalize_semantic_text(branch)
        terms.extend(lookup_semantic_synonyms(_BRANCH_SYNONYMS, branch_key))

    if exam_ref:
        exam_key = normalize_semantic_text(exam_ref)
        terms.extend(lookup_semantic_synonyms(_EXAM_REF_SYNONYMS, exam_key))

    return [normalize_semantic_text(term) for term in terms]


def unique_nonempty_terms(terms: list[str]) -> list[str]:
    """
    ينقّي قائمة المصطلحات بحذف التكرارات والقيم الفارغة.
    """
    return [term for term in dict.fromkeys(terms) if term]


def lookup_semantic_synonyms(mapping: dict[str, list[str]], key: str) -> list[str]:
    """
    يعيد مرادفات مطبّعة وفق مفتاح مطبّع، مع تطبيع مفاتيح القاموس عند الحاجة.
    """
    direct = mapping.get(key)
    if direct:
        return direct
    normalized_mapping = {normalize_semantic_text(k): v for k, v in mapping.items()}
    return normalized_mapping.get(key, [])


def has_exercise_marker(text_normalized: str) -> bool:
    """
    يتحقق مما إذا كان النص يحتوي على مؤشرات تدل على وجود تمرين.
    """
    if any(marker in text_normalized for marker in _EXERCISE_MARKERS_AR):
        return True
    return _EXERCISE_MARKERS_EN_PATTERN.search(text_normalized) is not None


def has_section_stop_marker(text_normalized: str) -> bool:
    """
    يتحقق مما إذا كان النص يمثل عنوان قسم جديد يتطلب إيقاف الالتقاط.
    """
    if _SECTION_STOP_MARKERS_AR_PATTERN.search(text_normalized):
        return True
    return _SECTION_STOP_MARKERS_EN_PATTERN.search(text_normalized) is not None


def get_core_content(content: str) -> str:
    """Helper to strip the file header if present (separated by ---)."""
    if "\n\n---\n\n" in content:
        return content.rsplit("\n\n---\n\n", maxsplit=1)[-1]
    return content


def deduplicate_contents(contents: list[str]) -> list[str]:
    """
    Deduplicates content by removing items that are substrings (or fuzzy matches) of longer items.
    Useful when we retrieve both a full document and a chunk of it.
    """
    if not contents:
        return []

    # Sort by length descending (longest first)
    sorted_contents = sorted(contents, key=len, reverse=True)

    unique_contents = []
    for content in sorted_contents:
        # Check if this content is a substring/fuzzy match of any already kept content
        is_duplicate = False
        content_core = get_core_content(content)

        for kept in unique_contents:
            kept_core = get_core_content(kept)

            # 1. Strict substring check (fastest)
            if content_core in kept_core:
                is_duplicate = True
                break

            # 2. Fuzzy inclusion check via Token Overlap (Robust against formatting/headers)
            try:
                # Simple tokenization: split by whitespace
                tokens_short = set(content_core.split())
                tokens_long = set(kept_core.split())

                if not tokens_short:
                    is_duplicate = True  # Empty content considered duplicate
                else:
                    intersection = tokens_short.intersection(tokens_long)
                    overlap = len(intersection) / len(tokens_short)

                    # Threshold: if > 90% of tokens in the short content are present in the long content
                    if overlap > 0.9:
                        is_duplicate = True
            except Exception:
                # Fallback to difflib if tokenization fails
                pass

            if is_duplicate:
                break

        if not is_duplicate:
            unique_contents.append(content)

    return unique_contents
