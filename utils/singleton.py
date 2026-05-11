# -*- coding: utf-8 -*-

from typing import Any


class _Singleton(type):
    """
    Defines a metaclass for singleton classes.
    """

    _instances: dict[type, Any] = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(_Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

    def has_instance(cls) -> bool:
        return cls in cls._instances

    def get_instance(cls) -> Any:
        return cls._instances[cls]


class Singleton(metaclass=_Singleton):
    pass
