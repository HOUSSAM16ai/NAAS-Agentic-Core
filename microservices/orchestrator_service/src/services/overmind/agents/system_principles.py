"""
المبادئ الصارمة للنظام على مستوى المشروع.

هذا الملف يمثل مصدر الحقيقة لمبادئ النظام الإلزامية
ويتيح الوصول البرمجي إليها بشكل موحد.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from pathlib import Path

import yaml

# Cache path to avoid re-calculating
# Adjusted to be relative to this file in the new microservice structure
_CONFIG_DIR = Path(__file__).parent.parent.parent.parent / "config_data"
_PRINCIPLES_FILE = _CONFIG_DIR / "system_principles.yaml"


@dataclass(frozen=True)
class SystemPrinciple:
    """تمثيل مبدأ واحد من مبادئ النظام الصارمة."""

    number: int
    statement: str


def _load_principles_from_yaml(section: str) -> tuple[SystemPrinciple, ...]:
    """
    Load principles from the YAML configuration file.
    """
    if not _PRINCIPLES_FILE.exists():
        return ()

    with open(_PRINCIPLES_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if section not in data:
        return ()

    principles = []
    for item in data[section]:
        principles.append(SystemPrinciple(number=item["number"], statement=item["statement"]))

    return tuple(principles)


@functools.lru_cache(maxsize=1)
def _get_all_system_principles() -> tuple[SystemPrinciple, ...]:
    return _load_principles_from_yaml("system_principles")


@functools.lru_cache(maxsize=1)
def _get_all_architecture_principles() -> tuple[SystemPrinciple, ...]:
    return _load_principles_from_yaml("architecture_principles")


def get_system_principles() -> tuple[SystemPrinciple, ...]:
    """الحصول على جميع مبادئ النظام الصارمة بشكل ثابت."""
    return _get_all_system_principles()


def get_architecture_system_principles() -> tuple[SystemPrinciple, ...]:
    """الحصول على مبادئ المعمارية وحوكمة البيانات الأساسية."""
    return _get_all_architecture_principles()
