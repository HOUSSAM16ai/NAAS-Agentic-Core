from datetime import timedelta
from typing import Protocol, runtime_checkable


@runtime_checkable
class CacheProviderProtocol(Protocol):
    """
    بروتوكول موفر التخزين المؤقت - Cache Provider Protocol

    This interface defines the contract for any caching mechanism used in the
    Gateway, ensuring that the underlying implementation (Memory, Redis, Memcached)
    can be swapped without affecting the core logic.

    Harvard Standard:
    - Interface Segregation Principle (ISP)
    - Dependency Inversion Principle (DIP)
    """

    async def get(self, key: str) -> object | None:
        """
        Retrieve an item from the cache.

        Args:
            key (str): The unique key for the item.

        Returns:
            object | None: The cached item if found and not expired, else None.
        """
        ...

    async def put(self, key: str, value: object, ttl: int | timedelta = 300) -> bool:
        """
        Store an item in the cache.

        Args:
            key (str): The unique key.
            value (object): The value to store (must be serializable if using remote cache).
            ttl (int | timedelta): Time To Live in seconds or timedelta object. Default 300s.

        Returns:
            bool: True if successful, False otherwise.
        """
        ...

    async def delete(self, key: str) -> bool:
        """
        Remove an item from the cache.

        Args:
            key (str): The unique key.

        Returns:
            bool: True if the item was found and removed, False otherwise.
        """
        ...

    async def clear(self) -> bool:
        """
        Clear all items from the cache.

        Returns:
            bool: True if successful.
        """
        ...

    async def get_stats(self) -> dict[str, object]:
        """
        Get statistics about the cache usage.

        Returns:
            dict: Dictionary containing metrics like hit_count, miss_count, size, etc.
        """
        ...
