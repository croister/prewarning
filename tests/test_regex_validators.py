from validators.regex_validators import is_control_ids, is_punch_id


class TestIsControlIds:
    def test_single_id(self):
        assert is_control_ids('123') is True

    def test_multiple_ids(self):
        assert is_control_ids('123 456 789') is True

    def test_invalid_empty(self):
        result = is_control_ids('')
        from validators.validation_error import ValidationError
        assert isinstance(result, ValidationError)

    def test_invalid_letters(self):
        result = is_control_ids('123 abc')
        assert not result

    def test_invalid_trailing_space(self):
        result = is_control_ids('123 ')
        assert not result

    def test_invalid_special_chars(self):
        result = is_control_ids('123,456')
        assert not result


class TestIsPunchId:
    def test_valid(self):
        assert is_punch_id('123_456_789') is True

    def test_invalid_no_underscores(self):
        result = is_punch_id('123456')
        assert not result

    def test_invalid_letters(self):
        result = is_punch_id('abc_456_789')
        assert not result

    def test_invalid_missing_part(self):
        result = is_punch_id('123_456')
        assert not result

    def test_invalid_empty(self):
        result = is_punch_id('')
        assert not result

    def test_valid_large_numbers(self):
        assert is_punch_id('999999_888888_777777') is True
