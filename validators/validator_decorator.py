# -*- coding: utf-8 -*-

import inspect
import itertools
from typing import Callable

from decorator import decorator

from validators.validation_error import ValidationError


def func_args_as_dict(func: Callable, args, kwargs):
    """
    Return given function's positional and key value arguments as an ordered
    dictionary.
    """
    _getargspec = inspect.getfullargspec

    arg_names = list(
        dict.fromkeys(
            itertools.chain(
                _getargspec(func)[0],
                kwargs.keys()
            )
        )
    )
    return dict(
        list(zip(arg_names, args)) +
        list(kwargs.items())
    )


@decorator
def validator(function, message=None, *args, **kwargs):
    """
    A decorator that makes given function a validator.

    Whenever the given function is called and returns ``False`` value
    this decorator returns :class:`ValidationError` object.

    Example::

        >>> import ipaddress
        ...
        ... @validator(message='Not a valid IP address.')
        ... def is_ip(value: str) -> bool:
        ...     try:
        ...         address = ipaddress.ip_address(value)
        ...     except ValueError:
        ...         return False
        ...
        ...     if not isinstance(address, ipaddress.IPv6Address):
        ...         return False
        ...
        ...     return True

        >>> is_ip('127.0.0.1')
        True

        >>> is_ip('300.10.10.22')
        ValidationError(function=is_ip, message='Not a valid IP address.', args={'value': '300.10.10.22'})

    :param Callable function: The function to decorate
    :param str message: The validation error message
    :param args: positional function arguments
    :param kwargs: key value function arguments
    """
    result = function(*args, **kwargs)
    if not result:
        if message is None:
            message = 'Not valid according to the "{}" validator.'.format(function.__name__)
        return ValidationError(function, message, func_args_as_dict(function, args, kwargs))
    return True
