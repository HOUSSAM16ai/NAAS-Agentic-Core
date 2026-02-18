"""
Shared environment variable readers to eliminate duplication.
"""

import os


def read_int_env(name: str, default: int) -> int:
    """Read integer from environment variable with fallback."""
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def read_bool_env(name: str, default: bool = False) -> bool:
    """Read boolean from environment variable with fallback."""
    return os.getenv(name, str(1 if default else 0)).strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def read_str_env(name: str, default: str = "") -> str:
    """Read string from environment variable with fallback."""
    return os.getenv(name, default)


def read_float_env(name: str, default: float) -> float:
    """Read float from environment variable with fallback."""
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default
