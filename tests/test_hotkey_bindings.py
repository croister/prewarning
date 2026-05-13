from utils.hotkey_bindings import keycode_to_str, modifiers_to_str


class TestKeycodeToStr:
    def test_known_keys(self):
        assert keycode_to_str(340) == "F1"
        assert keycode_to_str(13) == "Return"
        assert keycode_to_str(32) == "Space"
        assert keycode_to_str(27) == "Escape"
        assert keycode_to_str(8) == "Back"
        assert keycode_to_str(9) == "Tab"
        assert keycode_to_str(127) == "Delete"
        assert keycode_to_str(315) == "Up"
        assert keycode_to_str(317) == "Down"
        assert keycode_to_str(314) == "Left"
        assert keycode_to_str(316) == "Right"

    def test_unknown_key(self):
        result = keycode_to_str(9999)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_character_key(self):
        result = keycode_to_str(ord("A"))
        assert result == '"A"'

    def test_zero(self):
        assert keycode_to_str(0) == "None"


class TestModifiersToStr:
    def test_no_modifiers(self):
        assert modifiers_to_str(0) == ""

    def test_ctrl(self):
        import wx

        assert "Ctrl" in modifiers_to_str(wx.ACCEL_CTRL)

    def test_shift(self):
        import wx

        assert "Shift" in modifiers_to_str(wx.ACCEL_SHIFT)

    def test_alt(self):
        import wx

        assert "Alt" in modifiers_to_str(wx.ACCEL_ALT)

    def test_ctrl_shift(self):
        import wx

        result = modifiers_to_str(wx.ACCEL_CTRL | wx.ACCEL_SHIFT)
        assert "Ctrl" in result
        assert "Shift" in result

    def test_all_modifiers(self):
        import wx

        result = modifiers_to_str(wx.ACCEL_CTRL | wx.ACCEL_SHIFT | wx.ACCEL_ALT)
        assert "Ctrl" in result
        assert "Shift" in result
        assert "Alt" in result
