from validators.url_validators import (
    is_http_or_https_url,
    is_http_url,
    is_https_url,
    is_url,
)


class TestIsURL:
    def test_valid_https(self):
        assert is_url("https://example.com") is True

    def test_valid_http(self):
        assert is_url("http://example.com") is True

    def test_valid_ftp(self):
        assert is_url("ftp://files.example.com") is True

    def test_valid_with_path(self):
        assert is_url("https://example.com/path/to/page") is True

    def test_valid_with_port(self):
        assert is_url("https://example.com:8080/path") is True

    def test_invalid_scheme(self):
        from validators.validation_error import ValidationError

        result = is_url("invalid://example.com")
        assert isinstance(result, ValidationError)

    def test_no_scheme(self):
        result = is_url("example.com")
        assert not result

    def test_empty(self):
        result = is_url("")
        assert not result


class TestIsHttpURL:
    def test_valid(self):
        assert is_http_url("http://example.com") is True

    def test_https_rejected(self):
        from validators.validation_error import ValidationError

        result = is_http_url("https://example.com")
        assert isinstance(result, ValidationError)

    def test_ftp_rejected(self):
        result = is_http_url("ftp://example.com")
        assert not result

    def test_with_path(self):
        assert is_http_url("http://example.com/page") is True


class TestIsHttpsURL:
    def test_valid(self):
        assert is_https_url("https://example.com") is True

    def test_http_rejected(self):
        from validators.validation_error import ValidationError

        result = is_https_url("http://example.com")
        assert isinstance(result, ValidationError)

    def test_with_query(self):
        assert is_https_url("https://example.com/?q=1") is True


class TestIsHttpOrHttpsURL:
    def test_http(self):
        assert is_http_or_https_url("http://example.com") is True

    def test_https(self):
        assert is_http_or_https_url("https://example.com") is True

    def test_ftp_rejected(self):
        from validators.validation_error import ValidationError

        result = is_http_or_https_url("ftp://example.com")
        assert isinstance(result, ValidationError)

    def test_invalid_scheme(self):
        result = is_http_or_https_url("ssh://example.com")
        assert not result
