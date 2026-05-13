from validators.validation_error import ValidationError


def dummy_func():
    pass


class TestValidationError:
    def test_repr(self):
        err = ValidationError(dummy_func, "Something went wrong", {"value": "abc"})
        expected = "ValidationError(function=dummy_func, message=Something went wrong, args={'value': 'abc'})"
        assert repr(err) == expected

    def test_str(self):
        err = ValidationError(dummy_func, "Error message", {"x": 1})
        assert str(err) == repr(err)

    def test_bool_false(self):
        err = ValidationError(dummy_func, "msg", {"a": 1})
        assert not err

    def test_is_exception(self):
        err = ValidationError(dummy_func, "msg", {"a": 1})
        assert isinstance(err, Exception)

    def test_attributes_set(self):
        err = ValidationError(dummy_func, "msg", {"key": "val", "num": 42})
        assert err.key == "val"
        assert err.num == 42
        assert err.message == "msg"
        assert err.function == dummy_func
