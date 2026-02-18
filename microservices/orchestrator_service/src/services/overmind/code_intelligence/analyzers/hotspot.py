from microservices.orchestrator_service.src.services.overmind.code_intelligence.models import (
    FileMetrics,
    HotspotBuckets,
    HotspotConfig,
    HotspotWeights,
    NormalizedRanks,
)


class HotspotAnalyzer:
    """Analyzer for identifying code hotspots based on complexity, volatility, and smells."""

    def calculate_and_sort_hotspots(self, all_metrics: list[FileMetrics]) -> None:
        """
        Calculate hotspot scores and sort metrics by score.

        Args:
            all_metrics: List of file metrics
        """
        self.calculate_hotspot_scores(all_metrics)
        all_metrics.sort(key=lambda m: m.hotspot_score, reverse=True)

    def calculate_hotspot_scores(self, all_metrics: list[FileMetrics]) -> None:
        """
        Calculate hotspot scores with normalization.

        Args:
            all_metrics: List of file metrics
        """
        if not all_metrics:
            return

        # Extract and normalize values
        ranks = self._extract_and_normalize_metrics(all_metrics)

        # Calculate scores and assign priorities
        self._calculate_weighted_scores(all_metrics, ranks)

    def identify_hotspots(self, all_metrics: list[FileMetrics]) -> HotspotBuckets:
        """
        Identify critical and high priority hotspots.

        Args:
            all_metrics: Sorted list of file metrics

        Returns:
            HotspotBuckets: Categorized hotspots
        """
        return HotspotBuckets(
            critical=[m.relative_path for m in all_metrics[:20]],
            high=[m.relative_path for m in all_metrics[20:40]],
        )

    def _extract_and_normalize_metrics(self, all_metrics: list[FileMetrics]) -> NormalizedRanks:
        """
        Extract and normalize metrics.

        Args:
            all_metrics: List of metrics

        Returns:
            NormalizedRanks: Normalized values for each category
        """
        # Extract values
        complexities = [m.file_complexity for m in all_metrics]
        volatilities = [m.commits_last_12months for m in all_metrics]
        smells = [self._count_smells(m) for m in all_metrics]

        # Normalize
        return NormalizedRanks(
            complexity=self._normalize_values(complexities),
            volatility=self._normalize_values(volatilities),
            smell=self._normalize_values(smells),
        )

    def _count_smells(self, metrics: FileMetrics) -> int:
        """
        Count structural smells.

        Args:
            metrics: File metrics

        Returns:
            Number of smells
        """
        return (
            (1 if metrics.is_god_class else 0)
            + (1 if metrics.has_layer_mixing else 0)
            + (1 if metrics.has_cross_layer_imports else 0)
        )

    def _normalize_values(self, values: list[float]) -> list[float]:
        """
        Normalize values to 0-1 range.

        Args:
            values: List of values

        Returns:
            List of normalized values
        """
        if not values or max(values) == 0:
            return [0.0] * len(values)
        max_val = max(values)
        return [v / max_val for v in values]

    def _calculate_weighted_scores(
        self,
        all_metrics: list[FileMetrics],
        ranks: NormalizedRanks,
    ) -> None:
        """
        Calculate weighted scores.

        Args:
            all_metrics: List of metrics
            ranks: Normalized ranks
        """
        config = self._hotspot_config()
        for i, metrics in enumerate(all_metrics):
            self._assign_metric_ranks(metrics, ranks, i)
            score = self._calculate_hotspot_score(ranks, i, config.weights)
            metrics.hotspot_score = round(score, 4)
            metrics.priority_tier = self._determine_priority_tier(score)

    def _hotspot_config(self) -> HotspotConfig:
        """
        Create hotspot configuration.

        Returns:
            HotspotConfig: Hotspot settings
        """
        return HotspotConfig(
            weights=HotspotWeights(complexity=0.4, volatility=0.4, smell=0.2),
        )

    def _assign_metric_ranks(
        self,
        metrics: FileMetrics,
        ranks: NormalizedRanks,
        index: int,
    ) -> None:
        """
        Assign normalized ranks to file metrics.

        Args:
            metrics: File metrics
            ranks: Normalized ranks
            index: Index of the file in the list
        """
        metrics.complexity_rank = round(ranks.complexity[index], 4)
        metrics.volatility_rank = round(ranks.volatility[index], 4)
        metrics.smell_rank = round(ranks.smell[index], 4)

    def _calculate_hotspot_score(
        self,
        ranks: NormalizedRanks,
        index: int,
        weights: HotspotWeights,
    ) -> float:
        """
        Calculate hotspot score for a single file.

        Args:
            ranks: Normalized ranks
            index: Index of the file
            weights: Calculation weights

        Returns:
            float: Weighted score
        """
        return (
            weights.complexity * ranks.complexity[index]
            + weights.volatility * ranks.volatility[index]
            + weights.smell * ranks.smell[index]
        )

    def _determine_priority_tier(self, score: float) -> str:
        """
        Determine priority tier based on score.

        Args:
            score: Hotspot score

        Returns:
            Priority tier
        """
        if score >= 0.7:
            return "CRITICAL"
        if score >= 0.5:
            return "HIGH"
        if score >= 0.3:
            return "MEDIUM"
        return "LOW"
