"""Statistics — inferential layer (correlation, regression, intervals, tests).

Complements the *descriptive* statistics already in ``probability.py`` (mean,
median, sample variance/stddev) with the *inferential* layer a first course adds:
covariance, Pearson correlation, ordinary least-squares regression with r²,
standardization, a normal-approx confidence interval, a one-sample t-statistic,
and percentiles.

Results are floats. Every primitive raises :class:`FoundationsError` on a domain
violation (too few points, constant series, out-of-range percentile) rather than
returning a misleading 0.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from app.core.foundations.errors import FoundationsError
from app.core.foundations.probability import mean, sample_stddev, sample_variance

__all__ = [
    "confidence_interval_mean",
    "correlation",
    "covariance",
    "linear_regression",
    "percentile",
    "standardize",
    "t_statistic",
    "z_score",
]


def _require_pair(xs: Sequence[float], ys: Sequence[float], name: str) -> None:
    if len(xs) != len(ys):
        raise FoundationsError(f"{name}: series length mismatch ({len(xs)} vs {len(ys)})")
    if len(xs) < 2:
        raise FoundationsError(f"{name}: at least 2 paired points are required")


def covariance(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Sample covariance ``Σ(xᵢ−x̄)(yᵢ−ȳ) / (n−1)``."""
    _require_pair(xs, ys, "covariance")
    mx, my = mean(xs), mean(ys)
    return math.fsum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / (len(xs) - 1)


def correlation(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Pearson correlation coefficient in ``[-1, 1]``.

    Raises when either series is constant (zero variance) — correlation is
    undefined, not 0.
    """
    _require_pair(xs, ys, "correlation")
    sx, sy = sample_stddev(xs), sample_stddev(ys)
    if sx == 0 or sy == 0:
        raise FoundationsError("correlation: a series has zero variance — correlation undefined")
    return covariance(xs, ys) / (sx * sy)


def linear_regression(xs: Sequence[float], ys: Sequence[float]) -> dict[str, float]:
    """Ordinary least-squares fit ``y = slope·x + intercept`` with ``r_squared``."""
    _require_pair(xs, ys, "linear_regression")
    var_x = sample_variance(xs)
    if var_x == 0:
        raise FoundationsError("linear_regression: x has zero variance — slope undefined")
    slope = covariance(xs, ys) / var_x
    intercept = mean(ys) - slope * mean(xs)
    r = correlation(xs, ys) if sample_variance(ys) > 0 else 0.0
    return {"slope": slope, "intercept": intercept, "r_squared": r * r}


def z_score(value: float, data: Sequence[float]) -> float:
    """Standard score ``(value − mean) / stddev`` of ``value`` against ``data``."""
    sd = sample_stddev(data)
    if sd == 0:
        raise FoundationsError("z_score: data has zero standard deviation")
    return (value - mean(data)) / sd


def standardize(data: Sequence[float]) -> list[float]:
    """Return ``data`` rescaled to zero mean and unit standard deviation."""
    sd = sample_stddev(data)
    if sd == 0:
        raise FoundationsError("standardize: data has zero standard deviation")
    mu = mean(data)
    return [(x - mu) / sd for x in data]


def confidence_interval_mean(
    data: Sequence[float], confidence: float = 0.95
) -> tuple[float, float]:
    """Normal-approx CI for the population mean at the given ``confidence`` level."""
    if not 0 < confidence < 1:
        raise FoundationsError(
            f"confidence_interval_mean: confidence must be in (0,1), got {confidence}"
        )
    n = len(data)
    if n < 2:
        raise FoundationsError("confidence_interval_mean: at least 2 data points are required")
    mu = mean(data)
    stderr = sample_stddev(data) / math.sqrt(n)
    # Two-sided normal critical value via the inverse-erf identity.
    z = math.sqrt(2) * _erfinv(confidence)
    return (mu - z * stderr, mu + z * stderr)


def t_statistic(data: Sequence[float], population_mean: float) -> float:
    """One-sample t-statistic ``(x̄ − μ₀) / (s/√n)``."""
    n = len(data)
    if n < 2:
        raise FoundationsError("t_statistic: at least 2 data points are required")
    stderr = sample_stddev(data) / math.sqrt(n)
    if stderr == 0:
        raise FoundationsError("t_statistic: zero standard error (constant data)")
    return (mean(data) - population_mean) / stderr


def percentile(data: Sequence[float], p: float) -> float:
    """The ``p``-th percentile (0–100) via linear interpolation between ranks."""
    if not data:
        raise FoundationsError("percentile: data must be non-empty")
    if not 0 <= p <= 100:
        raise FoundationsError(f"percentile: p must be in [0, 100], got {p}")
    ordered = sorted(data)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (p / 100) * (len(ordered) - 1)
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return float(ordered[lo])
    return ordered[lo] + (rank - lo) * (ordered[hi] - ordered[lo])


def _erfinv(confidence: float) -> float:
    """Inverse error function argument for a two-sided ``confidence`` level.

    Solves ``erf(t) = confidence`` by bisection — dependency-free and precise
    enough for teaching-grade confidence intervals.
    """
    target = confidence
    lo, hi = 0.0, 5.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if math.erf(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2
