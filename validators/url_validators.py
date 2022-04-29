# -*- coding: utf-8 -*-

import logging

from imurl import URL

from validators import LOGGER_NAME
from validators.host_and_domain_name_validators import is_hostname_or_ip
from validators.validator_decorator import validator


SCHEMES = [
    'acap',
    'afp',
    'dict',
    'dns',
    'ftp',
    'git',
    'gopher',
    'hdl',
    'http',
    'https',
    'imap',
    'ipp',
    'ipps',
    'irc',
    'ircs',
    'ldap',
    'ldaps',
    'mms',
    'msrp',
    'mtqp',
    'nfs',
    'nntp',
    'nntps',
    'pop',
    'prospero',
    'redis',
    'rsync',
    'rtsp',
    'rtsps',
    'rtspu',
    'sftp',
    'sip',
    'sips',
    'smb',
    'snews',
    'snmp',
    'ssh',
    'svn',
    'telnet',
    'tftp',
    'ventrilo',
    'vnc',
    'wais',
    'ws',
    'wss',
    'xmpp',
]


@validator(message='Not a valid URL.')
def is_url(value: str) -> bool:
    """
    Validate if the given value is a valid URL.

    :param str value: The string to validate.
    """
    try:

        url = URL(value)

        if url.scheme not in SCHEMES:
            return False

        if not is_hostname_or_ip(url.host):
            return False

        return True
    except Exception as e:
        logging.getLogger(LOGGER_NAME).debug('is_url: %s', e)
        return False


@validator(message='Not a valid http URL.')
def is_http_url(value: str) -> bool:
    """
    Validate if the given value is a valid http URL.

    :param str value: The string to validate.
    """
    try:

        url = URL(value)

        if url.scheme != 'http':
            return False

        if not is_hostname_or_ip(url.host):
            return False

        return True
    except Exception as e:
        logging.getLogger(LOGGER_NAME).debug('is_http_url: %s', e)
        return False


@validator(message='Not a valid https URL.')
def is_https_url(value: str) -> bool:
    """
    Validate if the given value is a valid https URL.

    :param str value: The string to validate.
    """
    try:

        url = URL(value)

        if url.scheme != 'https':
            return False

        if not is_hostname_or_ip(url.host):
            return False

        return True
    except Exception as e:
        logging.getLogger(LOGGER_NAME).debug('is_https_url: %s', e)
        return False


@validator(message='Not a valid http or https URL.')
def is_http_or_https_url(value: str) -> bool:
    """
    Validate if the given value is a valid http or https URL.

    :param str value: The string to validate.
    """
    try:

        url = URL(value)

        if url.scheme not in ['http', 'https']:
            return False

        if not is_hostname_or_ip(url.host):
            return False

        return True
    except Exception as e:
        logging.getLogger(LOGGER_NAME).debug('is_http_or_https_url: %s', e)
        return False
