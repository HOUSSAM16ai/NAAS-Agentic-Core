"""Data structures — teaching-grade Stack, Queue, MinHeap, LinkedList, BST.

Deterministic, dependency-free implementations of the canonical abstract data
types a first course covers, each with the invariant made explicit and every
illegal operation (pop/peek on empty, etc.) raising :class:`FoundationsError`
rather than returning ``None`` — the impossibility is the teachable fact.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from microservices.foundations_service.src.foundations.errors import FoundationsError


class Stack[T]:
    """LIFO stack — ``push`` / ``pop`` / ``peek`` in O(1)."""

    def __init__(self, items: Iterable[T] | None = None) -> None:
        self._items: list[T] = list(items) if items is not None else []

    def push(self, item: T) -> None:
        self._items.append(item)

    def pop(self) -> T:
        if not self._items:
            raise FoundationsError("Stack.pop: stack is empty")
        return self._items.pop()

    def peek(self) -> T:
        if not self._items:
            raise FoundationsError("Stack.peek: stack is empty")
        return self._items[-1]

    def is_empty(self) -> bool:
        return not self._items

    def __len__(self) -> int:
        return len(self._items)


class Queue[T]:
    """FIFO queue — ``enqueue`` / ``dequeue`` / ``peek`` in amortized O(1)."""

    def __init__(self, items: Iterable[T] | None = None) -> None:
        from collections import deque

        self._items: deque[T] = deque(items) if items is not None else deque()

    def enqueue(self, item: T) -> None:
        self._items.append(item)

    def dequeue(self) -> T:
        if not self._items:
            raise FoundationsError("Queue.dequeue: queue is empty")
        return self._items.popleft()

    def peek(self) -> T:
        if not self._items:
            raise FoundationsError("Queue.peek: queue is empty")
        return self._items[0]

    def is_empty(self) -> bool:
        return not self._items

    def __len__(self) -> int:
        return len(self._items)


class MinHeap:
    """Binary min-heap over comparable numbers — ``push`` / ``pop`` in O(log n)."""

    def __init__(self, values: Iterable[float] | None = None) -> None:
        import heapq

        self._heap: list[float] = list(values) if values is not None else []
        heapq.heapify(self._heap)

    def push(self, value: float) -> None:
        import heapq

        heapq.heappush(self._heap, value)

    def pop(self) -> float:
        import heapq

        if not self._heap:
            raise FoundationsError("MinHeap.pop: heap is empty")
        return heapq.heappop(self._heap)

    def peek(self) -> float:
        if not self._heap:
            raise FoundationsError("MinHeap.peek: heap is empty")
        return self._heap[0]

    def __len__(self) -> int:
        return len(self._heap)


class _Node[T]:
    __slots__ = ("next", "value")

    def __init__(self, value: T) -> None:
        self.value: T = value
        self.next: _Node[T] | None = None


class LinkedList[T]:
    """Singly linked list — ``append`` O(1) tail, ``to_list`` / iteration O(n)."""

    def __init__(self, items: Iterable[T] | None = None) -> None:
        self._head: _Node[T] | None = None
        self._tail: _Node[T] | None = None
        self._size = 0
        if items is not None:
            for item in items:
                self.append(item)

    def append(self, value: T) -> None:
        node = _Node(value)
        if self._tail is None:
            self._head = self._tail = node
        else:
            self._tail.next = node
            self._tail = node
        self._size += 1

    def head(self) -> T:
        if self._head is None:
            raise FoundationsError("LinkedList.head: list is empty")
        return self._head.value

    def to_list(self) -> list[T]:
        return list(iter(self))

    def __iter__(self) -> Iterator[T]:
        node = self._head
        while node is not None:
            yield node.value
            node = node.next

    def __len__(self) -> int:
        return self._size


class BinarySearchTree:
    """Unbalanced BST over numbers — ``insert`` / ``contains`` / ``inorder``."""

    class _BSTNode:
        __slots__ = ("left", "right", "value")

        def __init__(self, value: float) -> None:
            self.value = value
            self.left: BinarySearchTree._BSTNode | None = None
            self.right: BinarySearchTree._BSTNode | None = None

    def __init__(self, values: Iterable[float] | None = None) -> None:
        self._root: BinarySearchTree._BSTNode | None = None
        self._size = 0
        if values is not None:
            for value in values:
                self.insert(value)

    def insert(self, value: float) -> None:
        if self._root is None:
            self._root = self._BSTNode(value)
            self._size += 1
            return
        node = self._root
        while True:
            if value < node.value:
                if node.left is None:
                    node.left = self._BSTNode(value)
                    self._size += 1
                    return
                node = node.left
            elif value > node.value:
                if node.right is None:
                    node.right = self._BSTNode(value)
                    self._size += 1
                    return
                node = node.right
            else:
                return  # duplicate ignored — set semantics

    def contains(self, value: float) -> bool:
        node = self._root
        while node is not None:
            if value == node.value:
                return True
            node = node.left if value < node.value else node.right
        return False

    def inorder(self) -> list[float]:
        """Sorted ascending traversal (the BST invariant made visible)."""
        result: list[float] = []
        stack: list[BinarySearchTree._BSTNode] = []
        node = self._root
        while stack or node is not None:
            while node is not None:
                stack.append(node)
                node = node.left
            node = stack.pop()
            result.append(node.value)
            node = node.right
        return result

    def min(self) -> float:
        if self._root is None:
            raise FoundationsError("BinarySearchTree.min: tree is empty")
        node = self._root
        while node.left is not None:
            node = node.left
        return node.value

    def __len__(self) -> int:
        return self._size
