"""إعدادات اختبارات conversation-service — تجاهل تحذيرات LangGraph الداخلية."""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """يُضيف filterwarnings لتجاهل LangChainPendingDeprecationWarning."""
    config.addinivalue_line(
        "filterwarnings",
        "ignore::langchain_core._api.deprecation.LangChainPendingDeprecationWarning",
    )
    config.addinivalue_line(
        "filterwarnings",
        "ignore:.*allowed_objects.*will change.*",
    )
