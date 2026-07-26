from validators.validator_decorator import func_args_as_dict, validator


def dummy_validator(value):
    return value > 0


class TestFuncArgsAsDict:
    def test_positional_only(self):
        def f(a, b):
            pass

        result = func_args_as_dict(f, (1, 2), {})
        assert result == {"a": 1, "b": 2}

    def test_mixed_args(self):
        def f(a, b, c=None):
            pass

        result = func_args_as_dict(f, (1,), {"b": 2, "c": 3})
        assert result == {"a": 1, "b": 2, "c": 3}


class TestValidatorDecorator:
    def test_valid_returns_true(self):
        decorated = validator(message="Must be positive")(dummy_validator)
        assert decorated(5) is True

    def test_invalid_returns_validation_error(self):
        decorated = validator(message="Must be positive")(dummy_validator)
        result = decorated(0)
        from validators.validation_error import ValidationError

        assert isinstance(result, ValidationError)
        assert result.message == "Must be positive"
        assert result.value == 0

    def test_default_message(self):
        decorated = validator()(dummy_validator)
        result = decorated(0)
        assert "dummy_validator" in result.message

    def test_preserves_function_name(self):
        decorated = validator(message="x")(dummy_validator)
        assert decorated.__name__ == "dummy_validator"

    def test_multiple_args(self):
        def two_arg(a, b):
            return a == b

        decorated = validator(message="Must match")(two_arg)
        result = decorated(1, 2)
        from validators.validation_error import ValidationError

        assert isinstance(result, ValidationError)
        assert result.a == 1
        assert result.b == 2
