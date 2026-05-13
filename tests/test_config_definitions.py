from unittest.mock import MagicMock, patch
from configparser import ConfigParser
from pathlib import Path
import pytest

from utils.config_definitions import (
    ConfigOptionDefinition,
    ConfigSectionOptionDefinition,
    ConfigSectionEnableType,
    ConfigSectionDefinition,
    config_section_definitions_sort_key,
    VerificationResult,
    VerificationError,
    ConfigVerifierDefinition,
    SelectionData,
    SelectionType,
    SelectionResult,
    SelectionError,
    ConfigSelectorDefinition,
    RuntimeStateGroup,
    RuntimeStateOptionDefinition,
)


# ---------------------------------------------------------------------------
# ConfigOptionDefinition
# ---------------------------------------------------------------------------


class TestConfigOptionDefinition:
    def test_minimal_init(self):
        d = ConfigOptionDefinition("opt1", "Option 1", str, "A string option")
        assert d.name == "opt1"
        assert d.display_name == "Option 1"
        assert d.value_type is str
        assert d.description == "A string option"
        assert d.mandatory is False
        assert d.default_value is None
        assert d.valid_values is None
        assert d.valid_values_gen is None
        assert d.enabled_by is None
        assert d.validator is None
        assert d.verifier is None
        assert d.selector is None

    def test_full_init(self):
        valid_values = [1, 2]
        d = ConfigOptionDefinition(
            "opt2", "Option 2", int, "An int", True, 1, valid_values
        )
        assert d.name == "opt2"
        assert d.value_type is int
        assert d.mandatory is True
        assert d.default_value == 1
        assert d.valid_values == [1, 2]

    def test_str_repr(self):
        d = ConfigOptionDefinition("x", "X", str, "desc")
        assert "ConfigOptionDefinition" in repr(d)
        s = str(d)
        assert "ConfigOptionDefinition" in s

    # --- _validate_type ---

    def test_bool_must_have_default(self):
        with pytest.raises(ValueError, match="bool must have a default value"):
            ConfigOptionDefinition("b", "B", bool, "desc")

    def test_bool_cannot_have_valid_values(self):
        with pytest.raises(ValueError, match="bool can not have valid values"):
            ConfigOptionDefinition(
                "b", "B", bool, "desc", default_value=True, valid_values=[True, False]
            )

    def test_bool_cannot_have_valid_values_gen(self):
        with pytest.raises(ValueError, match="bool can not have valid values"):
            ConfigOptionDefinition(
                "b",
                "B",
                bool,
                "desc",
                default_value=True,
                valid_values_gen=lambda: [True, False],
            )

    def test_bool_ok_with_default_no_valid_values(self):
        d = ConfigOptionDefinition("b", "B", bool, "desc", default_value=False)
        assert d.value_type is bool

    # --- get_valid_values ---

    def test_get_valid_values_none(self):
        d = ConfigOptionDefinition("x", "X", str, "desc")
        assert d.get_valid_values() is None

    def test_get_valid_values_from_list(self):
        d = ConfigOptionDefinition("x", "X", str, "desc", valid_values=["a", "b"])
        assert d.get_valid_values() == ["a", "b"]

    def test_get_valid_values_from_gen(self):
        d = ConfigOptionDefinition(
            "x", "X", str, "desc", valid_values_gen=lambda: ["c", "d"]
        )
        assert d.get_valid_values() == ["c", "d"]

    def test_get_valid_values_both_set_raises(self):
        with pytest.raises(ValueError, match="Both valid_values and valid_values_gen"):
            ConfigOptionDefinition(
                "x",
                "X",
                str,
                "desc",
                valid_values=["a"],
                valid_values_gen=lambda: ["b"],
            )

    # --- set_verifier / set_selector ---

    def test_set_verifier(self):
        d = ConfigOptionDefinition("x", "X", str, "desc")
        v = MagicMock()
        d.set_verifier(v)
        assert d.verifier is v

    def test_set_verifier_raises_on_duplicate(self):
        d = ConfigOptionDefinition("x", "X", str, "desc")
        d.set_verifier(MagicMock())
        with pytest.raises(ValueError, match="Verifier is already defined"):
            d.set_verifier(MagicMock())

    def test_set_selector(self):
        d = ConfigOptionDefinition("x", "X", str, "desc")
        s = MagicMock()
        d.set_selector(s)
        assert d.selector is s

    def test_set_selector_raises_on_duplicate(self):
        d = ConfigOptionDefinition("x", "X", str, "desc")
        d.set_selector(MagicMock())
        with pytest.raises(ValueError, match="Selector is already defined"):
            d.set_selector(MagicMock())

    # --- get_initial_option_value ---

    def test_get_initial_option_value_no_default(self):
        d = ConfigOptionDefinition("x", "X", str, "desc")
        assert d.get_initial_option_value() == ""

    def test_get_initial_option_value_with_default(self):
        d = ConfigOptionDefinition("x", "X", int, "desc", default_value=99)
        assert d.get_initial_option_value() == "99"

    def test_get_initial_option_value_bool(self):
        d = ConfigOptionDefinition("x", "X", bool, "desc", default_value=True)
        assert d.get_initial_option_value() == "True"

    # --- _convert_value ---

    def test_convert_none(self):
        d = ConfigOptionDefinition("x", "X", str, "desc")
        assert d._convert_value("val", None) is None

    def test_convert_empty_str(self):
        d = ConfigOptionDefinition("x", "X", str, "desc")
        assert d._convert_value("val", "") is None

    def test_convert_str(self):
        d = ConfigOptionDefinition("x", "X", str, "desc")
        assert d._convert_value("val", 123) == "123"

    def test_convert_int(self):
        d = ConfigOptionDefinition("x", "X", int, "desc")
        assert d._convert_value("val", "42") == 42

    def test_convert_int_from_str_raises(self):
        d = ConfigOptionDefinition("x", "X", int, "desc")
        with pytest.raises(ValueError):
            d._convert_value("val", "not_a_number")

    def test_convert_float(self):
        d = ConfigOptionDefinition("x", "X", float, "desc")
        assert d._convert_value("val", "3.14") == 3.14

    def test_convert_bool(self):
        d = ConfigOptionDefinition("x", "X", bool, "desc", default_value=False)
        assert d._convert_value("val", True) is True
        assert d._convert_value("val", False) is False

    def test_convert_bool_nonempty_str(self):
        d = ConfigOptionDefinition("x", "X", bool, "desc", default_value=False)
        assert d._convert_value("val", "hello") is True

    def test_convert_bool_empty_str(self):
        d = ConfigOptionDefinition("x", "X", bool, "desc", default_value=False)
        assert d._convert_value("val", "") is None

    def test_convert_path(self):
        d = ConfigOptionDefinition("x", "X", Path, "desc")
        result = d._convert_value("val", "/some/path")
        assert isinstance(result, Path)
        assert str(result) == "\\some\\path" or str(result) == "/some/path"

    def test_convert_unknown_type(self):
        d = ConfigOptionDefinition("x", "X", list, "desc")
        with pytest.raises(ValueError, match="expected to have the type"):
            d._convert_value("val", [1, 2])

    # --- validate ---

    def test_validate_mandatory_none(self):
        d = ConfigOptionDefinition("x", "X", str, "desc", mandatory=True)
        errors = d.validate(None)
        assert errors == ["The value is mandatory."]

    def test_validate_optional_none(self):
        d = ConfigOptionDefinition("x", "X", str, "desc")
        assert d.validate(None) == []

    def test_validate_conversion_error(self):
        d = ConfigOptionDefinition("x", "X", int, "desc")
        errors = d.validate("not_a_number")
        assert len(errors) == 1
        assert (
            "expected to have the type" in errors[0] or "invalid" in errors[0].lower()
        )

    def test_validate_valid_value(self):
        d = ConfigOptionDefinition("x", "X", str, "desc", valid_values=["a", "b"])
        assert d.validate("a") == []

    def test_validate_invalid_value(self):
        d = ConfigOptionDefinition("x", "X", str, "desc", valid_values=["a", "b"])
        errors = d.validate("c")
        assert len(errors) == 1
        assert "not in the valid values" in errors[0]

    def test_validate_with_validator_callable(self):
        def my_validator(val):
            if val != "ok":
                return VerificationResult("not ok", status=False)
            return VerificationResult("ok")

        d = ConfigOptionDefinition("x", "X", str, "desc", validator=my_validator)
        assert d.validate("ok") == []
        errors = d.validate("bad")
        assert errors == ["not ok"]

    def test_validate_validator_returns_true(self):
        d = ConfigOptionDefinition(
            "x",
            "X",
            str,
            "desc",
            validator=lambda v: VerificationResult("ok", status=True),
        )
        assert d.validate("any") == []

    def test_validate_default_flag(self):
        d = ConfigOptionDefinition("x", "X", str, "desc", valid_values=["a"])
        errors = d.validate("b", is_default=True)
        assert "DEFAULT value" in errors[0]

    # --- _validate_value_type ---

    def test_validate_value_type_ok(self):
        d = ConfigOptionDefinition("x", "X", str, "desc")
        assert d._validate_value_type("val", "hello") == []

    def test_validate_value_type_wrong(self):
        d = ConfigOptionDefinition("x", "X", int, "desc")
        errors = d._validate_value_type("val", "not_int")
        assert len(errors) == 1
        assert "expected to have the type" in errors[0]

    # --- _validate_value ---

    def test_validate_value_when_none_and_not_mandatory(self):
        d = ConfigOptionDefinition("x", "X", str, "desc")
        assert d._validate_value("val", None) == []

    def test_validate_value_by_type_str(self):
        d = ConfigOptionDefinition("x", "X", str, "desc")
        assert d._validate_value("val", "hello") == []

    def test_validate_value_by_type_int(self):
        d = ConfigOptionDefinition("x", "X", int, "desc")
        assert d._validate_value("val", 42) == []

    def test_validate_value_by_type_float(self):
        d = ConfigOptionDefinition("x", "X", float, "desc")
        assert d._validate_value("val", 3.14) == []

    def test_validate_value_by_type_bool(self):
        d = ConfigOptionDefinition("x", "X", bool, "desc", default_value=False)
        assert d._validate_value("val", True) == []

    def test_validate_value_by_type_path(self):
        d = ConfigOptionDefinition("x", "X", Path, "desc")
        assert d._validate_value("val", Path("/tmp")) == []

    # --- get_value / get_value_str / set_value with SectionProxy ---

    @pytest.fixture
    def config_with_section(self):
        cp = ConfigParser()
        cp.add_section("test")
        return cp["test"]

    def test_get_value_str_from_section(self, config_with_section):
        d = ConfigOptionDefinition("opt", "Opt", str, "desc", default_value="fallback")
        config_with_section["opt"] = "hello"
        assert d.get_value(config_with_section) == "hello"

    def test_get_value_str_fallback(self, config_with_section):
        d = ConfigOptionDefinition("opt", "Opt", str, "desc", default_value="fallback")
        assert d.get_value(config_with_section) == "fallback"

    def test_get_value_str_empty_returns_none(self, config_with_section):
        d = ConfigOptionDefinition("opt", "Opt", str, "desc", default_value="fallback")
        config_with_section["opt"] = ""
        assert d.get_value(config_with_section) is None

    def test_get_value_int(self, config_with_section):
        d = ConfigOptionDefinition("num", "Num", int, "desc", default_value=0)
        config_with_section["num"] = "42"
        assert d.get_value(config_with_section) == 42

    def test_get_value_int_error_returns_none(self, config_with_section):
        d = ConfigOptionDefinition("num", "Num", int, "desc", default_value=0)
        config_with_section["num"] = "not_int"
        assert d.get_value(config_with_section) is None

    def test_get_value_float(self, config_with_section):
        d = ConfigOptionDefinition("f", "F", float, "desc", default_value=0.0)
        config_with_section["f"] = "3.14"
        assert d.get_value(config_with_section) == 3.14

    def test_get_value_bool_true(self, config_with_section):
        d = ConfigOptionDefinition("b", "B", bool, "desc", default_value=False)
        config_with_section["b"] = "yes"
        assert d.get_value(config_with_section) is True

    def test_get_value_bool_error_returns_none(self, config_with_section):
        d = ConfigOptionDefinition("b", "B", bool, "desc", default_value=False)
        value = d.get_value(config_with_section)
        assert value is None or value is False

    def test_get_value_path(self, config_with_section):
        d = ConfigOptionDefinition("p", "P", Path, "desc")
        config_with_section["p"] = "/some/path"
        result = d.get_value(config_with_section)
        assert isinstance(result, Path)

    def test_get_value_path_none(self, config_with_section):
        d = ConfigOptionDefinition("p", "P", Path, "desc")
        assert d.get_value(config_with_section) is None

    def test_get_value_unknown_type(self):
        d = ConfigOptionDefinition("x", "X", list, "desc")
        cp = ConfigParser()
        with pytest.raises(ValueError, match="Unknown value type"):
            d.get_value(cp["DEFAULT"])

    def test_get_value_str_empty_string_returns_none(self, config_with_section):
        d = ConfigOptionDefinition("opt", "Opt", str, "desc", default_value="fallback")
        config_with_section["opt"] = ""
        assert d.get_value(config_with_section) is None

    def test_get_value_str_whitespace_not_handled(self, config_with_section):
        d = ConfigOptionDefinition("opt", "Opt", str, "desc")
        config_with_section["opt"] = "  "
        assert d.get_value(config_with_section) == "  "

    def test_get_value_str_default_fallback(self, config_with_section):
        d = ConfigOptionDefinition("opt", "Opt", str, "desc", default_value="default")
        config_with_section["opt"] = "explicit"
        assert d.get_value(config_with_section) == "explicit"

    def test_get_value_str_default_when_missing(self, config_with_section):
        d = ConfigOptionDefinition("opt", "Opt", str, "desc", default_value="default")
        assert d.get_value(config_with_section) == "default"

    def test_get_value_path_empty_returns_none(self, config_with_section):
        d = ConfigOptionDefinition("p", "P", Path, "desc")
        config_with_section["p"] = ""
        assert d.get_value(config_with_section) is None

    def test_get_value_path_invalid_returns_none(self, config_with_section):
        d = ConfigOptionDefinition("p", "P", Path, "desc")
        config_with_section["p"] = "/valid"
        with patch.object(Path, "__new__", side_effect=Exception("bad path")):
            assert d.get_value(config_with_section) is None

    def test_get_value_path_fallback_default(self, config_with_section):
        d = ConfigOptionDefinition(
            "p", "P", Path, "desc", default_value=Path("/default")
        )
        config_with_section["p"] = "/custom"
        result = d.get_value(config_with_section)
        assert isinstance(result, Path)
        assert str(result) == "\\custom" or str(result) == "/custom"

    def test_get_value_str_none_fallback_none(self, config_with_section):
        d = ConfigOptionDefinition("opt", "Opt", str, "desc", default_value=None)
        assert d.get_value(config_with_section) is None

    def test_get_value_int_none_fallback_none(self, config_with_section):
        d = ConfigOptionDefinition("num", "Num", int, "desc", default_value=None)
        assert d.get_value(config_with_section) is None

    def test_get_value_float_none_fallback_none(self, config_with_section):
        d = ConfigOptionDefinition("f", "F", float, "desc", default_value=None)
        assert d.get_value(config_with_section) is None

    def test_get_value_bool_absent_returns_fallback(self, config_with_section):
        d = ConfigOptionDefinition("b", "B", bool, "desc", default_value=True)
        assert d.get_value(config_with_section) is True

    def test_get_value_str_section_get_exception(self, config_with_section):
        d = ConfigOptionDefinition("opt", "Opt", str, "desc", default_value="def")
        with patch.object(config_with_section, "get", side_effect=ValueError):
            assert d.get_value(config_with_section) is None

    def test_get_value_int_get_exception(self, config_with_section):
        d = ConfigOptionDefinition("num", "Num", int, "desc", default_value=0)
        with patch.object(config_with_section, "getint", side_effect=ValueError):
            assert d.get_value(config_with_section) is None

    def test_get_value_float_get_exception(self, config_with_section):
        d = ConfigOptionDefinition("f", "F", float, "desc", default_value=0.0)
        with patch.object(config_with_section, "getfloat", side_effect=ValueError):
            assert d.get_value(config_with_section) is None

    def test_get_value_bool_get_exception(self, config_with_section):
        d = ConfigOptionDefinition("b", "B", bool, "desc", default_value=False)
        with patch.object(config_with_section, "getboolean", side_effect=ValueError):
            assert d.get_value(config_with_section) is None

    def test_get_value_path_get_exception(self, config_with_section):
        d = ConfigOptionDefinition("p", "P", Path, "desc")
        with patch.object(config_with_section, "get", side_effect=ValueError):
            assert d.get_value(config_with_section) is None

    def test_get_value_path_get_exception_returns_none(self, config_with_section):
        d = ConfigOptionDefinition("p", "P", Path, "desc")
        with patch.object(config_with_section, "get", side_effect=ValueError):
            assert d.get_value(config_with_section) is None

    def test_get_value_str_non_string_error(self, config_with_section):
        d = ConfigOptionDefinition("opt", "Opt", str, "desc", default_value="def")
        with patch.object(config_with_section, "get", return_value=123):
            value = d.get_value(config_with_section)
            assert value is None or value == 123

    def test_get_value_int_none_value(self, config_with_section):
        d = ConfigOptionDefinition("num", "Num", int, "desc", default_value=0)
        with patch.object(config_with_section, "getint", return_value=None):
            assert d.get_value(config_with_section) is None

    def test_get_value_float_zero(self, config_with_section):
        d = ConfigOptionDefinition("f", "F", float, "desc", default_value=0.0)
        config_with_section["f"] = "0"
        assert d.get_value(config_with_section) == 0.0

    def test_get_value_bool_false_string(self, config_with_section):
        d = ConfigOptionDefinition("b", "B", bool, "desc", default_value=True)
        config_with_section["b"] = "false"
        assert d.get_value(config_with_section) is False

    def test_get_value_str_empty_fallback_default(self, config_with_section):
        d = ConfigOptionDefinition("opt", "Opt", str, "desc", default_value="default")
        config_with_section["opt"] = ""
        assert d.get_value(config_with_section) is None

    def test_get_value_str_no_default_empty_config(self, config_with_section):
        d = ConfigOptionDefinition("opt", "Opt", str, "desc", default_value=None)
        assert d.get_value(config_with_section) is None

    def test_get_value_str_with_none_default_no_value_in_section(
        self, config_with_section
    ):
        d = ConfigOptionDefinition("opt", "Opt", str, "desc", default_value=None)
        assert d.get_value(config_with_section) is None

    def test_get_value_str_with_default_and_section_value(self, config_with_section):
        d = ConfigOptionDefinition("opt", "Opt", str, "desc", default_value="fallback")
        config_with_section["opt"] = "explicit"
        result = d.get_value(config_with_section)
        assert result == "explicit"

    def test_get_value_int_positive(self, config_with_section):
        d = ConfigOptionDefinition("num", "Num", int, "desc", default_value=0)
        config_with_section["num"] = "123"
        assert d.get_value(config_with_section) == 123

    def test_get_value_int_negative(self, config_with_section):
        d = ConfigOptionDefinition("num", "Num", int, "desc", default_value=0)
        config_with_section["num"] = "-5"
        assert d.get_value(config_with_section) == -5

    def test_get_value_float_with_int_string(self, config_with_section):
        d = ConfigOptionDefinition("f", "F", float, "desc", default_value=0.0)
        config_with_section["f"] = "42"
        assert d.get_value(config_with_section) == 42.0

    def test_get_value_bool_yes(self, config_with_section):
        d = ConfigOptionDefinition("b", "B", bool, "desc", default_value=False)
        config_with_section["b"] = "yes"
        assert d.get_value(config_with_section) is True

    def test_get_value_bool_on(self, config_with_section):
        d = ConfigOptionDefinition("b", "B", bool, "desc", default_value=False)
        config_with_section["b"] = "on"
        assert d.get_value(config_with_section) is True

    def test_get_value_bool_1(self, config_with_section):
        d = ConfigOptionDefinition("b", "B", bool, "desc", default_value=False)
        config_with_section["b"] = "1"
        assert d.get_value(config_with_section) is True

    def test_get_value_bool_no(self, config_with_section):
        d = ConfigOptionDefinition("b", "B", bool, "desc", default_value=True)
        config_with_section["b"] = "no"
        assert d.get_value(config_with_section) is False

    def test_get_value_bool_off(self, config_with_section):
        d = ConfigOptionDefinition("b", "B", bool, "desc", default_value=True)
        config_with_section["b"] = "off"
        assert d.get_value(config_with_section) is False

    def test_get_value_bool_0(self, config_with_section):
        d = ConfigOptionDefinition("b", "B", bool, "desc", default_value=True)
        config_with_section["b"] = "0"
        assert d.get_value(config_with_section) is False

    def test_get_value_str_trailing_whitespace_preserved(self, config_with_section):
        d = ConfigOptionDefinition("opt", "Opt", str, "desc", default_value=None)
        config_with_section["opt"] = "hello "
        assert d.get_value(config_with_section) == "hello "

    def test_get_value_str_leading_whitespace_preserved(self, config_with_section):
        d = ConfigOptionDefinition("opt", "Opt", str, "desc", default_value=None)
        config_with_section["opt"] = " hello"
        assert d.get_value(config_with_section) == " hello"

    def test_get_value_str_special_chars(self, config_with_section):
        d = ConfigOptionDefinition("opt", "Opt", str, "desc", default_value=None)
        config_with_section["opt"] = "a=b&c=d"
        assert d.get_value(config_with_section) == "a=b&c=d"

    def test_get_value_str_very_long(self, config_with_section):
        d = ConfigOptionDefinition("opt", "Opt", str, "desc", default_value=None)
        long_str = "x" * 10000
        config_with_section["opt"] = long_str
        assert d.get_value(config_with_section) == long_str

    def test_get_value_str_unicode(self, config_with_section):
        d = ConfigOptionDefinition("opt", "Opt", str, "desc", default_value=None)
        config_with_section["opt"] = "\u00e9\u00e0\u00fc"
        assert d.get_value(config_with_section) == "\u00e9\u00e0\u00fc"

    def test_get_value_int_large(self, config_with_section):
        d = ConfigOptionDefinition("num", "Num", int, "desc", default_value=0)
        config_with_section["num"] = "2147483647"
        assert d.get_value(config_with_section) == 2147483647

    def test_get_value_float_scientific(self, config_with_section):
        d = ConfigOptionDefinition("f", "F", float, "desc", default_value=0.0)
        config_with_section["f"] = "1e10"
        assert d.get_value(config_with_section) == 1e10

    def test_get_value_float_negative(self, config_with_section):
        d = ConfigOptionDefinition("f", "F", float, "desc", default_value=0.0)
        config_with_section["f"] = "-3.14"
        assert d.get_value(config_with_section) == -3.14

    def test_get_value_float_inf(self, config_with_section):
        d = ConfigOptionDefinition("f", "F", float, "desc", default_value=0.0)
        config_with_section["f"] = "inf"
        result = d.get_value(config_with_section)
        import math

        assert result == float("inf") or math.isinf(result)

    def test_get_value_float_nan(self, config_with_section):
        d = ConfigOptionDefinition("f", "F", float, "desc", default_value=0.0)
        config_with_section["f"] = "nan"
        result = d.get_value(config_with_section)
        import math

        assert math.isnan(result)

    def test_get_value_path_with_default_and_section_value(self, config_with_section):
        d = ConfigOptionDefinition(
            "p", "P", Path, "desc", default_value=Path("/default")
        )
        config_with_section["p"] = "/custom"
        result = d.get_value(config_with_section)
        assert isinstance(result, Path)
        assert str(result) == "\\custom" or str(result) == "/custom"

    def test_get_value_path_no_key_returns_default(self, config_with_section):
        d = ConfigOptionDefinition(
            "p", "P", Path, "desc", default_value=Path("/default")
        )
        result = d.get_value(config_with_section)
        assert isinstance(result, Path)

    def test_get_value_path_exception_on_construction(self, config_with_section):
        d = ConfigOptionDefinition("p", "P", Path, "desc")
        config_with_section["p"] = "/valid"
        with patch.object(Path, "__new__", side_effect=Exception("fail")):
            assert d.get_value(config_with_section) is None

    def test_get_value_str_value_as_non_string(self, config_with_section):
        d = ConfigOptionDefinition("opt", "Opt", str, "desc", default_value=None)
        with patch.object(config_with_section, "get", return_value=42):
            result = d.get_value(config_with_section)
            assert result is None or result == 42

    def test_get_value_str_empty_string_explicit(self, config_with_section):
        d = ConfigOptionDefinition("opt", "Opt", str, "desc", default_value=None)
        config_with_section["opt"] = ""
        assert d.get_value(config_with_section) is None

    def test_get_value_str_value_as_empty_string_returns_none(
        self, config_with_section
    ):
        d = ConfigOptionDefinition("opt", "Opt", str, "desc", default_value=None)
        config_with_section["opt"] = ""
        assert d.get_value(config_with_section) is None

    def test_get_value_str_section_key_missing(self, config_with_section):
        d = ConfigOptionDefinition("opt", "Opt", str, "desc", default_value=None)
        assert d.get_value(config_with_section) is None

    def test_get_value_str_fallback_used_when_missing(self, config_with_section):
        d = ConfigOptionDefinition("opt", "Opt", str, "desc", default_value="default")
        assert d.get_value(config_with_section) == "default"

    def test_get_value_unknown_type_raises(self):
        d = ConfigOptionDefinition("x", "X", bytes, "desc")
        cp = ConfigParser()
        with pytest.raises(ValueError, match="Unknown value type"):
            d.get_value(cp["DEFAULT"])

    def test_set_value(self, config_with_section):
        d = ConfigOptionDefinition("opt", "Opt", str, "desc")
        d.set_value(config_with_section, "new_value")
        assert config_with_section["opt"] == "new_value"

    def test_set_value_int(self, config_with_section):
        d = ConfigOptionDefinition("num", "Num", int, "desc")
        d.set_value(config_with_section, 42)
        assert config_with_section["num"] == "42"

    def test_set_value_path(self, config_with_section):
        d = ConfigOptionDefinition("p", "P", Path, "desc")
        d.set_value(config_with_section, Path("/tmp"))
        assert config_with_section["p"] == "\\tmp" or config_with_section["p"] == "/tmp"

    def test_set_value_bool(self, config_with_section):
        d = ConfigOptionDefinition("b", "B", bool, "desc", default_value=False)
        d.set_value(config_with_section, True)
        assert config_with_section["b"] == "True"

    def test_set_value_none(self, config_with_section):
        d = ConfigOptionDefinition("opt", "Opt", str, "desc")
        d.set_value(config_with_section, None)
        assert config_with_section["opt"] == "None"

    def test_get_value_str(self, config_with_section):
        d = ConfigOptionDefinition("opt", "Opt", str, "desc")
        config_with_section["opt"] = "val"
        assert d.get_value_str(config_with_section) == "val"

    def test_get_value_str_none(self, config_with_section):
        d = ConfigOptionDefinition("opt", "Opt", str, "desc")
        assert d.get_value_str(config_with_section) == ""

    # --- is_enabled ---

    def test_is_enabled_no_enabled_by(self, config_with_section):
        d = ConfigOptionDefinition("x", "X", str, "desc")
        assert d.is_enabled(config_with_section) is True

    def test_is_enabled_enabled_by_true(self, config_with_section):
        parent = ConfigOptionDefinition(
            "parent", "Parent", bool, "desc", default_value=False
        )
        child = ConfigOptionDefinition("child", "Child", str, "desc", enabled_by=parent)
        assert child.is_enabled(config_with_section) is False

    def test_is_enabled_by_raises_on_none(self, config_with_section):
        d = ConfigOptionDefinition("x", "X", str, "desc")
        with pytest.raises(ValueError, match='"enabled_by" is not configured'):
            d._is_enabled_by(config_with_section)

    def test_is_enabled_by_bool_true(self, config_with_section):
        parent = ConfigOptionDefinition("p", "P", bool, "desc", default_value=True)
        config_with_section["p"] = "yes"
        child = ConfigOptionDefinition("c", "C", str, "desc", enabled_by=parent)
        assert child.is_enabled(config_with_section) is True

    def test_is_enabled_by_bool_false(self, config_with_section):
        parent = ConfigOptionDefinition("p", "P", bool, "desc", default_value=False)
        config_with_section["p"] = "no"
        child = ConfigOptionDefinition("c", "C", str, "desc", enabled_by=parent)
        assert child.is_enabled(config_with_section) is False

    def test_enabled_by_must_be_bool(self):
        parent = ConfigOptionDefinition("p", "P", bool, "desc", default_value=True)
        child = ConfigOptionDefinition("c", "C", str, "desc", enabled_by=parent)
        assert child.enabled_by is parent
        assert child in parent.enables

    # --- validator callable that does not return VerificationResult ---

    def test_validate_validator_returns_non_verification_result(self):
        d = ConfigOptionDefinition(
            "x", "X", str, "desc", validator=lambda v: "accepted"
        )
        result = d.validate("val")
        assert result == []

    def test_validate_validator_none_and_valid_values_none(self):
        d = ConfigOptionDefinition("x", "X", int, "desc")
        assert d.validate(42) == []

    def test_validate_validator_with_valid_values_list(self):
        d = ConfigOptionDefinition("x", "X", str, "desc", valid_values=["a", "b", "c"])
        assert d.validate("a") == []
        errors = d.validate("d")
        assert len(errors) == 1
        assert "not in the valid values" in errors[0]

    def test_validate_validator_with_valid_values_gen(self):
        d = ConfigOptionDefinition(
            "x", "X", str, "desc", valid_values_gen=lambda: ["x", "y"]
        )
        assert d.validate("x") == []
        errors = d.validate("z")
        assert len(errors) == 1
        assert "not in the valid values" in errors[0]

    def test_validate_empty_string_for_str_type(self):
        d = ConfigOptionDefinition("x", "X", str, "desc")
        assert d.validate("") == []

    def test_validate_none_for_non_mandatory(self):
        d = ConfigOptionDefinition("x", "X", str, "desc", mandatory=False)
        assert d.validate(None) == []

    def test_validate_none_for_mandatory_returns_error(self):
        d = ConfigOptionDefinition("x", "X", str, "desc", mandatory=True)
        errors = d.validate(None)
        assert errors == ["The value is mandatory."]

    def test_validate_type_mismatch(self):
        d = ConfigOptionDefinition("x", "X", int, "desc")
        errors = d.validate("abc")
        assert len(errors) >= 1

    def test_validate_valid_values_override_validator(self):
        validator = MagicMock()
        d = ConfigOptionDefinition(
            "x", "X", str, "desc", valid_values=["a", "b"], validator=validator
        )
        d.validate("a")
        validator.assert_not_called()

    def test_validate_only_validator_called_when_no_valid_values(self):
        validator = MagicMock(return_value=VerificationResult("ok"))
        d = ConfigOptionDefinition("x", "X", str, "desc", validator=validator)
        d.validate("val")
        validator.assert_called_once_with("val")

    def test_validate_default_value_flag_true(self):
        d = ConfigOptionDefinition("x", "X", str, "desc", valid_values=["a"])
        errors = d.validate("b", is_default=True)
        assert "DEFAULT value" in errors[0]

    def test_validate_mandatory_with_valid_value(self):
        d = ConfigOptionDefinition(
            "x", "X", str, "desc", mandatory=True, valid_values=["a"]
        )
        assert d.validate("a") == []

    def test_validate_mandatory_with_invalid_value(self):
        d = ConfigOptionDefinition(
            "x", "X", str, "desc", mandatory=True, valid_values=["a"]
        )
        errors = d.validate("b")
        assert len(errors) == 1

    # --- _convert_value edge cases ---

    def test_convert_str_with_numeric(self):
        d = ConfigOptionDefinition("x", "X", str, "desc")
        assert d._convert_value("val", 42) == "42"

    def test_convert_str_with_float(self):
        d = ConfigOptionDefinition("x", "X", str, "desc")
        assert d._convert_value("val", 3.14) == "3.14"

    def test_convert_str_with_bool(self):
        d = ConfigOptionDefinition("x", "X", str, "desc")
        assert d._convert_value("val", True) == "True"

    def test_convert_int_from_float_string(self):
        d = ConfigOptionDefinition("x", "X", int, "desc")
        with pytest.raises(ValueError):
            d._convert_value("val", "3.14")

    def test_convert_float_from_int(self):
        d = ConfigOptionDefinition("x", "X", float, "desc")
        assert d._convert_value("val", 42) == 42.0

    def test_convert_bool_from_int(self):
        d = ConfigOptionDefinition("x", "X", bool, "desc", default_value=False)
        assert d._convert_value("val", 0) is False
        assert d._convert_value("val", 1) is True

    def test_convert_path_from_none(self):
        d = ConfigOptionDefinition("x", "X", Path, "desc")
        assert d._convert_value("val", None) is None

    def test_convert_path_from_empty_str(self):
        d = ConfigOptionDefinition("x", "X", Path, "desc")
        assert d._convert_value("val", "") is None

    def test_convert_value_name_in_error(self):
        d = ConfigOptionDefinition("x", "X", int, "desc")
        with pytest.raises(ValueError) as exc:
            d._convert_value("myvalue", "not_int")
        assert "myvalue" in str(exc.value)

    def test_convert_value_name_in_error_float(self):
        d = ConfigOptionDefinition("x", "X", float, "desc")
        with pytest.raises(ValueError) as exc:
            d._convert_value("custom_name", "abc")
        assert "custom_name" in str(exc.value)

    def test_convert_path_from_path(self):
        d = ConfigOptionDefinition("x", "X", Path, "desc")
        result = d._convert_value("val", Path("/already/path"))
        assert isinstance(result, Path)

    def test_convert_bool_empty_str_not_none(self):
        d = ConfigOptionDefinition("x", "X", bool, "desc", default_value=False)
        assert d._convert_value("val", "") is None


# ---------------------------------------------------------------------------
# ConfigSectionOptionDefinition
# ---------------------------------------------------------------------------


class TestConfigSectionOptionDefinition:
    def test_init(self):
        opt = ConfigOptionDefinition("o", "O", str, "d")
        section_opt = ConfigSectionOptionDefinition("sect", opt)
        assert section_opt.section_name == "sect"
        assert section_opt.option_definition is opt

    def test_str_repr(self):
        opt = ConfigOptionDefinition("o", "O", str, "d")
        section_opt = ConfigSectionOptionDefinition("sect", opt)
        assert "ConfigSectionOptionDefinition" in repr(section_opt)
        assert "sect" in str(section_opt)
        assert "o" in str(section_opt)


# ---------------------------------------------------------------------------
# ConfigSectionEnableType
# ---------------------------------------------------------------------------


class TestConfigSectionEnableType:
    def test_values(self):
        assert ConfigSectionEnableType.ALWAYS.value == "Always"
        assert ConfigSectionEnableType.IF_ENABLED.value == "If enabled"
        assert ConfigSectionEnableType.IF_REQUIRED.value == "If required"

    def test_members(self):
        assert ConfigSectionEnableType.ALWAYS in ConfigSectionEnableType
        assert ConfigSectionEnableType.IF_ENABLED in ConfigSectionEnableType
        assert ConfigSectionEnableType.IF_REQUIRED in ConfigSectionEnableType


# ---------------------------------------------------------------------------
# ConfigSectionDefinition
# ---------------------------------------------------------------------------


class TestConfigSectionDefinition:
    def test_minimal_init(self):
        s = ConfigSectionDefinition("sect1", "Section 1")
        assert s.name == "sect1"
        assert s.display_name == "Section 1"
        assert s.option_definitions == {}
        assert s.enable_type == ConfigSectionEnableType.ALWAYS
        assert s.requires == []
        assert s.enabled_by is None
        assert s.required_by == []

    def test_init_with_options(self):
        opt = ConfigOptionDefinition("o", "O", str, "d")
        s = ConfigSectionDefinition("s", "S", [opt])
        assert s.option_definitions == {"o": opt}

    def test_init_with_requires(self):
        other = ConfigSectionDefinition("other", "Other")
        s = ConfigSectionDefinition("s", "S", requires=[other])
        assert other in s.requires

    def test_str_repr(self):
        s = ConfigSectionDefinition("s", "S")
        assert "ConfigSectionDefinition" in repr(s)
        assert "s" in str(s)

    def test_sort_key(self):
        s = ConfigSectionDefinition("mysql", "MySQL", sort_key_prefix=200)
        assert s.sort_key() == "200 mysql"

    def test_sort_key_default(self):
        s = ConfigSectionDefinition("x", "X")
        assert s.sort_key() == "100 x"

    def test_add_option_definition(self):
        s = ConfigSectionDefinition("s", "S")
        opt = ConfigOptionDefinition("o", "O", str, "d")
        s.add_option_definition(opt)
        assert s.option_definitions == {"o": opt}

    def test_add_option_definition_duplicate_raises(self):
        s = ConfigSectionDefinition("s", "S")
        opt = ConfigOptionDefinition("o", "O", str, "d")
        s.add_option_definition(opt)
        with pytest.raises(ValueError, match="already exists"):
            s.add_option_definition(opt)

    def test_set_enabled_by(self):
        s = ConfigSectionDefinition("s", "S")
        opt = ConfigOptionDefinition("o", "O", bool, "d", default_value=False)
        section_opt = ConfigSectionOptionDefinition("other", opt)
        s.set_enabled_by(section_opt)
        assert s.enabled_by is section_opt

    def test_set_enabled_by_duplicate_raises(self):
        s = ConfigSectionDefinition("s", "S")
        opt = ConfigOptionDefinition("o", "O", bool, "d", default_value=False)
        section_opt = ConfigSectionOptionDefinition("o", opt)
        s.set_enabled_by(section_opt)
        with pytest.raises(ValueError, match="Enabled by is already defined"):
            s.set_enabled_by(section_opt)

    def test_add_required_by(self):
        s1 = ConfigSectionDefinition("s1", "S1")
        s2 = ConfigSectionDefinition("s2", "S2")
        s2.add_required_by(s1)
        assert s1 in s2.required_by

    def test_add_required_by_duplicate_raises(self):
        s1 = ConfigSectionDefinition("s1", "S1")
        s2 = ConfigSectionDefinition("s2", "S2")
        s2.add_required_by(s1)
        with pytest.raises(ValueError, match="already required"):
            s2.add_required_by(s1)

    def test_get_initial_config_section_empty(self):
        s = ConfigSectionDefinition("s", "S")
        assert s.get_initial_config_section() == {}

    def test_get_initial_config_section_with_options(self):
        o1 = ConfigOptionDefinition("o1", "O1", str, "d", default_value="v1")
        o2 = ConfigOptionDefinition("o2", "O2", int, "d", default_value=42)
        s = ConfigSectionDefinition("s", "S", [o1, o2])
        result = s.get_initial_config_section()
        assert result == {"o1": "v1", "o2": "42"}

    def test_get_initial_config_section_no_default(self):
        o = ConfigOptionDefinition("o", "O", str, "d")
        s = ConfigSectionDefinition("s", "S", [o])
        assert s.get_initial_config_section() == {"o": ""}

    def test_is_enabled_always(self):
        s = ConfigSectionDefinition("s", "S")
        assert s.is_enabled({}) is True

    def test_is_enabled_unknown_type(self):
        s = ConfigSectionDefinition("s", "S")
        s.enable_type = "UNKNOWN"
        assert s.is_enabled({}) is False

    def test_is_enabled_if_enabled_no_enabled_by(self):
        s = ConfigSectionDefinition(
            "s", "S", enable_type=ConfigSectionEnableType.IF_ENABLED
        )
        with pytest.raises(
            ValueError, match="not configured for the configuration section"
        ):
            s.is_enabled({})

    def test_is_enabled_if_enabled_none_value(self):
        parent_opt = ConfigOptionDefinition("p", "P", bool, "d", default_value=False)
        section_opt = ConfigSectionOptionDefinition("other_sect", parent_opt)
        s = ConfigSectionDefinition(
            "s", "S", enable_type=ConfigSectionEnableType.IF_ENABLED
        )
        s.set_enabled_by(section_opt)
        cp = ConfigParser()
        config_sections = {"other_sect": cp["DEFAULT"]}
        assert s.is_enabled(config_sections) is False

    def test_is_enabled_if_enabled_bool_true(self):
        parent_opt = ConfigOptionDefinition("p", "P", bool, "d", default_value=True)
        section_opt = ConfigSectionOptionDefinition("other_sect", parent_opt)
        s = ConfigSectionDefinition(
            "s", "S", enable_type=ConfigSectionEnableType.IF_ENABLED
        )
        s.set_enabled_by(section_opt)
        cp = ConfigParser()
        cp["DEFAULT"]["p"] = "yes"
        config_sections = {"other_sect": cp["DEFAULT"]}
        assert s.is_enabled(config_sections) is True

    def test_is_enabled_if_enabled_bool_false(self):
        parent_opt = ConfigOptionDefinition("p", "P", bool, "d", default_value=False)
        section_opt = ConfigSectionOptionDefinition("other_sect", parent_opt)
        s = ConfigSectionDefinition(
            "s", "S", enable_type=ConfigSectionEnableType.IF_ENABLED
        )
        s.set_enabled_by(section_opt)
        cp = ConfigParser()
        cp["DEFAULT"]["p"] = "no"
        config_sections = {"other_sect": cp["DEFAULT"]}
        assert s.is_enabled(config_sections) is False

    def test_is_enabled_if_enabled_str_matching(self):
        parent_opt = ConfigOptionDefinition("p", "P", str, "d")
        section_opt = ConfigSectionOptionDefinition("other_sect", parent_opt)
        child = ConfigSectionDefinition(
            "child", "Child", enable_type=ConfigSectionEnableType.IF_ENABLED
        )
        child.set_enabled_by(section_opt)
        cp = ConfigParser()
        cp["DEFAULT"]["p"] = "child"
        config_sections = {"other_sect": cp["DEFAULT"]}
        assert child.is_enabled(config_sections) is True

    def test_is_enabled_if_enabled_str_not_matching(self):
        parent_opt = ConfigOptionDefinition("p", "P", str, "d")
        section_opt = ConfigSectionOptionDefinition("other_sect", parent_opt)
        child = ConfigSectionDefinition(
            "child", "Child", enable_type=ConfigSectionEnableType.IF_ENABLED
        )
        child.set_enabled_by(section_opt)
        cp = ConfigParser()
        cp["DEFAULT"]["p"] = "other"
        config_sections = {"other_sect": cp["DEFAULT"]}
        assert child.is_enabled(config_sections) is False

    def test_is_enabled_if_enabled_int_raises(self):
        parent_opt = ConfigOptionDefinition("p", "P", int, "d")
        section_opt = ConfigSectionOptionDefinition("other_sect", parent_opt)
        child = ConfigSectionDefinition(
            "child", "Child", enable_type=ConfigSectionEnableType.IF_ENABLED
        )
        child.set_enabled_by(section_opt)
        cp = ConfigParser()
        cp["DEFAULT"]["p"] = "42"
        config_sections = {"other_sect": cp["DEFAULT"]}
        with pytest.raises(ValueError, match="Unknown value type"):
            child.is_enabled(config_sections)

    def test_is_enabled_if_required_no_required_by(self):
        s = ConfigSectionDefinition(
            "s", "S", enable_type=ConfigSectionEnableType.IF_REQUIRED
        )
        with pytest.raises(
            ValueError, match="not configured for the configuration section"
        ):
            s.is_enabled({})

    def test_is_enabled_if_required_true(self):
        requirer = ConfigSectionDefinition(
            "requirer", "Requirer", enable_type=ConfigSectionEnableType.ALWAYS
        )
        required = ConfigSectionDefinition(
            "required", "Required", enable_type=ConfigSectionEnableType.IF_REQUIRED
        )
        required.add_required_by(requirer)
        config_sections = {}
        assert required.is_enabled(config_sections) is True

    def test_is_enabled_if_required_false(self):
        requirer = ConfigSectionDefinition(
            "requirer", "Requirer", enable_type=ConfigSectionEnableType.IF_ENABLED
        )
        required = ConfigSectionDefinition(
            "required", "Required", enable_type=ConfigSectionEnableType.IF_REQUIRED
        )
        required.add_required_by(requirer)
        config_sections = {}
        with pytest.raises(ValueError):
            required.is_enabled(config_sections)

    def test_copy_from(self):
        target = ConfigSectionDefinition("target", "Target")
        source = ConfigSectionDefinition("source", "Source")
        opt = ConfigOptionDefinition("o", "O", str, "d")
        source.add_option_definition(opt)
        target.copy_from(source)
        assert "o" in target.option_definitions

    def test_copy_from_with_enabled_by(self):
        target = ConfigSectionDefinition("target", "Target")
        source = ConfigSectionDefinition("source", "Source")
        opt = ConfigOptionDefinition("p", "P", bool, "d", default_value=False)
        section_opt = ConfigSectionOptionDefinition("other", opt)
        source.set_enabled_by(section_opt)
        target.copy_from(source)
        assert target.enabled_by is section_opt

    def test_copy_from_with_required_by(self):
        target = ConfigSectionDefinition("target", "Target")
        source = ConfigSectionDefinition("source", "Source")
        r = ConfigSectionDefinition("r", "R")
        source.add_required_by(r)
        target.copy_from(source)
        assert r in target.required_by

    def test_sort_key_function(self):
        s = ConfigSectionDefinition("b", "B", sort_key_prefix=200)
        t = ConfigSectionDefinition("a", "A", sort_key_prefix=100)
        items = [s, t]
        items.sort(key=config_section_definitions_sort_key)
        assert items[0] is t
        assert items[1] is s


# ---------------------------------------------------------------------------
# VerificationResult
# ---------------------------------------------------------------------------


class TestVerificationResult:
    def test_default_message(self):
        r = VerificationResult(None)
        assert r.message == "Select value:"

    def test_custom_message(self):
        r = VerificationResult("Custom message")
        assert r.message == "Custom message"

    def test_status_default_true(self):
        r = VerificationResult("msg")
        assert r.status is True

    def test_status_false(self):
        r = VerificationResult("msg", status=False)
        assert r.status is False

    def test_bool_true(self):
        r = VerificationResult("msg")
        assert bool(r) is True

    def test_bool_false(self):
        r = VerificationResult("msg", status=False)
        assert bool(r) is False

    def test_str_repr(self):
        r = VerificationResult("msg")
        assert "SelectionResult" in repr(r)
        assert "msg" in str(r)


# ---------------------------------------------------------------------------
# VerificationError
# ---------------------------------------------------------------------------


class TestVerificationError:
    def test_init(self):
        def my_func(a, b):
            pass

        err = VerificationError(my_func, "Something failed", [("a", 1), ("b", 2)])
        assert err.function is my_func
        assert err.message == "Something failed"
        assert err.a == 1
        assert err.b == 2

    def test_bool_false(self):
        err = VerificationError(lambda: None, "msg", [])
        assert bool(err) is False

    def test_repr(self):
        def my_func(x):
            pass

        err = VerificationError(my_func, "fail", [("x", 42)])
        assert "my_func" in repr(err)
        assert "fail" in repr(err)
        assert "42" in repr(err)

    def test_str(self):
        def my_func(x):
            pass

        err = VerificationError(my_func, "fail", [("x", 42)])
        assert "my_func" in str(err)


# ---------------------------------------------------------------------------
# ConfigVerifierDefinition
# ---------------------------------------------------------------------------


class TestConfigVerifierDefinition:
    def test_init(self):
        def func(a, b):
            return True

        v = ConfigVerifierDefinition(func, [], "Custom message")
        assert v.function is func
        assert v.parameters == []
        assert v.message == "Custom message"

    def test_default_message(self):
        v = ConfigVerifierDefinition(lambda: True, [])
        assert v.message == "Verification failed."

    def test_str_repr(self):
        v = ConfigVerifierDefinition(lambda: True, [])
        assert "ConfigVerifierDefinition" in repr(v)

    def test_verify_success(self):
        v = ConfigVerifierDefinition(lambda: True, [])
        assert v.verify() is True

    def test_verify_failure_returning_false(self):
        v = ConfigVerifierDefinition(lambda: False, [])
        result = v.verify()
        assert isinstance(result, VerificationError)
        assert result.message == "Verification failed."

    @patch("utils.config.Config")
    def test_verify_failure_with_verification_result(self, mock_config_class):
        mock_config = MagicMock()
        mock_config_class.return_value = mock_config
        mock_config.get_section.return_value = MagicMock()

        def my_verifier(val):
            return VerificationResult("Custom fail", status=False)

        param = ConfigSectionOptionDefinition(
            "sect", ConfigOptionDefinition("o", "O", str, "d")
        )
        v = ConfigVerifierDefinition(my_verifier, [param])
        result = v.verify()
        assert isinstance(result, VerificationError)
        assert result.message == "Custom fail"

    @patch("utils.config.Config")
    def test_verify_passes_arguments(self, mock_config_class):
        mock_config = MagicMock()
        mock_config_class.return_value = mock_config

        opt = ConfigOptionDefinition("o", "O", str, "d")
        section_mock = MagicMock()
        section_mock.__getitem__.return_value = "passed_value"
        mock_config.get_section.return_value = section_mock

        captured = []

        def my_verifier(val):
            captured.append(val)
            return True

        param = ConfigSectionOptionDefinition("sect", opt)
        v = ConfigVerifierDefinition(my_verifier, [param])
        assert v.verify() is True
        assert len(captured) == 1

    def test_verify_passes_non_section_params_directly(self):
        captured = []

        def verifier(a, b):
            captured.extend([a, b])
            return True

        v = ConfigVerifierDefinition(verifier, ["direct", 42])
        assert v.verify() is True
        assert captured == ["direct", 42]


# ---------------------------------------------------------------------------
# SelectionData
# ---------------------------------------------------------------------------


class TestSelectionData:
    def test_init(self):
        sd = SelectionData("val", "Display")
        assert sd.value == "val"
        assert sd.display_name == "Display"

    def test_bool(self):
        sd = SelectionData("val", "Display")
        assert bool(sd) is True

    def test_str_repr(self):
        sd = SelectionData(42, "Forty-two")
        assert "SelectionData" in repr(sd)
        assert "42" in str(sd)
        assert "Forty-two" in str(sd)


# ---------------------------------------------------------------------------
# SelectionType
# ---------------------------------------------------------------------------


class TestSelectionType:
    def test_values(self):
        assert SelectionType.SINGLE.value == ("Single",)
        assert SelectionType.MULTIPLE.value == ("Multiple",)


# ---------------------------------------------------------------------------
# SelectionResult
# ---------------------------------------------------------------------------


class TestSelectionResult:
    def test_defaults(self):
        sr = SelectionResult()
        assert sr.caption == "Values"
        assert sr.message == "Select value:"
        assert sr.selection_type == SelectionType.SINGLE
        assert sr.values == []

    def test_custom(self):
        sr = SelectionResult("Caption", "Message", SelectionType.MULTIPLE)
        assert sr.caption == "Caption"
        assert sr.message == "Message"
        assert sr.selection_type == SelectionType.MULTIPLE

    def test_add_value(self):
        sr = SelectionResult()
        sd = SelectionData("v", "V")
        sr.add_value(sd)
        assert sr.values == [sd]

    def test_bool(self):
        sr = SelectionResult()
        assert bool(sr) is True

    def test_str_repr(self):
        sr = SelectionResult("Cap", "Msg")
        assert "SelectionResult" in repr(sr)
        assert "Cap" in str(sr)
        assert "Msg" in str(sr)


# ---------------------------------------------------------------------------
# SelectionError
# ---------------------------------------------------------------------------


class TestSelectionError:
    def test_init(self):
        def my_func(a, b):
            pass

        err = SelectionError(my_func, "Selection failed", [("a", 1), ("b", 2)])
        assert err.function is my_func
        assert err.message == "Selection failed"
        assert err.a == 1
        assert err.b == 2

    def test_bool_false(self):
        err = SelectionError(lambda: None, "msg", [])
        assert bool(err) is False

    def test_repr(self):
        def my_func(x):
            pass

        err = SelectionError(my_func, "fail", [("x", 99)])
        assert "SelectionError" in repr(err)
        assert "fail" in repr(err)
        assert "99" in repr(err)

    def test_str(self):
        def my_func(x):
            pass

        err = SelectionError(my_func, "fail", [("x", 99)])
        assert "SelectionError" in str(err)
        assert "fail" in str(err)


# ---------------------------------------------------------------------------
# ConfigSelectorDefinition
# ---------------------------------------------------------------------------


class TestConfigSelectorDefinition:
    def test_init(self):
        def func():
            return SelectionResult("Cap", "Msg")

        sel = ConfigSelectorDefinition(func, [], "Custom msg")
        assert sel.function is func
        assert sel.parameters == []
        assert sel.message == "Custom msg"

    def test_default_message(self):
        sel = ConfigSelectorDefinition(lambda: None, [])
        assert sel.message == "Value selection failed."

    def test_str_repr(self):
        sel = ConfigSelectorDefinition(lambda: None, [])
        assert "ConfigSelectorDefinition" in repr(sel)

    @patch("utils.config.Config")
    def test_select_success(self, mock_config_class):
        mock_config = MagicMock()
        mock_config_class.return_value = mock_config

        result = SelectionResult("Cap", "Msg")
        sel = ConfigSelectorDefinition(lambda: result, [])
        assert sel.select() is result

    @patch("utils.config.Config")
    def test_select_failure(self, mock_config_class):
        mock_config = MagicMock()
        mock_config_class.return_value = mock_config

        sel = ConfigSelectorDefinition(lambda: None, [])
        result = sel.select()
        assert isinstance(result, SelectionError)
        assert result.message == "Value selection failed."

    @patch("utils.config.Config")
    def test_select_failure_returns_false(self, mock_config_class):
        mock_config = MagicMock()
        mock_config_class.return_value = mock_config

        sel = ConfigSelectorDefinition(lambda: False, [])
        result = sel.select()
        assert isinstance(result, SelectionError)

    @patch("utils.config.Config")
    def test_select_passes_parent(self, mock_config_class):
        mock_config = MagicMock()
        mock_config_class.return_value = mock_config

        mock_parent = MagicMock()
        captured = []

        def func(parent, *args):
            captured.append(parent)
            return SelectionResult()

        sel = ConfigSelectorDefinition(func, [])
        sel.select(parent=mock_parent)
        assert captured[0] is mock_parent

    @patch("utils.config.Config")
    def test_select_passes_parameters(self, mock_config_class):
        mock_config = MagicMock()
        mock_config_class.return_value = mock_config

        opt = ConfigOptionDefinition("o", "O", str, "d")
        section_mock = MagicMock()
        section_mock.__getitem__.return_value = "val_from_config"
        mock_config.get_section.return_value = section_mock

        captured = []

        def func(*args):
            captured.extend(args)
            return SelectionResult()

        param = ConfigSectionOptionDefinition("sect", opt)
        sel = ConfigSelectorDefinition(func, [param])
        sel.select()
        assert len(captured) == 1

    @patch("utils.config.Config")
    def test_select_passes_non_section_parameters_directly(self, mock_config_class):
        mock_config = MagicMock()
        mock_config_class.return_value = mock_config

        captured = []

        def func(*args):
            captured.extend(args)
            return SelectionResult()

        sel = ConfigSelectorDefinition(func, ["direct_value", 42])
        sel.select()
        assert captured == ["direct_value", 42]


# ---------------------------------------------------------------------------
# RuntimeStateGroup
# ---------------------------------------------------------------------------


class TestRuntimeStateGroup:
    def test_repr_and_str(self, tmp_path):
        with patch("utils.config_definitions.DATA_DIR", tmp_path):
            rsg = RuntimeStateGroup("test.dat")
        rep = repr(rsg)
        assert "RuntimeStateGroup" in rep
        assert "test.dat" in rep
        assert str(rsg) == rep

    def test_register_duplicate_raises(self, tmp_path):
        with patch("utils.config_definitions.DATA_DIR", tmp_path):
            rsg = RuntimeStateGroup("test.dat")
            RuntimeStateOptionDefinition(rsg, "a", "A", str, "desc")
        with pytest.raises(ValueError, match="already registered"):
            RuntimeStateOptionDefinition(rsg, "a", "A", str, "desc")

    def test_get_value_returns_none_when_section_missing(self, tmp_path):
        with patch("utils.config_definitions.DATA_DIR", tmp_path):
            rsg = RuntimeStateGroup("test.dat")
            opt = RuntimeStateOptionDefinition(rsg, "x", "X", str, "desc")
        assert rsg.get_value("MissingSection", opt) is None

    def test_set_value_creates_section(self, tmp_path):
        with patch("utils.config_definitions.DATA_DIR", tmp_path):
            rsg = RuntimeStateGroup("test.dat")
            opt = RuntimeStateOptionDefinition(rsg, "x", "X", str, "desc")
        rsg.set_value("NewSection", opt, "hello")
        assert rsg.get_value("NewSection", opt) == "hello"


class TestRuntimeStateOptionDefinition:
    def test_repr_and_str(self, tmp_path):
        with patch("utils.config_definitions.DATA_DIR", tmp_path):
            rsg = RuntimeStateGroup("test.dat")
            opt = RuntimeStateOptionDefinition(rsg, "x", "X", str, "desc")
        rep = repr(opt)
        assert "RuntimeStateOptionDefinition" in rep
        assert "test.dat" in rep
        assert str(opt) == rep

    def test_runtime_state_group_property(self, tmp_path):
        with patch("utils.config_definitions.DATA_DIR", tmp_path):
            rsg = RuntimeStateGroup("test.dat")
            opt = RuntimeStateOptionDefinition(rsg, "x", "X", str, "desc")
        assert opt.runtime_state_group is rsg
