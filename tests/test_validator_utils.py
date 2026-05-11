from validators.validator_utils import to_unicode


class TestToUnicode:
    def test_none_returns_none(self):
        assert to_unicode(None) is None

    def test_bytes_decoded(self):
        assert to_unicode(b'hello') == 'hello'

    def test_str_passthrough(self):
        assert to_unicode('already string') == 'already string'

    def test_int_converted(self):
        assert to_unicode(42) == '42'

    def test_float_converted(self):
        assert to_unicode(3.14) == '3.14'

    def test_bytes_utf8(self):
        assert to_unicode(b'\xc3\xa4pple') == 'äpple'

    def test_bytes_other_charset(self):
        assert to_unicode(b'\xe4pple', charset='latin-1') == 'äpple'
