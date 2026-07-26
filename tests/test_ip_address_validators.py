from validators.ip_address_validators import (
    is_ip,
    is_ip_cidr,
    is_ipv4,
    is_ipv4_cidr,
    is_ipv6,
    is_ipv6_cidr,
)


class TestIsIPv4:
    def test_valid(self):
        assert is_ipv4("127.0.0.1") is True
        assert is_ipv4("192.168.1.1") is True
        assert is_ipv4("0.0.0.0") is True
        assert is_ipv4("255.255.255.255") is True

    def test_invalid(self):
        from validators.validation_error import ValidationError

        result = is_ipv4("300.10.10.22")
        assert isinstance(result, ValidationError)
        result = is_ipv4("abc")
        assert not result
        result = is_ipv4("::1")
        assert not result


class TestIsIPv4CIDR:
    def test_valid(self):
        assert is_ipv4_cidr("192.168.2.0/32") is True
        assert is_ipv4_cidr("10.0.0.0/8") is True
        assert is_ipv4_cidr("0.0.0.0/0") is True

    def test_invalid_mask(self):
        from validators.validation_error import ValidationError

        result = is_ipv4_cidr("192.168.2.0/33")
        assert isinstance(result, ValidationError)

    def test_no_cidr(self):
        result = is_ipv4_cidr("192.168.2.0")
        assert not result

    def test_invalid_ip(self):
        result = is_ipv4_cidr("300.10.10.22/24")
        assert not result


class TestIsIPv6:
    def test_valid(self):
        assert is_ipv6("::1") is True
        assert is_ipv6("abcd:ef::12:3") is True
        assert is_ipv6("::ffff:192.168.2.123") is True
        assert is_ipv6("2001:db8::1") is True

    def test_invalid(self):
        from validators.validation_error import ValidationError

        result = is_ipv6("abc.1.2.3")
        assert isinstance(result, ValidationError)
        result = is_ipv6("127.0.0.1")
        assert not result


class TestIsIPv6CIDR:
    def test_valid(self):
        assert is_ipv6_cidr("::123/128") is True
        assert is_ipv6_cidr("::/0") is True
        assert is_ipv6_cidr("2001:db8::/32") is True

    def test_invalid_mask(self):
        from validators.validation_error import ValidationError

        result = is_ipv6_cidr("::123/129")
        assert isinstance(result, ValidationError)

    def test_no_cidr(self):
        result = is_ipv6_cidr("::123")
        assert not result


class TestIsIP:
    def test_valid_v4(self):
        assert is_ip("127.0.0.1") is True
        assert is_ip("192.168.1.1") is True

    def test_valid_v6(self):
        assert is_ip("::1") is True
        assert is_ip("2001:db8::1") is True

    def test_invalid(self):
        from validators.validation_error import ValidationError

        result = is_ip("abc.1.2.3")
        assert isinstance(result, ValidationError)
        result = is_ip("not_an_ip")
        assert not result


class TestIsIPCIDR:
    def test_valid_v4(self):
        assert is_ip_cidr("192.168.2.0/32") is True

    def test_valid_v6(self):
        assert is_ip_cidr("::123/128") is True

    def test_invalid(self):
        from validators.validation_error import ValidationError

        result = is_ip_cidr("192.168.2.0")
        assert isinstance(result, ValidationError)
