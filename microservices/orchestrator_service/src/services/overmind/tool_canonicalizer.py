"""
Tool Name Canonicalization System
==================================

Advanced tool name canonicalization using Strategy Pattern and Chain of Responsibility.
Reduces cyclomatic complexity from 22 to ~3 per strategy.

Architecture:
- Strategy Pattern: Pluggable canonicalization strategies
- Chain of Responsibility: Sequential strategy evaluation
- Single Responsibility: Each strategy handles one concern
- Open/Closed: Easy to add new strategies without modifying existing code
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CanonicalResult:
    """Result of tool name canonicalization."""

    canonical_name: str
    notes: list[str]
    matched_by: str | None = None

    @classmethod
    def unmatched(cls, original_name: str) -> CanonicalResult:
        """Create result for unmatched tool name."""
        return cls(canonical_name=original_name, notes=[], matched_by=None)


class CanonicalStrategy(ABC):
    """Base strategy for tool name canonicalization."""

    @abstractmethod
    def can_handle(self, name: str, description: str) -> bool:
        """Check if this strategy can handle the given tool name."""

    @abstractmethod
    def canonicalize(self, name: str, description: str) -> CanonicalResult:
        """Canonicalize the tool name."""

    @property
    @abstractmethod
    def priority(self) -> int:
        """Strategy priority (lower = higher priority)."""


class DottedNameStrategy(CanonicalStrategy):
    """Handle dotted tool names (e.g., 'file.write')."""

    def __init__(self, accept_dotted: bool = True):
        self.accept_dotted = accept_dotted
        self.write_suffixes = {"write", "create", "save", "update", "delete", "modify"}
        self.read_suffixes = {"read", "open", "load", "get", "fetch", "list"}

    @property
    def priority(self) -> int:
        return 10

    def can_handle(self, name: str, description: str) -> bool:
        return self.accept_dotted and "." in name

    def canonicalize(self, name: str, description: str) -> CanonicalResult:
        base, suffix = name.split(".", 1)
        notes = [f"dotted_split:{base}.{suffix}"]

        if suffix.lower() in self.write_suffixes:
            return CanonicalResult("write_file", notes, "DottedNameStrategy")
        if suffix.lower() in self.read_suffixes:
            return CanonicalResult("read_file", notes, "DottedNameStrategy")

        return CanonicalResult.unmatched(name)


class AliasStrategy(CanonicalStrategy):
    """Handle tool name aliases."""

    def __init__(
        self,
        write_aliases: set[str] | None = None,
        read_aliases: set[str] | None = None,
    ):
        self.write_aliases = write_aliases or {
            "write",
            "write_file",
            "create_file",
            "save_file",
            "update_file",
            "str_replace_editor",
            "str_replace",
        }
        self.read_aliases = read_aliases or {
            "read",
            "read_file",
            "open_file",
            "load_file",
            "view_file",
            "cat",
        }

    @property
    def priority(self) -> int:
        return 20

    def can_handle(self, name: str, description: str) -> bool:
        name_lower = name.lower()
        return name_lower in self.write_aliases or name_lower in self.read_aliases

    def canonicalize(self, name: str, description: str) -> CanonicalResult:
        name_lower = name.lower()

        if name_lower in self.write_aliases:
            return CanonicalResult("write_file", [f"alias_write:{name}"], "AliasStrategy")
        if name_lower in self.read_aliases:
            return CanonicalResult("read_file", [f"alias_read:{name}"], "AliasStrategy")

        return CanonicalResult.unmatched(name)


class DirectMatchStrategy(CanonicalStrategy):
    """Handle direct canonical name matches."""

    def __init__(self):
        self.canonical_names = {
            "ensure_file",
            "append_file",
            "get_project_metrics",
            "count_files",
            "search_educational_content",
            "search_content",
            "get_content_raw",
            "list_files",
        }

    @property
    def priority(self) -> int:
        return 30

    def can_handle(self, name: str, description: str) -> bool:
        return name.lower() in self.canonical_names

    def canonicalize(self, name: str, description: str) -> CanonicalResult:
        name_lower = name.lower()
        return CanonicalResult(name_lower, [f"direct_{name_lower}"], "DirectMatchStrategy")


class KeywordStrategy(CanonicalStrategy):
    """Handle tool names containing specific keywords."""

    def __init__(self):
        self.write_keywords = {"write", "create", "generate", "save", "update"}
        self.read_keywords = {"read", "open", "load", "get", "fetch"}

    @property
    def priority(self) -> int:
        return 40

    def can_handle(self, name: str, description: str) -> bool:
        name_lower = name.lower()
        return any(kw in name_lower for kw in self.write_keywords | self.read_keywords)

    def canonicalize(self, name: str, description: str) -> CanonicalResult:
        name_lower = name.lower()

        for keyword in self.write_keywords:
            if keyword in name_lower:
                return CanonicalResult(
                    "write_file",
                    [f"keyword_write:{keyword}"],
                    "KeywordStrategy",
                )

        for keyword in self.read_keywords:
            if keyword in name_lower:
                return CanonicalResult(
                    "read_file",
                    [f"keyword_read:{keyword}"],
                    "KeywordStrategy",
                )

        return CanonicalResult.unmatched(name)


class DescriptionIntentStrategy(CanonicalStrategy):
    """Infer intent from tool description when name is ambiguous."""

    def __init__(self, force_intent_check: bool = True):
        self.force_intent_check = force_intent_check
        self.ambiguous_names = {"", "unknown", "file", "filesystem"}
        self.write_patterns = {"write", "create", "save", "modify", "update", "delete"}
        self.read_patterns = {"read", "open", "load", "view", "get", "fetch"}

    @property
    def priority(self) -> int:
        return 50

    def can_handle(self, name: str, description: str) -> bool:
        return self.force_intent_check and name.lower() in self.ambiguous_names and description

    def canonicalize(self, name: str, description: str) -> CanonicalResult:
        desc_lower = description.lower()

        if any(pattern in desc_lower for pattern in self.write_patterns):
            return CanonicalResult(
                "write_file",
                ["intent_desc_write"],
                "DescriptionIntentStrategy",
            )

        if any(pattern in desc_lower for pattern in self.read_patterns):
            return CanonicalResult(
                "read_file",
                ["intent_desc_read"],
                "DescriptionIntentStrategy",
            )

        return CanonicalResult.unmatched(name)


class ToolCanonicalizer:
    """
    Advanced tool name canonicalizer using Chain of Responsibility.

    Reduces complexity from CC:22 to CC:3 per strategy.
    """

    def __init__(self, strategies: list[CanonicalStrategy] | None = None):
        if strategies is None:
            strategies = self._default_strategies()

        self.strategies = sorted(strategies, key=lambda s: s.priority)

    @staticmethod
    def _default_strategies() -> list[CanonicalStrategy]:
        """Create default strategy chain."""
        return [
            DottedNameStrategy(),
            AliasStrategy(),
            DirectMatchStrategy(),
            KeywordStrategy(),
            DescriptionIntentStrategy(),
        ]

    def canonicalize(self, raw_name: str, description: str = "") -> CanonicalResult:
        """
        Canonicalize tool name using strategy chain.

        Args:
            raw_name: Raw tool name from LLM
            description: Tool description for intent inference

        Returns:
            CanonicalResult with canonical name and notes
        """
        for strategy in self.strategies:
            if strategy.can_handle(raw_name, description):
                result = strategy.canonicalize(raw_name, description)
                if result.matched_by:
                    return result

        return CanonicalResult.unmatched(raw_name)

    def add_strategy(self, strategy: CanonicalStrategy) -> None:
        """Add a new strategy to the chain."""
        self.strategies.append(strategy)
        self.strategies.sort(key=lambda s: s.priority)

    def remove_strategy(self, strategy_type: type[CanonicalStrategy]) -> None:
        """Remove a strategy from the chain."""
        self.strategies = [s for s in self.strategies if not isinstance(s, strategy_type)]


# Singleton instance for backward compatibility
_default_canonicalizer: ToolCanonicalizer | None = None


def get_canonicalizer() -> ToolCanonicalizer:
    """Get or create default canonicalizer instance."""
    global _default_canonicalizer
    if _default_canonicalizer is None:
        _default_canonicalizer = ToolCanonicalizer()
    return _default_canonicalizer


def canonicalize_tool_name(raw_name: str, description: str = "") -> tuple[str, list[str]]:
    """
    Backward-compatible function for tool name canonicalization.

    Args:
        raw_name: Raw tool name
        description: Tool description

    Returns:
        Tuple of (canonical_name, notes)
    """
    result = get_canonicalizer().canonicalize(raw_name, description)
    return result.canonical_name, result.notes
