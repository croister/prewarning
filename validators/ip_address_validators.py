# -*- coding: utf-8 -*-

import ipaddress

from validators.validator_decorator import validator


@validator(message='Not a valid IP version 4 address.')
def is_ipv4(value: str) -> bool:
    """
    Validate if the given value is a valid IP version 4 address.

    Examples::
        >>> is_ipv4('127.0.0.1')
        True
        >>> is_ipv4('300.10.10.22')
        ValidationError(function=is_ipv4, message='Not a valid IP version 4 address.', args={'value': '300.10.10.22'})

    :param str value: The string to validate
    """
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False

    if not isinstance(address, ipaddress.IPv4Address):
        return False

    return True


@validator(message='Not a valid CIDR-notated IP version 4 address range.')
def is_ipv4_cidr(value: str) -> bool:
    """
    Validate if the given value is a valid CIDR-notated IP version 4 address range.

    Examples::
        >>> is_ipv4_cidr('192.168.2.0/32')
        True
        >>> is_ipv4_cidr('192.168.2.0')
        ValidationError(function=is_ipv4_cidr, message='Not a valid CIDR-notated IP version 4 address range.',
         args={'value': '192.168.2.0'})

    :param str value: The string to validate
    """
    try:
        ipv4_address, cidr = value.split('/', 2)
    except ValueError:
        return False

    if not is_ipv4(ipv4_address) or not cidr.isdigit():
        return False

    return 0 <= int(cidr) <= 32


@validator(message='Not a valid IP version 6 address.')
def is_ipv6(value: str) -> bool:
    """
    Validate if the given value is a valid IP version 6 address.

    Examples::
        >>> is_ipv6('abcd:ef::12:3')
        True
        >>> is_ipv6('::ffff:192.168.2.123')
        True
        >>> is_ipv6('::192.168.2.123')
        True
        >>> is_ipv6('abc.1.2.3')
        ValidationError(function=is_ipv6, message='Not a valid IP version 6 address.', args={'value': 'abc.1.2.3'})

    :param str value: The string to validate
    """
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False

    if not isinstance(address, ipaddress.IPv6Address):
        return False

    return True


@validator(message='Not a valid CIDR-notated IP version 6 address range.')
def is_ipv6_cidr(value: str) -> bool:
    """
    Validate if the given value is a valid CIDR-notated IP version 6 address range.

    Examples::
        >>> is_ipv6_cidr('::123/128')
        True
        >>> is_ipv6_cidr('::123')
        ValidationError(function=is_ipv6_cidr, message='Not a valid CIDR-notated IP version 6 address range.',
         args={'value': '::1'})

    :param str value: The string to validate
    """
    try:
        ipv6_address, cidr = value.split('/', 2)
    except ValueError:
        return False

    if not is_ipv6(ipv6_address) or not cidr.isdigit():
        return False

    return 0 <= int(cidr) <= 128


@validator(message='Not a valid IP address.')
def is_ip(value: str) -> bool:
    """
    Validate if the given value is a valid IP address, both version 4 and 6 are accepted.

    Examples::
        >>> is_ip('127.0.0.1')
        True
        >>> is_ip('300.10.10.22')
        ValidationError(function=is_ip, message='Not a valid IP address.', args={'value': '300.10.10.22'})
        >>> is_ip('abcd:ef::12:3')
        True
        >>> is_ip('::ffff:192.168.2.123')
        True
        >>> is_ip('::192.168.2.123')
        True
        >>> is_ip('abc.1.2.3')
        ValidationError(function=is_ip, message='Not a valid IP address.', args={'value': 'abc.1.2.3'})

    :param str value: The string to validate
    """
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False

    return True


@validator(message='Not a valid CIDR-notated IP address range.')
def is_ip_cidr(value: str) -> bool:
    """
    Validate if the given value is a valid CIDR-notated IP address range, both version 4 and 6 are accepted.

    Examples::
        >>> is_ip_cidr('192.168.2.0/32')
        True
        >>> is_ip_cidr('192.168.2.0')
        ValidationError(function=is_ipv4_cidr, message='Not a valid CIDR-notated IP address range.',
         args={'value': '192.168.2.0'})
        >>> is_ip_cidr('::123/128')
        True
        >>> is_ip_cidr('::123')
        ValidationError(function=is_ip_cidr, message='Not a valid CIDR-notated IP address range.',
         args={'value': '::1'})

    :param str value: The string to validate
    """
    return is_ipv4_cidr(value) or is_ipv6_cidr(value)
