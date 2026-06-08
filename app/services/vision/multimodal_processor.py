"""
معالج الوسائط المتعددة (MultiModal Processor).
==============================================

يفهم الصور والرسوم والمعادلات.
"""

import base64
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from app.core.ai_gateway import AIClient

logger = logging.getLogger(__name__)

# نموذج رؤية مجاني فقط (لا نماذج مدفوعة). gemma-4-26b مجاني ويدعم الصور ومُتحقَّق
# حياً في المشروع (GATEWAY_FALLBACK_2 — عربي + LaTeX). قابل للتجاوز عبر متغير البيئة.
_VISION_MODEL = os.getenv("OPENROUTER_VISION_MODEL", "google/gemma-4-26b-a4b-it:free")


@dataclass
class ImageAnalysis:
    """نتيجة تحليل صورة."""

    text_content: str  # النص المستخرج
    equations: list[str]  # المعادلات المكتشفة
    diagrams: list[str]  # وصف الرسوم
    exercise_type: str  # نوع التمرين
    subject: str  # المادة
    confidence: float  # مستوى الثقة


class MultiModalProcessor:
    """
    يعالج الوسائط المتعددة (صور، رسوم، إلخ).

    المميزات:
    - استخراج النص العربي من الصور (OCR)
    - كشف المعادلات الرياضية
    - فهم الرسوم البيانية
    - تحديد نوع التمرين
    """

    ANALYSIS_PROMPT = """
أنت خبير في تحليل الصور التعليمية. حلل الصورة المرفقة واستخرج:

1. **النص**: كل النص الموجود (عربي/إنجليزي)
2. **المعادلات**: كل المعادلات الرياضية بتنسيق LaTeX
3. **الرسوم**: وصف أي رسوم بيانية أو أشكال
4. **نوع التمرين**: (احتمالات، أعداد مركبة، دوال، متتاليات، إلخ)
5. **المادة**: (رياضيات، فيزياء، إلخ)

أجب بتنسيق JSON:
{
    "text_content": "...",
    "equations": ["...", "..."],
    "diagrams": ["وصف الرسم 1", "..."],
    "exercise_type": "...",
    "subject": "...",
    "confidence": 0.0-1.0
}
"""

    def __init__(self, ai_client: AIClient | None = None) -> None:
        self.ai_client = ai_client

    async def analyze_image(
        self,
        image_path: str,
    ) -> ImageAnalysis:
        """
        يحلل صورة ويستخرج المحتوى التعليمي.
        """
        if not self.ai_client:
            logger.warning("AI client not available for image analysis")
            return self._fallback_analysis()

        # قراءة وتشفير الصورة
        image_data = self._encode_image(image_path)

        if not image_data:
            return self._fallback_analysis()

        try:
            # استدعاء Vision API
            response = await self.ai_client.generate(
                model=_VISION_MODEL,  # نموذج رؤية مجاني فقط (google/gemma-4-26b-a4b-it:free)
                messages=[
                    {"role": "system", "content": self.ANALYSIS_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "حلل هذه الصورة:"},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{image_data}"},
                            },
                        ],
                    },
                ],
                response_format={"type": "json_object"},
            )

            import json

            result = json.loads(response.choices[0].message.content)

            return ImageAnalysis(
                text_content=result.get("text_content", ""),
                equations=result.get("equations", []),
                diagrams=result.get("diagrams", []),
                exercise_type=result.get("exercise_type", "غير محدد"),
                subject=result.get("subject", "رياضيات"),
                confidence=result.get("confidence", 0.5),
            )

        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            return self._fallback_analysis()

    def _encode_image(self, image_path: str) -> str | None:
        """يشفر الصورة لـ base64."""

        try:
            path = Path(image_path)
            if not path.exists():
                logger.error(f"Image not found: {image_path}")
                return None

            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")

        except Exception as e:
            logger.error(f"Error encoding image: {e}")
            return None

    def _fallback_analysis(self) -> ImageAnalysis:
        """يعيد تحليل افتراضي عند الفشل."""

        return ImageAnalysis(
            text_content="",
            equations=[],
            diagrams=[],
            exercise_type="غير محدد",
            subject="غير محدد",
            confidence=0.0,
        )

    async def extract_exercise_from_image(
        self,
        image_path: str,
    ) -> dict[str, object]:
        """
        يستخرج تمرين كامل من صورة.
        """
        analysis = await self.analyze_image(image_path)

        return {
            "success": analysis.confidence > 0.5,
            "text": analysis.text_content,
            "equations": analysis.equations,
            "type": analysis.exercise_type,
            "subject": analysis.subject,
            "formatted": self._format_exercise(analysis),
        }

    def _format_exercise(self, analysis: ImageAnalysis) -> str:
        """يصيغ التمرين بشكل قابل للقراءة."""

        parts = []

        if analysis.text_content:
            parts.append(analysis.text_content)

        if analysis.equations:
            parts.append("\n**المعادلات:**")
            for eq in analysis.equations:
                parts.append(f"- ${eq}$")

        if analysis.diagrams:
            parts.append("\n**الرسوم:**")
            for diagram in analysis.diagrams:
                parts.append(f"- {diagram}")

        return "\n".join(parts)


# Singleton
_processor: MultiModalProcessor | None = None


def get_multimodal_processor(ai_client: AIClient | None = None) -> MultiModalProcessor:
    """يحصل على معالج الوسائط."""
    global _processor
    if _processor is None:
        _processor = MultiModalProcessor(ai_client)
    return _processor
