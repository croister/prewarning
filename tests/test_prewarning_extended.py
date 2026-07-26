from unittest.mock import MagicMock, call, patch

import pytest
import wx

from prewarning import PreWarning


class TestConfigSectionDefinition:
    def test_returns_common_config_section_definition(self):
        result = PreWarning.config_section_definition()
        assert result is PreWarning.COMMON_CONFIG_SECTION_DEFINITION


class TestStop:
    @pytest.fixture
    def pw(self):
        inst = MagicMock()
        inst.observer = MagicMock()
        inst.observer.is_alive.return_value = True
        inst.punch_source = MagicMock()
        inst.start_list_source = MagicMock()
        return inst

    def test_stops_observer(self, pw):
        PreWarning.stop(pw)
        pw.observer.stop.assert_called_once()
        pw.observer.join.assert_called_once()

    def test_stops_config(self, pw):
        with patch("prewarning.Config") as mock_config:
            PreWarning.stop(pw)
            mock_config.return_value.stop.assert_called_once()

    def test_stops_punch_source(self, pw):
        PreWarning.stop(pw)
        pw.punch_source.stop.assert_called_once()

    def test_stops_start_list_source(self, pw):
        PreWarning.stop(pw)
        pw.start_list_source.stop.assert_called_once()

    def test_no_observer(self, pw):
        pw.observer = None
        PreWarning.stop(pw)

    def test_observer_not_alive(self, pw):
        pw.observer.is_alive.return_value = False
        PreWarning.stop(pw)
        pw.observer.stop.assert_not_called()

    def test_no_punch_source(self, pw):
        pw.punch_source = None
        PreWarning.stop(pw)


class TestFontSize:
    @pytest.fixture
    def pw(self):
        inst = MagicMock()
        inst.font_factor_offset = 0
        return inst

    def test_increase_font_size(self, pw):
        with patch("prewarning.wx.CallAfter"):
            PreWarning._increase_font_size(pw)
        assert pw.font_factor_offset == -1
        pw._calculate_sizes.assert_called_once()

    def test_decrease_font_size(self, pw):
        with patch("prewarning.wx.CallAfter"):
            PreWarning._decrease_font_size(pw)
        assert pw.font_factor_offset == 1
        pw._calculate_sizes.assert_called_once()

    def test_restore_font_size(self, pw):
        pw.font_factor_offset = 5
        with patch("prewarning.wx.CallAfter"):
            PreWarning._restore_font_size(pw)
        assert pw.font_factor_offset == 0
        pw._calculate_sizes.assert_called_once()


class TestPlayTestSound:
    def test_plays_sound(self):
        pw = MagicMock()
        pw.sound = MagicMock()
        from pathlib import Path as _Path

        pw.test_sound_file = _Path("Testing.mp3")
        PreWarning._play_test_sound(pw)
        pw.sound.resolve_voice.assert_called_once_with(None)
        pw.sound.play_voice_sound.assert_called_once()
        call_args = pw.sound.play_voice_sound.call_args[0]
        assert call_args[0] == "Testing.mp3"


class TestSimulatePunch:
    @pytest.fixture
    def pw(self):
        inst = MagicMock()
        inst.test_bib_number = 0
        inst.test_leg_number = 0
        inst.logger = MagicMock()
        inst.announcement_queue = MagicMock()
        return inst

    def test_increments_and_adds_pre_warning(self, pw):
        PreWarning._simulate_punch(pw)
        assert pw.test_bib_number == 10
        assert pw.test_leg_number == 1
        pw._add_pre_warning.assert_called_once()

    def test_queues_announcement(self, pw):
        PreWarning._simulate_punch(pw)
        pw.sound.resolve_voice.assert_called_once_with(None)
        pw.announcement_queue.put.assert_called_once()
        call_args = pw.announcement_queue.put.call_args[0][0]
        assert call_args["sound"] == "10"


class TestPunchReceived:
    def test_puts_punch_in_queue(self):
        pw = MagicMock()
        pw.logger = MagicMock()
        pw.punch_queue = MagicMock()
        punch = {"cardNumber": "123"}
        PreWarning.punch_received(pw, punch)
        pw.punch_queue.put.assert_called_once_with(punch)


class TestConfigUpdated:
    def test_calls_apply_with_callafter(self):
        pw = MagicMock()
        with patch("prewarning.wx.CallAfter") as callafter:
            PreWarning.config_updated(pw, ["Common"])
            callafter.assert_called_once_with(pw._apply_config_update)


class TestApplyConfigUpdate:
    def test_calls_parse_and_update(self):
        pw = MagicMock()
        PreWarning._apply_config_update(pw)
        pw._parse_config.assert_called_once()
        pw.update_sources.assert_called_once()


class TestOnTimer:
    def test_updates_time_label(self):
        from time import strftime

        pw = MagicMock()
        pw.time_label = MagicMock()
        pw._health_tick_counter = 0
        PreWarning._on_timer(pw, None)
        pw.time_label.SetLabel.assert_called_once_with(strftime("%H:%M:%S"))


class TestToggleFullScreen:
    @pytest.fixture
    def pw(self):
        inst = MagicMock()
        inst.logger = MagicMock()
        return inst

    def test_toggles_from_fullscreen(self, pw):
        pw.IsFullScreen.return_value = True
        PreWarning._toggle_full_screen(pw)
        pw.ShowFullScreen.assert_called_once_with(False, style=wx.FULLSCREEN_ALL)

    def test_toggles_to_fullscreen(self, pw):
        pw.IsFullScreen.return_value = False
        PreWarning._toggle_full_screen(pw)
        pw.ShowFullScreen.assert_called_once_with(True, style=wx.FULLSCREEN_ALL)


class TestNotifyIp:
    def test_sends_ip_sections(self):
        pw = MagicMock()
        pw.logger = MagicMock()
        pw.announcement_queue = MagicMock()
        with patch("prewarning.socket.socket") as mock_socket:
            sock = MagicMock()
            mock_socket.return_value = sock
            sock.getsockname.return_value = ("192.168.1.42", 0)

            PreWarning._notify_ip(pw)

            sock.connect.assert_called_once_with(("8.8.8.8", 0))
            assert pw.announcement_queue.put.call_count == 4
            pw.announcement_queue.put.assert_has_calls(
                [
                    call({"voice": None, "sound": "192"}),
                    call({"voice": None, "sound": "168"}),
                    call({"voice": None, "sound": "1"}),
                    call({"voice": None, "sound": "42"}),
                ]
            )
            sock.close.assert_called_once()


class TestClose:
    def test_calls_stop_and_close(self):
        pw = MagicMock()
        pw.logger = MagicMock()
        PreWarning._close(pw)
        pw.stop.assert_called_once()
        pw.Unbind.assert_called_once_with(wx.EVT_CLOSE, handler=pw._close)
        pw.Close.assert_called_once_with(True)


class TestGetInteractiveMode:
    def test_gets_interactive_mode_true(self):
        pw = MagicMock()
        pw.CONFIG_OPTION_INTERACTIVE_MODE = MagicMock()
        pw.CONFIG_OPTION_INTERACTIVE_MODE.get_value.return_value = True
        with patch("prewarning.Config") as mock_config:
            mock_config.return_value.get_section.return_value = {}
            PreWarning._get_interactive_mode(pw)
        assert pw.interactive_mode is True

    def test_defaults_to_true_when_none(self):
        pw = MagicMock()
        pw.CONFIG_OPTION_INTERACTIVE_MODE = MagicMock()
        pw.CONFIG_OPTION_INTERACTIVE_MODE.get_value.return_value = None
        with patch("prewarning.Config") as mock_config:
            mock_config.return_value.get_section.return_value = {}
            PreWarning._get_interactive_mode(pw)
        assert pw.interactive_mode is True


class TestStart:
    @pytest.fixture
    def pw(self):
        inst = MagicMock()
        inst.announce_ip_on_startup = False
        inst.punch_processor = MagicMock()
        inst.announcement_processor = MagicMock()
        inst.punch_source = MagicMock()
        inst.start_list_source = MagicMock()
        return inst

    def test_starts_sources_and_threads(self, pw):
        PreWarning.start(pw)
        pw.punch_processor.start.assert_called_once()
        pw.announcement_processor.start.assert_called_once()
        pw.punch_source.start.assert_called_once()
        pw.start_list_source.start.assert_called_once()

    def test_notifies_ip_when_enabled(self, pw):
        pw.announce_ip_on_startup = True
        pw._notify_ip = MagicMock()
        PreWarning.start(pw)
        pw._notify_ip.assert_called_once()


class TestOnKeyPress:
    @pytest.fixture
    def pw(self):
        inst = MagicMock()
        inst.logger = MagicMock()
        return inst

    def test_dispatches_to_matching_binding(self, pw):
        handler = MagicMock()
        binding = MagicMock()
        binding.matches.return_value = True
        binding.handler = handler
        pw.hotkey_bindings = [binding]

        key_event = MagicMock(spec=wx.KeyEvent)
        PreWarning._on_key_press(pw, key_event)

        handler.assert_called_once()
        key_event.Skip.assert_called_once()

    def test_skips_if_no_match(self, pw):
        binding = MagicMock()
        binding.matches.return_value = False
        pw.hotkey_bindings = [binding]

        key_event = MagicMock(spec=wx.KeyEvent)
        PreWarning._on_key_press(pw, key_event)

        binding.handler.assert_not_called()
        key_event.Skip.assert_called_once()


class TestAboutDialog:
    def test_creates_and_shows(self):
        from prewarning import __version__ as ver

        pw = MagicMock()
        pw.logger = MagicMock()
        with patch("prewarning.AboutDialog") as mock_dlg:
            PreWarning._about_dialog(pw)
            mock_dlg.assert_called_once_with(pw, app_version=ver)
            mock_dlg.return_value.Show.assert_called_once()


class TestHelpDialog:
    def test_creates_and_shows(self):
        from prewarning import __version__ as ver

        pw = MagicMock()
        pw.logger = MagicMock()
        pw.hotkey_bindings = []
        with patch("prewarning.HelpDialog") as mock_dlg:
            PreWarning._help_dialog(pw)
            mock_dlg.assert_called_once_with(
                pw, app_version=ver, hotkey_bindings=pw.hotkey_bindings
            )
            mock_dlg.return_value.Show.assert_called_once()


class TestSetScreenAndSize:
    def test_uses_portrait_display_when_available(self, wx_app):
        pw = MagicMock()
        pw.logger = MagicMock()

        class _FakeClientArea:
            width = 1200
            height = 1920

            def GetTopLeft(self):
                return wx.Point(0, 0)

        class _FakeMode:
            def GetWidth(self):
                return 1200

            def GetHeight(self):
                return 1920

        class _FakeDisplay:
            def GetClientArea(self):
                return _FakeClientArea()

            def GetCurrentMode(self):
                return _FakeMode()

        pw._get_portrait_screen = MagicMock(return_value=_FakeDisplay())
        PreWarning._set_screen_and_size(pw)

        pw.SetPosition.assert_called_once_with(wx.Point(0, 0))
        pw.SetMinSize.assert_called_once()
        pw.SetSize.assert_called_once()
        pw.Center.assert_called_once()


class _MockPunchSource:
    name = "MockPunch"

    def __init__(self):
        self.register_punch_listener = MagicMock()

    def stop(self):
        pass

    def is_running(self):
        return False

    def start(self):
        pass


class _OldMockPunchSource:
    name = "OldPunchName"

    def __init__(self):
        self.register_punch_listener = MagicMock()

    def stop(self):
        pass

    def is_running(self):
        return False

    def start(self):
        pass


class _MockStartListSource:
    name = "MockStartList"

    def __init__(self):
        pass

    def stop(self):
        pass

    def is_running(self):
        return False

    def start(self):
        pass


MOCK_PUNCH_SOURCES = {"MockPunch": _MockPunchSource}
MOCK_START_LIST_SOURCES = {"MockStartList": _MockStartListSource}


class TestUpdateSources:
    def _make_pw(self):
        pw = MagicMock()
        pw.logger = MagicMock()
        return pw

    @patch("prewarning.PUNCH_SOURCES", MOCK_PUNCH_SOURCES)
    @patch("prewarning.START_LIST_SOURCES", MOCK_START_LIST_SOURCES)
    def test_punch_source_not_in_PUNCH_SOURCES_raises(self):
        pw = self._make_pw()
        pw.punch_source_name = "Unknown"
        pw.start_list_source_name = "MockStartList"
        pw.punch_source = None
        pw.start_list_source = None
        with pytest.raises(ValueError, match="not a valid Punch Source"):
            PreWarning.update_sources(pw)

    @patch("prewarning.PUNCH_SOURCES", {"MockPunch": _MockPunchSource})
    @patch("prewarning.START_LIST_SOURCES", MOCK_START_LIST_SOURCES)
    def test_start_list_source_not_in_START_LIST_SOURCES_raises(self):
        pw = self._make_pw()
        pw.punch_source_name = "MockPunch"
        pw.start_list_source_name = "Unknown"
        pw.punch_source = None
        pw.start_list_source = None
        with pytest.raises(ValueError, match="not a valid Start List Source"):
            PreWarning.update_sources(pw)

    @patch("prewarning.PUNCH_SOURCES", MOCK_PUNCH_SOURCES)
    @patch("prewarning.START_LIST_SOURCES", MOCK_START_LIST_SOURCES)
    def test_creates_new_punch_source_when_none(self):
        pw = self._make_pw()
        pw.punch_source_name = "MockPunch"
        pw.start_list_source_name = "MockStartList"
        pw.punch_source = None
        pw.start_list_source = None
        PreWarning.update_sources(pw)
        assert isinstance(pw.punch_source, _MockPunchSource)
        assert isinstance(pw.start_list_source, _MockStartListSource)

    @patch("prewarning.PUNCH_SOURCES", MOCK_PUNCH_SOURCES)
    @patch("prewarning.START_LIST_SOURCES", MOCK_START_LIST_SOURCES)
    def test_registers_punch_listener(self):
        pw = self._make_pw()
        pw.punch_source_name = "MockPunch"
        pw.start_list_source_name = "MockStartList"
        pw.punch_source = None
        pw.start_list_source = None
        PreWarning.update_sources(pw)
        pw.punch_source.register_punch_listener.assert_called_once_with(pw)

    @patch("prewarning.PUNCH_SOURCES", MOCK_PUNCH_SOURCES)
    @patch("prewarning.START_LIST_SOURCES", MOCK_START_LIST_SOURCES)
    def test_switches_punch_source_when_name_changes(self):
        old_source = _OldMockPunchSource()
        old_source.is_running = MagicMock(return_value=False)
        old_source.stop = MagicMock()
        pw = self._make_pw()
        pw.punch_source_name = "MockPunch"
        pw.start_list_source_name = "MockStartList"
        pw.punch_source = old_source
        pw.start_list_source = _MockStartListSource()
        PreWarning.update_sources(pw)
        old_source.stop.assert_called_once()
        assert isinstance(pw.punch_source, _MockPunchSource)

    @patch("prewarning.PUNCH_SOURCES", MOCK_PUNCH_SOURCES)
    @patch("prewarning.START_LIST_SOURCES", MOCK_START_LIST_SOURCES)
    def test_restarts_source_when_running(self):
        old_source = _OldMockPunchSource()
        old_source.is_running = MagicMock(return_value=True)
        old_source.stop = MagicMock()
        pw = self._make_pw()
        pw.punch_source_name = "MockPunch"
        pw.start_list_source_name = "MockStartList"
        pw.punch_source = old_source
        pw.start_list_source = _MockStartListSource()
        PreWarning.update_sources(pw)
        old_source.stop.assert_called_once()
        assert isinstance(pw.punch_source, _MockPunchSource)
