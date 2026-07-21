"""Number theory — gcd/lcm, primality, factorization, modular arithmetic.

Exact integer arithmetic. ``is_prime`` uses a deterministic Miller–Rabin with a
witness set that is proven correct for all n < 3.3 × 10^24, which covers every
value a Baccalaureate problem can produce.
"""

from __future__ import annotations

import math

from app.core.foundations.errors import FoundationsError, require_non_negative_int

# Deterministic Miller–Rabin witnesses (correct for all n < 3,317,044,064,679,887,385,961,981).
_MR_WITNESSES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)


def gcd(a: int, b: int) -> int:
    """Greatest common divisor (Euclid's algorithm, via stdlib)."""
    return math.gcd(a, b)


def lcm(a: int, b: int) -> int:
    """Least common multiple. ``lcm(0, x) == 0``."""
    return math.lcm(a, b)


def is_prime(n: int) -> bool:
    """True iff ``n`` is prime. Deterministic for all inputs a BAC problem yields."""
    require_non_negative_int(n, "n")
    if n < 2:
        return False
    for p in _MR_WITNESSES:
        if n == p:
            return True
        if n % p == 0:
            return False
    d = n - 1
    r = 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for a in _MR_WITNESSES:
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def prime_factorization(n: int) -> dict[int, int]:
    """Return ``{prime: exponent}`` for ``n >= 2`` (e.g. 360 → {2:3, 3:2, 5:1})."""
    require_non_negative_int(n, "n")
    if n < 2:
        raise FoundationsError(f"prime_factorization: n must be >= 2, got {n}")
    factors: dict[int, int] = {}
    for p in (2, 3):
        while n % p == 0:
            factors[p] = factors.get(p, 0) + 1
            n //= p
    i = 5
    step = 2
    while i * i <= n:
        while n % i == 0:
            factors[i] = factors.get(i, 0) + 1
            n //= i
        i += step
        step = 6 - step  # 5,7,11,13,... (skip multiples of 2 and 3)
    if n > 1:
        factors[n] = factors.get(n, 0) + 1
    return factors


def divisors(n: int) -> list[int]:
    """Sorted list of all positive divisors of ``n >= 1``."""
    require_non_negative_int(n, "n")
    if n < 1:
        raise FoundationsError(f"divisors: n must be >= 1, got {n}")
    small, large = [], []
    i = 1
    while i * i <= n:
        if n % i == 0:
            small.append(i)
            if i != n // i:
                large.append(n // i)
        i += 1
    return small + large[::-1]


def euler_totient(n: int) -> int:
    """Euler's φ(n) — count of integers in [1, n] coprime to ``n`` (n >= 1)."""
    require_non_negative_int(n, "n")
    if n < 1:
        raise FoundationsError(f"euler_totient: n must be >= 1, got {n}")
    result = n
    for p in prime_factorization(n) if n > 1 else {}:
        result -= result // p
    return result


def mod_pow(base: int, exponent: int, modulus: int) -> int:
    """Modular exponentiation ``base**exponent mod modulus`` (fast, stdlib pow)."""
    require_non_negative_int(exponent, "exponent")
    if modulus <= 0:
        raise FoundationsError(f"mod_pow: modulus must be positive, got {modulus}")
    return pow(base, exponent, modulus)


def mod_inverse(a: int, modulus: int) -> int:
    """Modular multiplicative inverse of ``a`` mod ``modulus`` (requires gcd(a, m) == 1)."""
    if modulus <= 0:
        raise FoundationsError(f"mod_inverse: modulus must be positive, got {modulus}")
    if math.gcd(a % modulus, modulus) != 1:
        raise FoundationsError(f"mod_inverse: {a} has no inverse mod {modulus} (not coprime)")
    return pow(a, -1, modulus)
