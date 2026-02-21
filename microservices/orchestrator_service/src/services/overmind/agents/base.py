"""
Base classes and constants for Agents.
"""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel

FORMAL_ARABIC_STYLE_PROMPT = """
[المعايير الهندسية للصياغة - Engineering Specification Style]
يجب أن تكون إجابتك نصاً عربياً ذا طابع "مواصفة هندسية" (Specification-Grade)، يتسم بالخصائص التالية:

1. **الصرامة التعريفية (Definitional Rigor):**
   - عرّف المفاهيم كأنك تكتب بنداً في مواصفة (ISO/IEC).
   - استخدم مصطلحات دقيقة ومحايدة (لا "رائع"، لا "ممتاز"، لا "سحري").
   - اذكر القيود (Constraints) والشروط (Pre-conditions/Post-conditions) بوضوح.

2. **المنهجية الهيكلية (Structural Methodology):**
   - لا تسرد خطوات عشوائية؛ ابنِ الإجابة كـ "خوارزمية" أو "بروتوكول".
   - استخدم الترقيم (1, 2, 3) أو البنود (Bullets) لتمثيل التسلسل المنطقي.
   - وضّح مدخلات ومخرجات كل مرحلة.

3. **اللغة الأكاديمية (Formal Academic Arabic):**
   - جمل فعلية محكمة، مبتدأ وخبر واضحان.
   - تجنب الزخرفة البلاغية (لا استعارات، لا تشبيهات جمالية).
   - استخدم المصطلحات الإنجليزية بين قوسين عند الضرورة القصوى للتدقيق التقني (مثل: "قابلية التحقق (Verifiability)").

4. **التركيز على التحقق (Verifiability Focus):**
   - لا تذكر مجرد "إنجاز"؛ اذكر "معيار القبول" (Acceptance Criteria).
   - اعتبر كل خطوة مشروطة باجتياز "بوابة جودة" (Quality Gate).

مثال على النبرة المطلوبة:
"يُعرَّف التخطيط في هذا السياق كعملية تحويل الأهداف المجردة إلى رسم مهام (Task Graph) قابل للتنفيذ والقياس، محكوماً بقيود الميزانية والمخاطر. يلتزم النظام ببروتوكول Plan-Execute-Verify لضمان عدم اعتماد أي مخرج دون دليل تحقق (Evidence)."
"""


class AgentResponse(BaseModel):
    success: bool
    data: object | None = None
    message: str | None = None


@runtime_checkable
class AgentProtocol(Protocol):
    async def process(self, input_data: object) -> AgentResponse: ...
