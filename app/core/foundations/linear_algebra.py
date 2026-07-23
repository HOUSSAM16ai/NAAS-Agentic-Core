"""Linear algebra — vectors, matrices, and exact/near-exact linear systems.

Dependency-free implementations of the linear-algebra a first course covers:
vector arithmetic, matrix products, transpose, determinant, rank, and solving
``Ax = b`` by Gaussian elimination with partial pivoting. Vectors are plain
sequences of numbers; matrices are row-major sequences of equal-length rows.

Every primitive raises :class:`FoundationsError` on a shape/domain violation
(non-rectangular matrix, dimension mismatch, singular system) rather than
returning a misleading value — the impossibility is the teachable fact.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from app.core.foundations.errors import FoundationsError

Vector = Sequence[float]
Matrix = Sequence[Sequence[float]]


# --- Vectors ----------------------------------------------------------------


def dot(a: Vector, b: Vector) -> float:
    """Dot product ``Σ aᵢ·bᵢ`` — requires equal-length vectors."""
    if len(a) != len(b):
        raise FoundationsError(f"dot: length mismatch ({len(a)} vs {len(b)})")
    if not a:
        raise FoundationsError("dot: vectors must be non-empty")
    return math.fsum(x * y for x, y in zip(a, b, strict=True))


def vector_add(a: Vector, b: Vector) -> list[float]:
    """Element-wise sum of two equal-length vectors."""
    if len(a) != len(b):
        raise FoundationsError(f"vector_add: length mismatch ({len(a)} vs {len(b)})")
    return [x + y for x, y in zip(a, b, strict=True)]


def scale(vector: Vector, factor: float) -> list[float]:
    """Multiply every component of ``vector`` by ``factor``."""
    return [factor * x for x in vector]


def norm(vector: Vector) -> float:
    """Euclidean (L2) length ``√Σ xᵢ²``."""
    if not vector:
        raise FoundationsError("norm: vector must be non-empty")
    return math.sqrt(math.fsum(x * x for x in vector))


# --- Matrices ---------------------------------------------------------------


def _validate_matrix(matrix: Matrix, name: str = "matrix") -> tuple[int, int]:
    """Return ``(rows, cols)`` after checking ``matrix`` is non-empty & rectangular."""
    if not matrix or not matrix[0]:
        raise FoundationsError(f"{name}: must be a non-empty matrix")
    cols = len(matrix[0])
    for i, row in enumerate(matrix):
        if len(row) != cols:
            raise FoundationsError(f"{name}: row {i} has length {len(row)}, expected {cols}")
    return len(matrix), cols


def transpose(matrix: Matrix) -> list[list[float]]:
    """Return ``matrixᵀ`` — rows become columns."""
    _validate_matrix(matrix)
    return [list(col) for col in zip(*matrix, strict=True)]


def matmul(a: Matrix, b: Matrix) -> list[list[float]]:
    """Matrix product ``A·B`` — inner dimensions must agree."""
    _ra, ca = _validate_matrix(a, "a")
    rb, _cb = _validate_matrix(b, "b")
    if ca != rb:
        raise FoundationsError(f"matmul: inner dimensions disagree ({ca} vs {rb})")
    bt = transpose(b)
    return [[math.fsum(x * y for x, y in zip(row, col, strict=True)) for col in bt] for row in a]


def identity(n: int) -> list[list[float]]:
    """The ``n×n`` identity matrix."""
    if not isinstance(n, int) or isinstance(n, bool) or n <= 0:
        raise FoundationsError(f"identity: n must be a positive int, got {n!r}")
    return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]


def determinant(matrix: Matrix) -> float:
    """Determinant of a square matrix via LU-style elimination (O(n³))."""
    rows, cols = _validate_matrix(matrix)
    if rows != cols:
        raise FoundationsError(f"determinant: matrix must be square, got {rows}×{cols}")
    m = [list(map(float, row)) for row in matrix]
    n = rows
    det = 1.0
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-12:
            return 0.0
        if pivot != col:
            m[col], m[pivot] = m[pivot], m[col]
            det = -det
        det *= m[col][col]
        for r in range(col + 1, n):
            factor = m[r][col] / m[col][col]
            for c in range(col, n):
                m[r][c] -= factor * m[col][c]
    return det


def is_singular(matrix: Matrix) -> bool:
    """True when the square matrix has determinant 0 (no unique inverse/solution)."""
    return abs(determinant(matrix)) < 1e-12


def solve_linear_system(a: Matrix, b: Vector) -> list[float]:
    """Solve ``Ax = b`` for a square, non-singular ``A`` (Gaussian elimination).

    Raises :class:`FoundationsError` when ``A`` is singular — no unique solution
    is the teachable fact, not a silent NaN.
    """
    rows, cols = _validate_matrix(a, "a")
    if rows != cols:
        raise FoundationsError(f"solve_linear_system: A must be square, got {rows}×{cols}")
    if len(b) != rows:
        raise FoundationsError(f"solve_linear_system: b length {len(b)} != {rows}")
    n = rows
    aug = [[*map(float, row), float(b[i])] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-12:
            raise FoundationsError("solve_linear_system: singular matrix — no unique solution")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        pivot_val = aug[col][col]
        for r in range(n):
            if r == col:
                continue
            factor = aug[r][col] / pivot_val
            for c in range(col, n + 1):
                aug[r][c] -= factor * aug[col][c]
    return [aug[i][n] / aug[i][i] for i in range(n)]


def matrix_rank(matrix: Matrix) -> int:
    """Rank — the number of linearly independent rows (row-echelon pivots)."""
    _validate_matrix(matrix)
    m = [list(map(float, row)) for row in matrix]
    rows = len(m)
    cols = len(m[0])
    rank = 0
    pivot_row = 0
    for col in range(cols):
        if pivot_row >= rows:
            break
        pivot = max(range(pivot_row, rows), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-12:
            continue
        m[pivot_row], m[pivot] = m[pivot], m[pivot_row]
        pivot_val = m[pivot_row][col]
        for r in range(rows):
            if r != pivot_row and abs(m[r][col]) > 1e-12:
                factor = m[r][col] / pivot_val
                for c in range(col, cols):
                    m[r][c] -= factor * m[pivot_row][c]
        pivot_row += 1
        rank += 1
    return rank
