# -*- coding: utf-8 -*-

from typing import Any


class _Singleton(type):
    """
    Defines a metaclass for singleton classes.
    """

    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(_Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

    @classmethod
    def has_instance(mcs) -> bool:
        return mcs in mcs._instances

    @classmethod
    def get_instance(mcs) -> Any:
        return mcs._instances[mcs]


class Singleton(_Singleton('SingletonMeta', (object,), {})):
    pass
