from unittest.mock import MagicMock, patch

import wx

from prewarning import PreWarning, _filter_logging_configuration


class TestFilterLoggingConfiguration:
    def test_replaces_placeholders(self):
        config = {"filename": "{APPLICATION_DIR}/logs/test.log"}
        with patch(
            "prewarning.LOGGING_CONFIGURATION_FILE_FILTER_VALUES",
            {"APPLICATION_DIR": "C:\\app"},
        ):
            _filter_logging_configuration(config)
        assert "C:\\app" in config["filename"] or "C:/app" in config["filename"]

    def test_resolves_filename_path(self):
        config = {"filename": "logs/test.log"}
        with patch(
            "prewarning.LOGGING_CONFIGURATION_FILE_FILTER_VALUES",
            {"APPLICATION_DIR": "/tmp"},
        ):
            _filter_logging_configuration(config)
        assert isinstance(config["filename"], str)

    def test_handles_nested_dicts(self):
        config = {
            "root": {"level": "{APPLICATION_DIR}/info"},
        }
        with patch(
            "prewarning.LOGGING_CONFIGURATION_FILE_FILTER_VALUES",
            {"APPLICATION_DIR": "/base"},
        ):
            _filter_logging_configuration(config)
        assert "/base" in config["root"]["level"]

    def test_ignores_non_string_values(self):
        config = {"version": 1, "enabled": True}
        _filter_logging_configuration(config)
        assert config["version"] == 1
        assert config["enabled"] is True

    def test_handles_non_dict(self):
        config = {"key": "no_placeholder"}
        _filter_logging_configuration(config)
        assert config["key"] == "no_placeholder"


class TestToStr:
    def test_converts_int(self):
        assert PreWarning._to_str(42) == "42"

    def test_converts_none(self):
        assert PreWarning._to_str(None) == "-"

    def test_returns_string(self):
        assert PreWarning._to_str("hello") == "hello"

    def test_converts_zero(self):
        assert PreWarning._to_str(0) == "0"

    def test_converts_empty_string(self):
        assert PreWarning._to_str("") == ""


class TestGetPortraitScreen:
    def test_returns_portrait_display(self):
        mock_portrait = MagicMock(spec=wx.Display)
        mock_portrait.GetGeometry.return_value.GetHeight.return_value = 1080
        mock_portrait.GetGeometry.return_value.GetWidth.return_value = 720

        mock_landscape = MagicMock(spec=wx.Display)
        mock_landscape.GetGeometry.return_value.GetHeight.return_value = 720
        mock_landscape.GetGeometry.return_value.GetWidth.return_value = 1080

        displays = [mock_landscape, mock_portrait]

        with patch("wx.Display", side_effect=displays) as mock_display:
            mock_display.GetCount.return_value = 2
            result = PreWarning._get_portrait_screen()
            assert result is mock_portrait

    def test_returns_none_when_no_portrait(self):
        mock_landscape = MagicMock(spec=wx.Display)
        mock_landscape.GetGeometry.return_value.GetHeight.return_value = 720
        mock_landscape.GetGeometry.return_value.GetWidth.return_value = 1080

        displays = [mock_landscape]

        with patch("wx.Display", side_effect=displays) as mock_display:
            mock_display.GetCount.return_value = 1
            result = PreWarning._get_portrait_screen()
            assert result is None
