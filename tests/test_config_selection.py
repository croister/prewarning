from unittest.mock import patch, MagicMock
import wx
import pytest

from utils.config_selection import select_file


class TestSelectFile:
    @pytest.fixture
    def parent(self, wx_app):
        return wx.Frame(None)

    @staticmethod
    def _make_dialog(show_modal_ret=wx.ID_OK, path="/path/to/file.txt"):
        mock_dialog = MagicMock(spec=wx.FileDialog)
        mock_dialog.ShowModal.return_value = show_modal_ret
        mock_dialog.GetPath.return_value = path
        mock_dialog.__enter__.return_value = mock_dialog
        return mock_dialog

    def test_returns_path_on_ok(self, parent):
        mock_dialog = self._make_dialog(wx.ID_OK, "/path/to/file.txt")
        with patch("wx.FileDialog", return_value=mock_dialog):
            result = select_file(parent, "Select", wildcard="*.txt")
        assert result == "/path/to/file.txt"

    def test_returns_none_on_cancel(self, parent):
        mock_dialog = self._make_dialog(wx.ID_CANCEL)
        with patch("wx.FileDialog", return_value=mock_dialog):
            result = select_file(parent, "Select")
        assert result is None

    def test_passes_arguments(self, parent):
        mock_dialog = self._make_dialog()
        with patch("wx.FileDialog", return_value=mock_dialog) as mock_ctor:
            select_file(parent, "Pick a file", default_dir="/tmp", wildcard="*.csv")
        mock_ctor.assert_called_once_with(
            parent=parent,
            message="Pick a file",
            defaultDir="/tmp",
            wildcard="*.csv",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        )

    def test_default_message(self, parent):
        mock_dialog = self._make_dialog()
        with patch("wx.FileDialog", return_value=mock_dialog) as mock_ctor:
            select_file(parent)
        mock_ctor.assert_called_once_with(
            parent=parent,
            message="Select a file",
            defaultDir=None,
            wildcard="",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        )
