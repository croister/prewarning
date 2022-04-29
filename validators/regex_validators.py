# -*- coding: utf-8 -*-

import logging
import re
from re import Pattern

from validators import LOGGER_NAME
from validators.validator_decorator import validator


def _regex(value: str, regex_pattern: str or Pattern, flags: int = 0) -> bool:
    """
    Validate the given value using the given regex pattern.

    :param str value: The string to validate.
    :param str or Pattern regex_pattern: The regex pattern to validate with.
    :param int flags: The regex flags to use, for example re.IGNORECASE. Ignored if `regex` is not a string.
    """
    if isinstance(regex_pattern, str):
        regex_pattern = re.compile(regex_pattern, flags)
    try:
        match = regex_pattern.match(value)
        return bool(match)
    except TypeError as e:
        logging.getLogger(LOGGER_NAME).debug('regex: %s', e)
        return False


CONTROL_IDS_PATTERN = re.compile(r'^(\d+)(\s(\d+))*$')


@validator(message='Not a valid list of Control IDs.')
def is_control_ids(value: str) -> bool:
    """
    Validate if the given value is a list of Control IDs separated by spaces.

    :param str value: The string to validate.
    """
    result = _regex(value, CONTROL_IDS_PATTERN)
    return result


PUNCH_ID_PATTERN = re.compile(r'^(\d+)_(\d+)_(\d+)$')


@validator(message='Not a valid Punch ID.')
def is_punch_id(value: str) -> bool:
    """
    Validate if the given value is a Punch ID.

    :param str value: The string to validate.
    """
    result = _regex(value, PUNCH_ID_PATTERN)
    return result
