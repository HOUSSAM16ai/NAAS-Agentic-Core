"""Probability & statistics — discrete distributions, expectation, Bayes, descriptive stats.

Discrete masses use exact ``Fraction`` where the inputs are integers (binomial,
hypergeometric), so a BAC probability answer is a rational, not a lossy float.
Descriptive statistics return floats. Every function validates its domain.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from fractions import Fraction

from microservices.foundations_service.src.foundations.combinatorics import combinations
from microservices.foundations_service.src.foundations.errors import (
    FoundationsError,
    require_non_negative_int,
)


def binomial_pmf(k: int, n: int, p: Fraction | float) -> Fraction | float:
    """P(X = k) for X ~ Binomial(n, p). Exact ``Fraction`` when ``p`` is a Fraction."""
    require_non_negative_int(n, "n")
    require_non_negative_int(k, "k")
    if not 0 <= p <= 1:
        raise FoundationsError(f"binomial_pmf: p must be in [0, 1], got {p}")
    if k > n:
        return Fraction(0) if isinstance(p, Fraction) else 0.0
    return combinations(n, k) * p**k * (1 - p) ** (n - k)


def binomial_cdf(k: int, n: int, p: Fraction | float) -> Fraction | float:
    """P(X <= k) for X ~ Binomial(n, p)."""
    require_non_negative_int(k, "k")
    zero: Fraction | float = Fraction(0) if isinstance(p, Fraction) else 0.0
    return sum((binomial_pmf(i, n, p) for i in range(min(k, n) + 1)), zero)


def hypergeometric_pmf(k: int, population: int, successes: int, draws: int) -> Fraction:
    """P(k successes) drawing ``draws`` without replacement from a finite population.

    The canonical BAC "urn" model: ``C(successes,k)·C(pop-successes,draws-k) / C(pop,draws)``.
    """
    for name, value in (
        ("population", population),
        ("successes", successes),
        ("draws", draws),
        ("k", k),
    ):
        require_non_negative_int(value, name)
    if successes > population or draws > population:
        raise FoundationsError("hypergeometric_pmf: successes and draws must be <= population")
    if k > successes or (draws - k) > (population - successes) or k > draws:
        return Fraction(0)
    favorable = combinations(successes, k) * combinations(population - successes, draws - k)
    return Fraction(favorable, combinations(population, draws))


def expectation(values: Sequence[float], probabilities: Sequence[Fraction | float]) -> float:
    """E[X] = Σ xᵢ·pᵢ for a discrete distribution (probabilities must sum to 1)."""
    _validate_distribution(values, probabilities)
    return float(sum(x * float(p) for x, p in zip(values, probabilities, strict=True)))


def variance(values: Sequence[float], probabilities: Sequence[Fraction | float]) -> float:
    """Var(X) = E[X²] − E[X]² for a discrete distribution."""
    _validate_distribution(values, probabilities)
    mean = expectation(values, probabilities)
    return float(
        sum((x - mean) ** 2 * float(p) for x, p in zip(values, probabilities, strict=True))
    )


def bayes_posterior(
    prior: Fraction | float,
    likelihood: Fraction | float,
    false_positive: Fraction | float,
) -> float:
    """P(H | E) via Bayes: ``prior·likelihood / (prior·likelihood + (1−prior)·false_positive)``."""
    for name, value in (
        ("prior", prior),
        ("likelihood", likelihood),
        ("false_positive", false_positive),
    ):
        if not 0 <= value <= 1:
            raise FoundationsError(f"bayes_posterior: {name} must be in [0, 1], got {value}")
    evidence = prior * likelihood + (1 - prior) * false_positive
    if evidence == 0:
        raise FoundationsError("bayes_posterior: evidence probability is 0 (undefined posterior)")
    return float(prior * likelihood / evidence)


# --- Descriptive statistics (float results) ---------------------------------


def mean(data: Sequence[float]) -> float:
    """Arithmetic mean."""
    _require_non_empty(data, "mean")
    return statistics.fmean(data)


def median(data: Sequence[float]) -> float:
    """Median (middle value / average of the two middle values)."""
    _require_non_empty(data, "median")
    return statistics.median(data)


def sample_variance(data: Sequence[float]) -> float:
    """Unbiased sample variance (n − 1 denominator); needs at least 2 points."""
    if len(data) < 2:
        raise FoundationsError("sample_variance: at least 2 data points are required")
    return statistics.variance(data)


def sample_stddev(data: Sequence[float]) -> float:
    """Unbiased sample standard deviation."""
    return math.sqrt(sample_variance(data))


def _require_non_empty(data: Sequence[float], name: str) -> None:
    if not data:
        raise FoundationsError(f"{name}: data must be non-empty")


def _validate_distribution(
    values: Sequence[float], probabilities: Sequence[Fraction | float]
) -> None:
    if len(values) != len(probabilities):
        raise FoundationsError("distribution: values and probabilities must have equal length")
    if not values:
        raise FoundationsError("distribution: at least one outcome is required")
    for p in probabilities:
        if not 0 <= p <= 1:
            raise FoundationsError(f"distribution: probability {p} is outside [0, 1]")
    total = sum(float(p) for p in probabilities)
    if not math.isclose(total, 1.0, abs_tol=1e-9):
        raise FoundationsError(f"distribution: probabilities sum to {total}, expected 1")
