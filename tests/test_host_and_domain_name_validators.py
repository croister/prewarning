from validators.host_and_domain_name_validators import (
    is_hostname,
    is_hostname_or_ip,
    is_domain_name,
)


class TestIsHostname:
    def test_bare_hostname(self):
        assert is_hostname("db-server") is True
        assert is_hostname("localhost") is True

    def test_fqdn(self):
        assert is_hostname("db-server.local") is True
        assert is_hostname("db-server.company.se") is True
        assert is_hostname("example.com") is True

    def test_single_char(self):
        assert is_hostname("s") is True

    def test_invalid_tld_too_short(self):
        from validators.validation_error import ValidationError

        result = is_hostname("db-server.l")
        assert isinstance(result, ValidationError)

    def test_too_long(self):
        result = is_hostname("a" * 256)
        assert not result

    def test_starts_with_dash(self):
        result = is_hostname("-host")
        assert not result


class TestIsHostnameOrIP:
    def test_hostname(self):
        assert is_hostname_or_ip("db-server") is True
        assert is_hostname_or_ip("db-server.local") is True

    def test_ipv4(self):
        assert is_hostname_or_ip("127.0.0.1") is True

    def test_ipv6(self):
        assert is_hostname_or_ip("::1") is True
        assert is_hostname_or_ip("abcd:ef::12:3") is True
        assert is_hostname_or_ip("::ffff:192.168.2.123") is True
        assert is_hostname_or_ip("::192.168.2.123") is True

    def test_invalid(self):
        from validators.validation_error import ValidationError

        result = is_hostname_or_ip("abc.1.2.3")
        assert isinstance(result, ValidationError)
        result = is_hostname_or_ip("300.10.10.22")
        assert isinstance(result, ValidationError)

    def test_invalid_hostname_single_char_tld(self):
        result = is_hostname_or_ip("db-server.l")
        assert not result

    def test_invalid_hostname_too_short_tld(self):
        result = is_hostname_or_ip("example.x")
        assert not result


class TestIsDomainName:
    def test_valid(self):
        assert is_domain_name("db-server") is True
        assert is_domain_name("db-server.local") is True
        assert is_domain_name("db-server.company.se") is True
        assert is_domain_name("se") is True

    def test_single_char_invalid(self):
        from validators.validation_error import ValidationError

        result = is_domain_name("s")
        assert isinstance(result, ValidationError)

    def test_single_char_tld_invalid(self):
        result = is_domain_name("db-server.l")
        assert not result

    def test_too_long(self):
        result = is_domain_name("a" * 256)
        assert not result
