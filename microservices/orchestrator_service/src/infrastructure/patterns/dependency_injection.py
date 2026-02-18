"""حاوية حقن تبعيات بسيطة تلتزم بالتصميم الواضح والخالي من النوع العام."""

import contextlib
import inspect
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class DIContainer:
    """حاوية مركزية لتسجيل الخدمات وإنشائها بطريقة آمنة."""

    def __init__(self):
        self._services: dict[type, type[object]] = {}
        self._factories: dict[type, Callable[..., object]] = {}
        self._singletons: dict[type, object] = {}

    def register(self, interface: type[T], implementation: type[T] | T) -> None:
        """يسجل تطبيق خدمة سواء كان صنفًا أو مثيلًا جاهزًا."""
        if inspect.isclass(implementation):
            self._services[interface] = implementation
        else:
            self._singletons[interface] = implementation

    def register_factory(self, interface: type[T], factory: Callable[..., T]) -> None:
        """يسجل دالة مصنع لإنشاء الخدمة عند الطلب."""
        self._factories[interface] = factory

    def register_singleton(self, interface: type[T], instance: T) -> None:
        """يسجل مثيلًا جاهزًا ليعمل كعنصر وحيد."""
        self._singletons[interface] = instance

    def resolve(self, interface: type[T]) -> T:
        """يعيد مثيل الخدمة بعد تطبيق قواعد التسجيل المختلفة."""
        if interface in self._singletons:
            return self._singletons[interface]  # type: ignore[return-value]

        if interface in self._factories:
            return self._factories[interface]()

        if interface in self._services:
            implementation = self._services[interface]
            if inspect.isclass(implementation):
                return self._create_instance(implementation)  # type: ignore[arg-type]
            return implementation  # type: ignore[return-value]

        raise ValueError(f"Service not registered: {interface}")

    def _create_instance(self, cls: type[T]) -> T:
        """يبني مثيلًا مع حقن التبعيات في الباني إن أمكن."""
        sig = inspect.signature(cls.__init__)
        params: dict[str, object] = {}

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            if param.annotation != inspect.Parameter.empty:
                try:
                    params[param_name] = self.resolve(param.annotation)
                except ValueError:
                    if param.default != inspect.Parameter.empty:
                        params[param_name] = param.default
                    else:
                        raise

        return cls(**params)

    def clear(self) -> None:
        """يمسح جميع التسجيلات لإعادة تهيئة الحاوية."""
        self._services.clear()
        self._factories.clear()
        self._singletons.clear()


def get_container() -> DIContainer:
    """يعيد الحاوية العالمية لحقن التبعيات."""
    return _global_container


def inject[T](func: Callable[..., T]) -> Callable[..., T]:
    """مُزخرف يقوم بحقن التبعيات تلقائيًا في التابع الهدف."""

    def wrapper(*args: object, **kwargs: object) -> T:
        sig = inspect.signature(func)
        container = get_container()

        for param_name, param in sig.parameters.items():
            if param_name not in kwargs and param.annotation != inspect.Parameter.empty:
                with contextlib.suppress(ValueError):
                    kwargs[param_name] = container.resolve(param.annotation)

        return func(*args, **kwargs)  # type: ignore[arg-type]

    return wrapper


_global_container = DIContainer()
