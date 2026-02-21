"""
Collaboration Context Implementation.
Implements the CollaborationContext protocol.
"""

from typing import Any


class InMemoryCollaborationContext:
    """
    In-memory implementation of CollaborationContext.
    """

    def __init__(self, initial_data: dict[str, Any] | None = None) -> None:
        self.shared_memory: dict[str, Any] = initial_data or {}

    def update(self, key: str, value: Any) -> None:
        """Update a value in shared memory."""
        self.shared_memory[key] = value

    def get(self, key: str) -> Any | None:
        """Get a value from shared memory."""
        return self.shared_memory.get(key)
