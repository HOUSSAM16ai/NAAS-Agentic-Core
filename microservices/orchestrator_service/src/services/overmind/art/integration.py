# app/services/overmind/art/integration.py
"""
🎨 CS73: Integration with Overmind System
==========================================

دمج الفن والتصور مع نظام Overmind الموجود.
يوفر واجهات سهلة للحصول على تصورات فنية من البيانات البرمجية.

CS73 Integration Strategy:
- Code Intelligence → Art: تحويل تحليل الكود إلى فن
- Mission Flow → Timeline: تصور سير المهام كخط زمني فني
- Metrics → Dashboard: لوحة مقاييس جمالية
- Dependencies → Network: شبكة التبعيات كفن
"""

from microservices.orchestrator_service.src.services.overmind.art.generators import (
    CodePatternArtist,
    MetricsArtist,
    NetworkArtist,
)
from microservices.orchestrator_service.src.services.overmind.art.styles import ArtStyle
from microservices.orchestrator_service.src.services.overmind.art.visualizer import (
    CodeArtVisualizer,
    DataArtGenerator,
    MissionFlowArtist,
)


class OvermindArtIntegration:
    """
    نقطة التكامل الرئيسية بين Overmind والفن.

    CS73: Bridge between code and art.
    """

    def __init__(self, default_style: ArtStyle = ArtStyle.MODERN):
        """
        تهيئة نظام الفن.

        Args:
            default_style: النمط الافتراضي للتصورات
        """
        self.default_style = default_style
        self.code_visualizer = CodeArtVisualizer(default_style)
        self.mission_artist = MissionFlowArtist(default_style)
        self.data_generator = DataArtGenerator(default_style)
        self.pattern_artist = CodePatternArtist(default_style)
        self.metrics_artist = MetricsArtist(default_style)
        self.network_artist = NetworkArtist(default_style)

    def visualize_code_intelligence(
        self, analysis_result: dict[str, object], style: ArtStyle | None = None
    ) -> dict[str, str]:
        """
        تحويل نتائج تحليل الكود إلى تصورات فنية.

        Args:
            analysis_result: نتائج من StructuralCodeIntelligence
            style: نمط فني اختياري

        Returns:
            dict: مجموعة من التصورات الفنية

        Example:
            >>> integration = OvermindArtIntegration()
            >>> art = integration.visualize_code_intelligence({
            ...     "avg_complexity": 5.2,
            ...     "max_complexity": 15,
            ...     "functions": 42,
            ...     "classes": 12
            ... })
            >>> logger.info(art["complexity_art"])  # SVG art
        """
        if style:
            self.code_visualizer = CodeArtVisualizer(style)

        visualizations = {}

        # 1. Complexity Landscape
        if "avg_complexity" in analysis_result:
            visualizations["complexity_art"] = self.code_visualizer.create_complexity_art(
                analysis_result, title="Code Complexity Landscape"
            )

        # 2. Metrics Dashboard
        metrics = {k: v for k, v in analysis_result.items() if isinstance(v, (int, float))}
        if metrics:
            visualizations["metrics_dashboard"] = self.code_visualizer.create_metrics_dashboard(
                metrics, title="Code Metrics Art"
            )

        # 3. Code Pattern Art
        visualizations["pattern_art"] = self.data_generator.generate_code_pattern(
            analysis_result, size=(600, 600)
        )

        # 4. Fractal Tree (based on complexity)
        complexity = int(analysis_result.get("avg_complexity", 5))
        fractal_depth = min(max(complexity // 2, 3), 7)
        visualizations["fractal_tree"] = self.pattern_artist.generate_fractal_tree(
            complexity=fractal_depth, seed=42
        )

        return visualizations

    def visualize_mission_journey(
        self, mission_data: dict[str, object], style: ArtStyle | None = None
    ) -> dict[str, str]:
        """
        تصور رحلة المهمة بشكل فني.

        Args:
            mission_data: بيانات المهمة (events, phases, etc.)
            style: نمط فني اختياري

        Returns:
            dict: تصورات فنية للمهمة

        Example:
            >>> integration = OvermindArtIntegration()
            >>> art = integration.visualize_mission_journey({
            ...     "events": [
            ...         {"name": "Start", "type": "start"},
            ...         {"name": "Planning", "type": "info"},
            ...         {"name": "Complete", "type": "success"}
            ...     ]
            ... })
        """
        if style:
            self.mission_artist = MissionFlowArtist(style)

        visualizations = {}

        # 1. Mission Timeline
        visualizations["timeline"] = self.mission_artist.create_mission_timeline(
            mission_data, title="Mission Journey"
        )

        # 2. Evolution Spiral
        iterations = len(mission_data.get("events", [])) * 10
        visualizations["evolution_spiral"] = self.pattern_artist.generate_spiral_code(
            iterations=max(iterations, 50), data_seed=mission_data.get("id", 42)
        )

        return visualizations

    def visualize_metrics(
        self,
        metrics: dict[str, float],
        style: ArtStyle | None = None,
        visualization_types: list[str] | None = None,
    ) -> dict[str, str]:
        """
        تصور المقاييس بطرق فنية متعددة.

        Args:
            metrics: المقاييس المراد تصورها
            style: نمط فني اختياري
            visualization_types: أنواع التصورات المطلوبة
                ["radial", "bar", "sculpture"]

        Returns:
            dict: تصورات فنية متعددة

        Example:
            >>> integration = OvermindArtIntegration()
            >>> art = integration.visualize_metrics({
            ...     "performance": 8.5,
            ...     "quality": 9.0,
            ...     "maintainability": 7.8
            ... })
        """
        if style:
            self.metrics_artist = MetricsArtist(style)
            self.data_generator = DataArtGenerator(style)

        if visualization_types is None:
            visualization_types = ["radial", "bar", "sculpture"]

        visualizations = {}

        if "radial" in visualization_types:
            visualizations["radial_chart"] = self.metrics_artist.create_radial_chart(
                metrics, title="Metrics Radial View"
            )

        if "bar" in visualization_types:
            visualizations["bar_chart"] = self.metrics_artist.create_bar_art(
                metrics, title="Metrics Bar Chart"
            )

        if "sculpture" in visualization_types:
            visualizations["data_sculpture"] = self.data_generator.create_data_sculpture(
                metrics, title="Metrics Sculpture"
            )

        return visualizations

    def visualize_dependencies(
        self, modules: list[str], dependencies: list[tuple[str, str]], style: ArtStyle | None = None
    ) -> str:
        """
        تصور شبكة التبعيات بشكل فني.

        Args:
            modules: قائمة أسماء الوحدات
            dependencies: قائمة التبعيات (من, إلى)
            style: نمط فني اختياري

        Returns:
            str: SVG network visualization

        Example:
            >>> integration = OvermindArtIntegration()
            >>> art = integration.visualize_dependencies(
            ...     modules=["auth", "users", "database"],
            ...     dependencies=[("users", "auth"), ("users", "database")]
            ... )
        """
        if style:
            self.network_artist = NetworkArtist(style)

        # تحويل قائمة الوحدات إلى عقد
        nodes = [{"id": module, "label": module} for module in modules]

        return self.network_artist.create_dependency_web(
            nodes=nodes, edges=dependencies, title="Code Dependencies Network"
        )

    def create_full_report(
        self, analysis_data: dict[str, object], style: ArtStyle | None = None
    ) -> dict[str, object]:
        """
        إنشاء تقرير فني شامل.

        CS73: تحويل التقرير التقني إلى معرض فني.

        Args:
            analysis_data: بيانات التحليل الشاملة
            style: نمط فني اختياري

        Returns:
            dict: تقرير فني شامل مع جميع التصورات
        """
        style = style or self.default_style

        report = {
            "style": style.value,
            "generated_at": "now",  # يمكن استبداله بـ datetime
            "visualizations": {},
        }

        # Code Intelligence Art
        if "code_analysis" in analysis_data:
            report["visualizations"]["code_intelligence"] = self.visualize_code_intelligence(
                analysis_data["code_analysis"], style
            )

        # Mission Journey Art
        if "mission_data" in analysis_data:
            report["visualizations"]["mission_journey"] = self.visualize_mission_journey(
                analysis_data["mission_data"], style
            )

        # Metrics Art
        if "metrics" in analysis_data:
            report["visualizations"]["metrics"] = self.visualize_metrics(
                analysis_data["metrics"], style
            )

        # Dependencies Network Art
        if "dependencies" in analysis_data:
            deps = analysis_data["dependencies"]
            report["visualizations"]["dependencies"] = self.visualize_dependencies(
                modules=deps.get("modules", []), dependencies=deps.get("edges", []), style=style
            )

        return report


def create_art_from_overmind_data(
    overmind_data: dict[str, object], style: ArtStyle = ArtStyle.MODERN
) -> dict[str, object]:
    """
    دالة مساعدة سريعة لإنشاء الفن من بيانات Overmind.

    CS73: One-liner للحصول على فن من البيانات.

    Args:
        overmind_data: أي بيانات من نظام Overmind
        style: النمط الفني

    Returns:
        dict: تصورات فنية

    Example:
        >>> from microservices.orchestrator_service.src.services.overmind.art.integration import create_art_from_overmind_data
        >>> art = create_art_from_overmind_data(my_analysis_result)
        >>> logger.info(art["visualizations"]["code_intelligence"]["complexity_art"])
    """
    integration = OvermindArtIntegration(style)
    return integration.create_full_report(overmind_data, style)
