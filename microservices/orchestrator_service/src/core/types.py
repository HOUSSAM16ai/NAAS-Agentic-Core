"""
نظام الأنواع المركزي (Central Type System).
========================================

This module provides centralized type definitions following CS 252r principles:
- Type safety and correctness
- Reusable type aliases
- Clear semantic types
- Documentation for complex types

المعايير (Standards):
- Harvard CS 252r: Type Systems & Program Verification
- PEP 484: Type Hints
- PEP 604: Allow writing union types as X | Y
- PEP 695: Type Parameter Syntax

استخدام (Usage):
    from microservices.orchestrator_service.src.core.types import JSON, JSONDict, JSONList, Metadata
"""

from __future__ import annotations

from typing import TypeVar

# ============================================================================
# Basic Type Aliases
# ============================================================================

type JSONPrimitive = str | int | float | bool | None
"""القيمة البدائية المسموح بها ضمن JSON."""

type JSON = dict[str, "JSON"] | list["JSON"] | JSONPrimitive
"""نوع يدعم جميع قيم JSON بشكل متداخل دون استخدام object."""

type JSONDict = dict[str, JSON]
"""تمثيل كائن JSON مع قيم متماسكة النوع."""

type JSONList = list[JSON]
"""تمثيل مصفوفة JSON بقيم متداخلة محكمة."""

type JSONValue = JSONPrimitive
"""نوع القيم البدائية لـ JSON لإبقاء التوثيق موحدًا."""

# ============================================================================
# Common Data Structure Types
# ============================================================================

type Metadata = dict[str, str | int | float | bool]
"""قاموس بيانات وصفية بقيم بدائية فقط لتفادي الأنواع الحرة."""

type Headers = dict[str, str]
"""HTTP headers type"""

type QueryParams = dict[str, str | int | bool]
"""نوع معاملات الاستعلام بقيم محددة ودون object."""

type Config = dict[str, JSON]
"""تهيئة منسجمة تعتمد على قيم JSON الصارمة."""

# ============================================================================
# Function and Callback Types
# ============================================================================

from collections.abc import Awaitable, Callable

type AsyncCallable = Callable[..., Awaitable[object]]
"""تابع غير متزامن يعيد أي كائن مضبوط النوع دون اللجوء إلى object."""

type ErrorHandler = Callable[[Exception], object]
"""معالج أخطاء يعيد قيمة مضبوطة لتوثيق السلوك بوضوح."""

type Validator = Callable[[object], bool]
"""دالة تحقق لمدخلات موثقة بدلاً من الأنواع العامة."""

# ============================================================================
# Domain-Specific Types
# ============================================================================

# User and Authentication
type UserId = int
"""User identifier type"""

type Email = str
"""Email address type (semantic)"""

type Token = str
"""Authentication token type"""

# Mission and Task
type MissionId = int
"""Mission identifier type"""

type TaskId = int
"""Task identifier type"""

# Timestamps
type Timestamp = float
"""Unix timestamp (seconds since epoch)"""

# ============================================================================
# Type Variables for Generics
# ============================================================================


class BaseEntity:
    """كيان أساسي لتقييد المتغيرات النوعية بعقدة نطاقية واضحة."""


T = TypeVar("T")
"""Generic type variable"""

T_co = TypeVar("T_co", covariant=True)
"""Covariant type variable"""

T_contra = TypeVar("T_contra", contravariant=True)
"""Contravariant type variable"""

# Bounded type variables
EntityT = TypeVar("EntityT", bound="BaseEntity")
"""Type variable bounded to BaseEntity"""

ModelT = TypeVar("ModelT")
"""Type variable for model types"""

# ============================================================================
# Result Types (for error handling)
# ============================================================================


class Result[T]:
    """
    نوع نتيجة موثق لإرجاع نجاح أو خطأ مع واجهة عربية واضحة.

    Result type for operations that can succeed or fail.

    Following functional programming principles for error handling.

    Example:
        def divide(a: int, b: int) -> Result[float]:
            if b == 0:
                return Result.from_error("Division by zero")
            return Result.ok(a / b)
    """

    def __init__(self, value: T | None = None, error: str | None = None):
        self._value = value
        self._error = error

    @property
    def is_ok(self) -> bool:
        """Check if result is successful"""
        return self._error is None

    @property
    def is_error(self) -> bool:
        """Check if result is an error"""
        return self._error is not None

    @property
    def value(self) -> T:
        """Get the value (raises if error)"""
        if self._error:
            raise ValueError(f"Cannot get value from error result: {self._error}")
        return self._value  # type: ignore

    @property
    def error(self) -> str:
        """Get the error message (raises if ok)"""
        if self._error is None:
            raise ValueError("Cannot get error from ok result")
        return self._error

    @classmethod
    def ok(cls, value: T) -> Result[T]:
        """Create a successful result"""
        return cls(value=value)

    @classmethod
    def from_error(cls, error: str) -> Result[T]:
        """Create an error result"""
        return cls(error=error)


# ============================================================================
# Export All Types
# ============================================================================

__all__ = [
    "JSON",
    "AsyncCallable",
    "BaseEntity",
    "Config",
    "Email",
    "EntityT",
    "ErrorHandler",
    "Headers",
    "JSONDict",
    "JSONList",
    "JSONPrimitive",
    "JSONValue",
    "Metadata",
    "MissionId",
    "ModelT",
    "QueryParams",
    "Result",
    "T",
    "T_co",
    "T_contra",
    "TaskId",
    "Timestamp",
    "Token",
    "UserId",
    "Validator",
]
