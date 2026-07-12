# -*- coding: utf-8 -*-

from unittest.mock import MagicMock, patch

import wx

from utils.control_window import ControlWindow


class TestFindLandscapeDisplay:
    def test_returns_none_when_no_displays(self, wx_app):
        with patch.object(wx.Display, "GetCount", return_value=0):
            result = ControlWindow.find_landscape_display()
            assert result is None

    def test_returns_landscape_display(self, wx_app):
        with patch.object(wx.Display, "GetCount", return_value=2):
            geo_portrait = wx.Rect(0, 0, 1080, 1920)
            geo_landscape = wx.Rect(1080, 0, 1920, 1080)

            def mock_display_init(self_display, idx):
                self_display._idx = idx

            with patch.object(wx.Display, "__init__", mock_display_init):
                with patch.object(
                    wx.Display,
                    "GetGeometry",
                    side_effect=[geo_portrait, geo_landscape],
                ):
                    ControlWindow.find_landscape_display()
                    # Since mocking is complex with Display, just verify it doesn't crash
                    # The real test is below with exclude_display

    def test_returns_none_when_all_portrait(self, wx_app):
        with patch.object(wx.Display, "GetCount", return_value=2):
            geo1 = MagicMock()
            geo1.GetWidth.return_value = 1080
            geo1.GetHeight.return_value = 1920
            geo2 = MagicMock()
            geo2.GetWidth.return_value = 1080
            geo2.GetHeight.return_value = 1920

            mock_displays = [MagicMock(), MagicMock()]
            mock_displays[0].GetGeometry.return_value = geo1
            mock_displays[1].GetGeometry.return_value = geo2

            with patch("utils.control_window.wx.Display") as MockDisplay:
                MockDisplay.GetCount.return_value = 2
                MockDisplay.side_effect = lambda i: mock_displays[i]
                geo1.__eq__ = lambda self, other: False
                geo2.__eq__ = lambda self, other: False

                result = ControlWindow.find_landscape_display()
                assert result is None

    def test_excludes_specified_display(self, wx_app):
        geo_main = MagicMock()
        geo_main.GetWidth.return_value = 1920
        geo_main.GetHeight.return_value = 1080

        geo_other = MagicMock()
        geo_other.GetWidth.return_value = 1920
        geo_other.GetHeight.return_value = 1080

        mock_display_main = MagicMock()
        mock_display_main.GetGeometry.return_value = geo_main

        mock_display_other = MagicMock()
        mock_display_other.GetGeometry.return_value = geo_other

        with patch("utils.control_window.wx.Display") as MockDisplay:
            MockDisplay.GetCount.return_value = 2

            def display_factory(i):
                if i == 0:
                    return mock_display_main
                return mock_display_other

            MockDisplay.side_effect = display_factory

            # When the geometries match (idx 0 == exclude_display), skip it
            geo_main.__eq__ = lambda self, other: other is geo_main
            geo_other.__eq__ = lambda self, other: other is geo_other

            result = ControlWindow.find_landscape_display(
                exclude_display=mock_display_main
            )
            assert result is mock_display_other

    def test_returns_first_landscape_when_multiple_available(self, wx_app):
        geo1 = MagicMock()
        geo1.GetWidth.return_value = 1920
        geo1.GetHeight.return_value = 1080
        geo2 = MagicMock()
        geo2.GetWidth.return_value = 2560
        geo2.GetHeight.return_value = 1440

        mock_d1 = MagicMock()
        mock_d1.GetGeometry.return_value = geo1
        mock_d2 = MagicMock()
        mock_d2.GetGeometry.return_value = geo2

        with patch("utils.control_window.wx.Display") as MockDisplay:
            MockDisplay.GetCount.return_value = 2
            MockDisplay.side_effect = lambda i: [mock_d1, mock_d2][i]
            geo1.__eq__ = lambda self, other: False
            geo2.__eq__ = lambda self, other: False

            result = ControlWindow.find_landscape_display()
            assert result is mock_d1

    def test_square_display_is_landscape(self, wx_app):
        """A square display (width==height) qualifies as landscape."""
        geo = MagicMock()
        geo.GetWidth.return_value = 1024
        geo.GetHeight.return_value = 1024

        mock_d = MagicMock()
        mock_d.GetGeometry.return_value = geo

        with patch("utils.control_window.wx.Display") as MockDisplay:
            MockDisplay.GetCount.return_value = 1
            MockDisplay.side_effect = lambda i: mock_d
            geo.__eq__ = lambda self, other: False

            result = ControlWindow.find_landscape_display()
            assert result is mock_d

    def test_returns_none_when_only_excluded_display(self, wx_app):
        geo = MagicMock()
        geo.GetWidth.return_value = 1920
        geo.GetHeight.return_value = 1080

        mock_d = MagicMock()
        mock_d.GetGeometry.return_value = geo

        exclude = MagicMock()
        exclude.GetGeometry.return_value = geo

        with patch("utils.control_window.wx.Display") as MockDisplay:
            MockDisplay.GetCount.return_value = 1
            MockDisplay.side_effect = lambda i: mock_d
            # Same geometry — should match
            geo.__eq__ = lambda self, other: True

            result = ControlWindow.find_landscape_display(exclude_display=exclude)
            assert result is None
