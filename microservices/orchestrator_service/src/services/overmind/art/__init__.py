# app/services/overmind/art/__init__.py
"""
🎨 CS73: Code, Data, and Art Module
====================================

هذا الوحدة تطبق مبادئ Harvard CS73 على نظام Overmind.
تدمج بين البرمجة وفن التصميم، وتستكشف كيفية استخدام
الشيفرة والبيانات لإنشاء تصورات فنية وإبداعية.

CS73 Integration:
- Code as Art: تحويل البيانات البرمجية إلى تمثيلات فنية
- Data Visualization: تصور البيانات بطريقة جمالية وإبداعية
- Aesthetic Computing: الحوسبة الجمالية والتصميم التفاعلي
- Generative Art: الفن التوليدي باستخدام الخوارزميات
"""

from microservices.orchestrator_service.src.services.overmind.art.generators import (
    CodePatternArtist,
    MetricsArtist,
    NetworkArtist,
)
from microservices.orchestrator_service.src.services.overmind.art.styles import (
    ArtStyle,
    ColorPalette,
    VisualTheme,
)
from microservices.orchestrator_service.src.services.overmind.art.visualizer import (
    CodeArtVisualizer,
    DataArtGenerator,
    MissionFlowArtist,
)

__all__ = [
    # Styles
    "ArtStyle",
    # Visualizers
    "CodeArtVisualizer",
    # Generators
    "CodePatternArtist",
    "ColorPalette",
    "DataArtGenerator",
    "MetricsArtist",
    "MissionFlowArtist",
    "NetworkArtist",
    "VisualTheme",
]
