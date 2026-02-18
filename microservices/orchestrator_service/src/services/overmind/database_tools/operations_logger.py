"""
مسجل العمليات (Operations Logger).

مسؤول عن تسجيل جميع العمليات المنفذة على قاعدة البيانات.
"""

from datetime import datetime

from app.core.di import get_logger

logger = get_logger(__name__)


class OperationsLogger:
    """مسجل العمليات على قاعدة البيانات."""

    def __init__(self) -> None:
        """تهيئة مسجل العمليات."""
        self.operations_log: list[dict[str, object]] = []

    def log_operation(
        self,
        operation: str,
        details: dict[str, object],
        success: bool = True,
    ) -> None:
        """
        تسجيل عملية في السجل.

        Args:
            operation: اسم العملية
            details: تفاصيل العملية
            success: هل نجحت العملية
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "operation": operation,
            "details": details,
            "success": success,
        }
        self.operations_log.append(log_entry)

        log_level = logger.info if success else logger.error
        log_level(f"DB Operation: {operation} - {'✓' if success else '✗'}")

    def get_operations_log(self) -> list[dict[str, object]]:
        """
        الحصول على سجل العمليات.

        Returns:
            list[dict]: جميع العمليات المُنفذة
        """
        return self.operations_log

    def clear_operations_log(self) -> None:
        """مسح سجل العمليات."""
        self.operations_log.clear()
        logger.info("Operations log cleared")
