# -*- coding: utf-8 -*-

import logging
from pathlib import Path

from validators import LOGGER_NAME
from validators.validator_decorator import validator


BASE_DIR = Path(__file__).resolve().parent.parent.absolute()


def _to_path(value: str or Path) -> Path:
    """
    Validate if the given value is a valid path.

    :param str or Path value: The string to validate.
    """
    if issubclass(type(value), Path):
        path = value
    else:
        try:
            path = Path(value)
        except Exception as e:
            logging.getLogger(LOGGER_NAME).debug('_to_path: %s', e)
            raise

    try:
        if not path.is_absolute():
            path = BASE_DIR / path
        path = path.resolve()
    except Exception as e:
        logging.getLogger(LOGGER_NAME).debug('_to_path: %s', e)
        raise

    return path


@validator(message='Not a valid Path.')
def is_path(value: str or Path) -> bool:
    """
    Validate if the given value is a valid path.

    :param str or Path value: The string to validate.
    """
    try:
        _to_path(value)
    except Exception as e:
        logging.getLogger(LOGGER_NAME).debug('is_path: %s', e)
        return False

    return True


@validator(message='The path does not exist.')
def path_exists(value: str or Path) -> bool:
    """
    Validate if the given value is an existing path.

    :param str or Path value: The string to validate.
    """
    try:
        path = _to_path(value)
    except Exception as e:
        logging.getLogger(LOGGER_NAME).debug('path_exists: %s', e)
        return False

    if not path.exists():
        return False

    return True


@validator(message='The file does not exist.')
def file_exists(value: str or Path) -> bool:
    """
    Validate if the given value is an existing file path.

    :param str or Path value: The string to validate.
    """
    try:
        path = _to_path(value)
    except Exception as e:
        logging.getLogger(LOGGER_NAME).debug('file_exists: %s', e)
        return False

    if not path.exists():
        return False

    if not path.is_file():
        return False

    return True


@validator(message='The directory does not exist.')
def directory_exists(value: str or Path) -> bool:
    """
    Validate if the given value is an existing directory path.

    :param str or Path value: The string to validate.
    """
    try:
        path = _to_path(value)
    except Exception as e:
        logging.getLogger(LOGGER_NAME).debug('directory_exists: %s', e)
        return False

    if not path.exists():
        return False

    if not path.is_dir():
        return False

    return True
