# -*- coding: utf-8 -*-

import logging
import sys

from validators import LOGGER_NAME
from validators.validator_decorator import validator


MAX_SIZE = sys.maxsize
MIN_SIZE = -sys.maxsize - 1


def _int(value: str, min_limit: int = MIN_SIZE, max_limit: int = MAX_SIZE) -> bool:
    """
    Validate if the given value is an int and is within the min and max limits.

    :param str value: The string to validate.
    :param int min_limit: The minimum allowed value.
    :param int max_limit: The maximum allowed value.
    """
    try:
        int_value = int(value)
        return min_limit <= int_value <= max_limit
    except TypeError or ValueError as e:
        logging.getLogger(LOGGER_NAME).debug('_int: %s', e)
        return False


@validator(message='Not an integer value.')
def is_int(value: str) -> bool:
    """
    Validate if the given value is an integer.

    :param str value: The string to validate.
    """
    result = _int(value)
    return result


@validator(message='Only positive integer values are allowed.')
def is_positive_int(value: str) -> bool:
    """
    Validate if the given value is a positive integer.

    :param str value: The string to validate.
    """
    result = _int(value, min_limit=1)
    return result


@validator(message='Only negative integer values are allowed.')
def is_negative_int(value: str) -> bool:
    """
    Validate if the given value is a positive integer.

    :param str value: The string to validate.
    """
    result = _int(value, max_limit=-1)
    return result


@validator(message='Negative integer values are not allowed.')
def is_not_negative_int(value: str) -> bool:
    """
    Validate if the given value is not a negative integer.

    :param str value: The string to validate.
    """
    result = _int(value, min_limit=0)
    return result


@validator(message='Positive integer values are not allowed.')
def is_not_positive_int(value: str) -> bool:
    """
    Validate if the given value is not a positive integer.

    :param str value: The string to validate.
    """
    result = _int(value, max_limit=0)
    return result
