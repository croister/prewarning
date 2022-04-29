# -*- coding: utf-8 -*-

import logging
from datetime import datetime

from validators import LOGGER_NAME
from validators.validator_decorator import validator


def _timestamp_pattern(value: str, datetime_pattern: str) -> bool:
    """
    Validate the given value using the given datetime pattern.

    :param str value: The string to validate.
    :param str datetime_pattern: The datetime pattern to validate with.
    """
    try:
        parsed = datetime.strptime(value, datetime_pattern)
        return type(parsed) == datetime
    except TypeError or ValueError as e:
        logging.getLogger(LOGGER_NAME).debug('timestamp_pattern: %s', e)
        return False


TIMESTAMP_PATTERN = '%Y-%m-%d %H:%M:%S.%f'


@validator(message='Not a valid timestamp.')
def is_timestamp(value: str) -> bool:
    """
    Validate if the given value is a valid timestamp.

    :param str value: The string to validate.
    """
    result = _timestamp_pattern(value, TIMESTAMP_PATTERN)
    return result


DATE_PATTERN = '%Y-%m-%d'


@validator(message='Not a valid date.')
def is_date(value: str) -> bool:
    """
    Validate if the given value is a valid date.

    :param str value: The string to validate.
    """
    result = _timestamp_pattern(value, DATE_PATTERN)
    return result


TIME_PATTERN = '%H:%M:%S'


@validator(message='Not a valid timestamp.')
def is_time(value: str) -> bool:
    """
    Validate if the given value is a valid time.

    :param str value: The string to validate.
    """
    result = _timestamp_pattern(value, TIME_PATTERN)
    return result
