from validators.number_validators import (
    is_int,
    is_positive_int,
    is_negative_int,
    is_not_negative_int,
    is_not_positive_int,
)


class TestIsInt:
    def test_valid_int(self):
        assert is_int('42') is True
        assert is_int('0') is True
        assert is_int('-10') is True

    def test_invalid(self):
        from validators.validation_error import ValidationError
        result = is_int('abc')
        assert isinstance(result, ValidationError)
        result = is_int('12.5')
        assert not result
        result = is_int('')
        assert not result


class TestIsPositiveInt:
    def test_valid(self):
        assert is_positive_int('1') is True
        assert is_positive_int('100') is True

    def test_zero_invalid(self):
        from validators.validation_error import ValidationError
        result = is_positive_int('0')
        assert isinstance(result, ValidationError)

    def test_negative_invalid(self):
        result = is_positive_int('-1')
        assert not result


class TestIsNegativeInt:
    def test_valid(self):
        assert is_negative_int('-1') is True
        assert is_negative_int('-100') is True

    def test_zero_invalid(self):
        result = is_negative_int('0')
        assert not result

    def test_positive_invalid(self):
        from validators.validation_error import ValidationError
        result = is_negative_int('1')
        assert isinstance(result, ValidationError)


class TestIsNotNegativeInt:
    def test_valid(self):
        assert is_not_negative_int('0') is True
        assert is_not_negative_int('5') is True

    def test_negative_invalid(self):
        from validators.validation_error import ValidationError
        result = is_not_negative_int('-1')
        assert isinstance(result, ValidationError)


class TestIsNotPositiveInt:
    def test_valid(self):
        assert is_not_positive_int('0') is True
        assert is_not_positive_int('-5') is True

    def test_positive_invalid(self):
        from validators.validation_error import ValidationError
        result = is_not_positive_int('1')
        assert isinstance(result, ValidationError)
