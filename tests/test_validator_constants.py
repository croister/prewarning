from validators.constants import (
    DOMAIN_NAME_LABEL_PATTERN,
    DOMAIN_NAME_TLD_PATTERN,
    HOSTNAME_PATTERN,
    HOSTNAME_FQDN_PATTERN,
    DOMAIN_NAME_PATTERN,
)


class TestDomainNameLabelPattern:
    def test_valid_labels(self):
        assert DOMAIN_NAME_LABEL_PATTERN.match("a")
        assert DOMAIN_NAME_LABEL_PATTERN.match("example")
        assert DOMAIN_NAME_LABEL_PATTERN.match("my-host")
        assert DOMAIN_NAME_LABEL_PATTERN.match("a1b2c3")
        assert DOMAIN_NAME_LABEL_PATTERN.match("x" * 63)

    def test_invalid_labels(self):
        assert not DOMAIN_NAME_LABEL_PATTERN.match("")
        assert not DOMAIN_NAME_LABEL_PATTERN.match("-leading")
        assert not DOMAIN_NAME_LABEL_PATTERN.match("trailing-")
        assert not DOMAIN_NAME_LABEL_PATTERN.match("x" * 64)
        assert not DOMAIN_NAME_LABEL_PATTERN.match("has space")
        assert not DOMAIN_NAME_LABEL_PATTERN.match(".dot")


class TestDomainNameTLDPattern:
    def test_valid_tlds(self):
        assert DOMAIN_NAME_TLD_PATTERN.match("se")
        assert DOMAIN_NAME_TLD_PATTERN.match("com")
        assert DOMAIN_NAME_TLD_PATTERN.match("org")
        assert DOMAIN_NAME_TLD_PATTERN.match("x" * 63)

    def test_invalid_tlds(self):
        assert not DOMAIN_NAME_TLD_PATTERN.match("")
        assert not DOMAIN_NAME_TLD_PATTERN.match("1abc")
        assert not DOMAIN_NAME_TLD_PATTERN.match("-abc")
        assert not DOMAIN_NAME_TLD_PATTERN.match("x" * 64)


class TestHostnamePattern:
    def test_valid(self):
        assert HOSTNAME_PATTERN.match("a")
        assert HOSTNAME_PATTERN.match("localhost")
        assert HOSTNAME_PATTERN.match("db-server")

    def test_invalid(self):
        assert not HOSTNAME_PATTERN.match("")
        assert not HOSTNAME_PATTERN.match("-x")


class TestHostnameFQDNPattern:
    def test_valid(self):
        assert HOSTNAME_FQDN_PATTERN.match("example.com")
        assert HOSTNAME_FQDN_PATTERN.match("db.example.com")
        assert HOSTNAME_FQDN_PATTERN.match("a.b.c.se")
        assert HOSTNAME_FQDN_PATTERN.match("my-host.example.org")

    def test_invalid(self):
        assert not HOSTNAME_FQDN_PATTERN.match("localhost")
        assert not HOSTNAME_FQDN_PATTERN.match("")
        assert not HOSTNAME_FQDN_PATTERN.match(".com")
        assert not HOSTNAME_FQDN_PATTERN.match("a.")
        assert not HOSTNAME_FQDN_PATTERN.match("a.b.c")


class TestDomainNamePattern:
    def test_valid(self):
        assert DOMAIN_NAME_PATTERN.match("example.com")
        assert DOMAIN_NAME_PATTERN.match("sub.example.com")
        assert DOMAIN_NAME_PATTERN.match("se")
        assert DOMAIN_NAME_PATTERN.match("localhost")

    def test_invalid(self):
        assert not DOMAIN_NAME_PATTERN.match("")
        assert not DOMAIN_NAME_PATTERN.match(".com")
        assert not DOMAIN_NAME_PATTERN.match("a.")
        assert not DOMAIN_NAME_PATTERN.match("a.b.c")
        assert not DOMAIN_NAME_PATTERN.match("-x.y")
