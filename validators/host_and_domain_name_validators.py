# -*- coding: utf-8 -*-

from validators.constants import HOSTNAME_PATTERN, HOSTNAME_FQDN_PATTERN, DOMAIN_NAME_PATTERN
from validators.ip_address_validators import is_ip
from validators.validator_decorator import validator
from validators.validator_utils import to_unicode


@validator(message='Not a valid hostname.')
def is_hostname(value: str) -> bool:
    """
    Validate if the given value is a valid hostname.
    Both bare hostnames and Fully Qualified Domain Names (FQDN) are accepted.

    Examples::
        >>> is_hostname('db-server')
        True
        >>> is_hostname('db-server.local')
        True
        >>> is_hostname('db-server.company.se')
        True
        >>> is_hostname('db-server.l')
        ValidationError(function=is_hostname, message='Not a valid hostname.', args={'value': 'db-server.l'})
        >>> is_hostname('se')
        True
        >>> is_hostname('s')
        True

    :param str value: The string to validate
    """
    try:
        # To handle internationalized (IDN) hostnames
        encoded_value = to_unicode(value).encode('idna').decode('ascii')
    except (UnicodeError, AttributeError):
        return False

    # A FQDN has a max length of 255 characters
    if len(encoded_value) > 255:
        return False

    if HOSTNAME_PATTERN.match(encoded_value):
        return True

    if HOSTNAME_FQDN_PATTERN.match(encoded_value):
        return True

    return False


@validator(message='Not a valid hostname or IP address.')
def is_hostname_or_ip(value: str):
    """
    Validate if the given value is a valid hostname or IP address.

    Examples::
        >>> is_hostname_or_ip('db-server')
        True
        >>> is_hostname_or_ip('db-server.local')
        True
        >>> is_hostname_or_ip('db-server.company.se')
        True
        >>> is_hostname_or_ip('db-server.l')
        ValidationError(function=is_hostname_or_ip, message='Not a valid hostname.', args={'value': 'db-server.l'})
        >>> is_hostname_or_ip('se')
        ValidationError(function=is_hostname_or_ip, message='Not a valid hostname.', args={'value': 'se'})
        >>> is_hostname_or_ip('127.0.0.1')
        True
        >>> is_hostname_or_ip('300.10.10.22')
        ValidationError(function=is_hostname_or_ip, message='Not a valid IP address.', args={'value': '300.10.10.22'})
        >>> is_hostname_or_ip('abcd:ef::12:3')
        True
        >>> is_hostname_or_ip('::ffff:192.168.2.123')
        True
        >>> is_hostname_or_ip('::192.168.2.123')
        True
        >>> is_hostname_or_ip('abc.1.2.3')
        ValidationError(function=is_hostname_or_ip, message='Not a valid IP address.', args={'value': 'abc.1.2.3'})

    :param str value: The string to validate
    """
    if is_ip(value):
        return True

    if is_hostname(value):
        return True

    return False


@validator(message='Not a valid domain name.')
def is_domain_name(value: str) -> bool:
    """
    Validate if the given value is a valid domain name.

    Examples::
        >>> is_domain_name('db-server')
        True
        >>> is_domain_name('db-server.local')
        True
        >>> is_domain_name('db-server.company.se')
        True
        >>> is_domain_name('db-server.l')
        ValidationError(function=is_domain_name, message='Not a valid hostname.', args={'value': 'db-server.l'})
        >>> is_domain_name('se')
        True
        >>> is_domain_name('s')
        ValidationError(function=is_domain_name, message='Not a valid hostname.', args={'value': 's'})

    :param str value: The string to validate
    """
    try:
        # To handle internationalized (IDN) hostnames
        encoded_value = to_unicode(value).encode('idna').decode('ascii')
    except (UnicodeError, AttributeError):
        return False

    # A FQDN has a max length of 255 characters
    if len(encoded_value) > 255:
        return False

    if DOMAIN_NAME_PATTERN.match(encoded_value):
        return True

    return False
