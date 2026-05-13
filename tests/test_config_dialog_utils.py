from configparser import ConfigParser
from pathlib import Path
import wx
import pytest

from utils.config_definitions import ConfigOptionDefinition

from utils.config_dialog import (
    _default_value,
    _value,
    _has_default_value,
    _default_tooltip,
    _set_value,
    _get_value,
)


class TestDefaultValue:
    def test_bool_returns_value(self):
        opt = ConfigOptionDefinition("b", "B", bool, "desc", default_value=True)
        assert _default_value(opt) is True

    def test_bool_false(self):
        opt = ConfigOptionDefinition("b", "B", bool, "desc", default_value=False)
        assert _default_value(opt) is False

    def test_str_returns_str(self):
        opt = ConfigOptionDefinition("s", "S", str, "desc", default_value="hello")
        assert _default_value(opt) == "hello"

    def test_int_returns_str(self):
        opt = ConfigOptionDefinition("i", "I", int, "desc", default_value=42)
        assert _default_value(opt) == "42"

    def test_float_returns_str(self):
        opt = ConfigOptionDefinition("f", "F", float, "desc", default_value=3.14)
        assert _default_value(opt) == "3.14"

    def test_path_returns_str(self):
        opt = ConfigOptionDefinition("p", "P", Path, "desc", default_value=Path("/tmp"))
        result = _default_value(opt)
        assert isinstance(result, str)

    def test_none_default_returns_str_none(self):
        opt = ConfigOptionDefinition("s", "S", str, "desc", default_value=None)
        assert _default_value(opt) == "None"


class TestValue:
    @pytest.fixture
    def section(self):
        cp = ConfigParser()
        cp.add_section("test")
        cp["test"]["opt"] = "hello"
        return cp["test"]

    def test_str_value(self, section):
        opt = ConfigOptionDefinition("opt", "Opt", str, "desc")
        assert _value(opt, section) == "hello"

    def test_str_value_empty(self, section):
        cp = ConfigParser()
        cp.add_section("test")
        opt = ConfigOptionDefinition("opt", "Opt", str, "desc")
        assert _value(opt, cp["test"]) == ""

    def test_bool_value(self, section):
        opt = ConfigOptionDefinition("opt", "Opt", bool, "desc", default_value=False)
        cp = ConfigParser()
        cp.add_section("test")
        cp["test"]["opt"] = "yes"
        result = _value(opt, cp["test"])
        assert result is True

    def test_bool_value_false(self, section):
        opt = ConfigOptionDefinition("opt", "Opt", bool, "desc", default_value=True)
        cp = ConfigParser()
        cp.add_section("test")
        assert _value(opt, cp["test"]) is True

    def test_int_value_returns_str(self, section):
        opt = ConfigOptionDefinition("num", "Num", int, "desc", default_value=0)
        cp = ConfigParser()
        cp.add_section("test")
        cp["test"]["num"] = "42"
        assert _value(opt, cp["test"]) == "42"


class TestHasDefaultValue:
    @pytest.fixture
    def section(self):
        cp = ConfigParser()
        cp.add_section("test")
        return cp["test"]

    def test_value_equals_default(self, section):
        opt = ConfigOptionDefinition("opt", "Opt", str, "desc", default_value="default")
        section["opt"] = "default"
        assert _has_default_value(opt, section) is True

    def test_value_differs_from_default(self, section):
        opt = ConfigOptionDefinition("opt", "Opt", str, "desc", default_value="default")
        section["opt"] = "custom"
        assert _has_default_value(opt, section) is False

    def test_bool_default(self, section):
        opt = ConfigOptionDefinition("b", "B", bool, "desc", default_value=True)
        section["b"] = "1"
        assert _has_default_value(opt, section) is True

    def test_bool_differs(self, section):
        opt = ConfigOptionDefinition("b", "B", bool, "desc", default_value=True)
        section["b"] = "0"
        assert _has_default_value(opt, section) is False


class TestDefaultTooltip:
    def test_default(self):
        assert _default_tooltip("default") == "Reset to the default value."

    def test_verify(self):
        assert _default_tooltip("verify") == "Test the value(s)."

    def test_select(self):
        assert _default_tooltip("select") == "Select a value."

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="_default_tooltip: Invalid function"):
            _default_tooltip("invalid")


class TestSetGetValue:
    def test_text_ctrl(self, wx_app):
        ctrl = wx.TextCtrl(wx.Frame(None))
        _set_value(ctrl, "test_value")
        assert _get_value(ctrl) == "test_value"
        ctrl.Destroy()

    def test_text_ctrl_empty(self, wx_app):
        ctrl = wx.TextCtrl(wx.Frame(None))
        _set_value(ctrl, "")
        assert _get_value(ctrl) == ""
        ctrl.Destroy()

    def test_checkbox_true(self, wx_app):
        ctrl = wx.CheckBox(wx.Frame(None))
        _set_value(ctrl, True)
        assert _get_value(ctrl) is True or _get_value(ctrl) == "1"
        ctrl.Destroy()

    def test_checkbox_false(self, wx_app):
        ctrl = wx.CheckBox(wx.Frame(None))
        _set_value(ctrl, False)
        assert _get_value(ctrl) is False or _get_value(ctrl) == ""
        ctrl.Destroy()

    def test_combobox(self, wx_app):
        parent = wx.Frame(None)
        ctrl = wx.ComboBox(parent, choices=["a", "b", "c"])
        _set_value(ctrl, "b")
        assert _get_value(ctrl) == "b"
        ctrl.Destroy()
        parent.Destroy()

    def test_listbox(self, wx_app):
        parent = wx.Frame(None)
        ctrl = wx.ListBox(parent, choices=["x", "y", "z"])
        _set_value(ctrl, "y")
        assert ctrl.GetSelection() == 1
        assert _get_value(ctrl) == "y"
        ctrl.Destroy()
        parent.Destroy()

    def test_listbox_no_selection(self, wx_app):
        parent = wx.Frame(None)
        ctrl = wx.ListBox(parent, choices=["a", "b"])
        assert _get_value(ctrl) is None
        ctrl.Destroy()
        parent.Destroy()
