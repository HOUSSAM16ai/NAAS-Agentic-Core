import re

from microservices.orchestrator_service.src.services.overmind.domain.writer_intent import (
    WriterIntent,
)


class RegexIntentDetector:
    """
    Analyzes user input to determine if they are explicitly requesting
    the solution (triggering Dual Mode) or just asking a general question.
    """

    # Regex patterns for high-precision detection
    REQUEST_INDICATORS = r"(أريد|بدي|ابغى|عطيني|اعطني|هات|وريني|show|give|want|provide|display|please|plz|من فضلك|لو سمحت)"
    TARGET_NOUNS = r"(حل|إجابة|اجابة|جواب|صحح|تصحيح|solution|answer|result|correction)"
    GRADING_KEYWORDS = (
        r"(سلم\s*التنقيط|سلم\s*التصحيح|شبكة\s*التنقيط|marking\s*scheme|grading\s*scheme|grading)"
    )
    # Updated negation to include "without" variants
    NEGATION_PATTERN = r"(don't|do not|not|no|never|without|sans|لا|ما|لم|لن|ليس|بدون|بلاش|من غير).{0,20}(want|need|give|show|solution|answer|أريد|بدي|تعطيني|عطيني|هات|حل|إجابة)"
    DIAGNOSIS_KEYWORDS = (
        r"(diagnose|quiz|test|exam|assessment|شخصني|شخص|تشخيص|ختبرني|إختبار|اختبار|"
        r"قيم|تقييم|مراجعة|تشخيصي|تقييم مستواي|تشخيص مستواي)"
    )
    QUESTION_ONLY_KEYWORDS = (
        # Arabic patterns
        r"(أسئلة\s*فقط|فقط\s*أسئلة|فقط\s*التمرين|التمرين\s*فقط|نص\s*التمرين\s*فقط|"
        r"بدون\s*إجابة|بدون\s*اجابة|بدون\s*حلول|بدون\s*حل|لا\s*أريد\s*الحل|"
        r"ما\s*أريد\s*الحل|لا\s*تعطيني\s*الحل|لا\s*أحتاج\s*الحل|"
        r"أعطني\s*التمرين\s*بدون|أعطني\s*الأسئلة\s*بدون|اعطني\s*فقط|"
        r"اعطني\s*التمرين\s*فقط|اعطني\s*الاسئلة\s*فقط|"
        # English patterns
        r"without\s*answers|no\s*answers|without\s*solution|no\s*solution|"
        r"questions\s*only|just\s*questions|just\s*the\s*exercise|exercise\s*only|"
        r"give\s*me\s*only\s*the\s*exercise|don't\s*show\s*solution)"
    )

    def analyze(self, user_message: str) -> WriterIntent:
        msg_lower = user_message.lower()

        # Check for Diagnosis first
        is_diagnosis = bool(re.search(self.DIAGNOSIS_KEYWORDS, msg_lower))
        if is_diagnosis:
            return WriterIntent.DIAGNOSIS_REQUEST
        is_questions_only = bool(re.search(self.QUESTION_ONLY_KEYWORDS, msg_lower))
        if is_questions_only:
            return WriterIntent.QUESTION_ONLY_REQUEST
        is_grading_request = bool(re.search(self.GRADING_KEYWORDS, msg_lower))
        if is_grading_request:
            return WriterIntent.GRADING_REQUEST

        has_noun = bool(re.search(self.TARGET_NOUNS, msg_lower))
        is_request = bool(re.search(self.REQUEST_INDICATORS, msg_lower))
        is_question = "?" in msg_lower or "؟" in msg_lower
        is_short = len(msg_lower.split()) <= 3
        has_negation = bool(re.search(self.NEGATION_PATTERN, msg_lower))

        # Decision Matrix
        if has_noun and not has_negation and (is_request or is_question or is_short):
            return WriterIntent.SOLUTION_REQUEST

        return WriterIntent.GENERAL_INQUIRY
