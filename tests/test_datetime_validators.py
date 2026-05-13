from validators.datetime_validators import is_timestamp, is_date, is_time


class TestIsTimestamp:
    def test_valid(self):
        assert is_timestamp("2024-01-15 10:30:00.123456") is True

    def test_invalid_format(self):
        from validators.validation_error import ValidationError

        result = is_timestamp("2024-01-15 10:30:00")
        assert isinstance(result, ValidationError)

    def test_not_a_date(self):
        result = is_timestamp("not a date")
        assert not result

    def test_empty(self):
        result = is_timestamp("")
        assert not result


class TestIsDate:
    def test_valid(self):
        assert is_date("2024-01-15") is True
        assert is_date("2024-12-31") is True

    def test_invalid_format(self):
        from validators.validation_error import ValidationError

        result = is_date("15-01-2024")
        assert isinstance(result, ValidationError)

    def test_not_a_date(self):
        result = is_date("abc")
        assert not result


class TestIsTime:
    def test_valid(self):
        assert is_time("10:30:00") is True
        assert is_time("00:00:00") is True
        assert is_time("23:59:59") is True

    def test_invalid_format(self):
        from validators.validation_error import ValidationError

        result = is_time("10:30")
        assert isinstance(result, ValidationError)

    def test_not_a_time(self):
        result = is_time("abc")
        assert not result
