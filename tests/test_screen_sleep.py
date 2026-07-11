import sys
from unittest.mock import patch

from utils.screen_sleep import ScreenSleepInhibitor


class TestScreenSleepInhibitor:
    def test_initial_state_not_active(self):
        inhibitor = ScreenSleepInhibitor()
        assert inhibitor.is_active is False

    def test_inhibit_sets_active(self):
        inhibitor = ScreenSleepInhibitor()
        with patch.object(
            inhibitor,
            f"_inhibit_{'windows' if sys.platform == 'win32' else 'darwin' if sys.platform == 'darwin' else 'linux'}",
        ):
            inhibitor.inhibit()
            assert inhibitor.is_active is True

    def test_uninhibit_clears_active(self):
        inhibitor = ScreenSleepInhibitor()
        with patch.object(
            inhibitor,
            f"_inhibit_{'windows' if sys.platform == 'win32' else 'darwin' if sys.platform == 'darwin' else 'linux'}",
        ):
            inhibitor.inhibit()
        with patch.object(
            inhibitor,
            f"_uninhibit_{'windows' if sys.platform == 'win32' else 'darwin' if sys.platform == 'darwin' else 'linux'}",
        ):
            inhibitor.uninhibit()
            assert inhibitor.is_active is False

    def test_inhibit_twice_only_calls_once(self):
        inhibitor = ScreenSleepInhibitor()
        mock_method = f"_inhibit_{'windows' if sys.platform == 'win32' else 'darwin' if sys.platform == 'darwin' else 'linux'}"
        with patch.object(inhibitor, mock_method) as mock:
            inhibitor.inhibit()
            inhibitor.inhibit()
            mock.assert_called_once()

    def test_uninhibit_when_not_active_does_nothing(self):
        inhibitor = ScreenSleepInhibitor()
        mock_method = f"_uninhibit_{'windows' if sys.platform == 'win32' else 'darwin' if sys.platform == 'darwin' else 'linux'}"
        with patch.object(inhibitor, mock_method) as mock:
            inhibitor.uninhibit()
            mock.assert_not_called()

    def test_inhibit_failure_does_not_set_active(self):
        inhibitor = ScreenSleepInhibitor()
        mock_method = f"_inhibit_{'windows' if sys.platform == 'win32' else 'darwin' if sys.platform == 'darwin' else 'linux'}"
        with patch.object(inhibitor, mock_method, side_effect=OSError("fail")):
            inhibitor.inhibit()
            assert inhibitor.is_active is False

    def test_uninhibit_failure_still_clears_active(self):
        inhibitor = ScreenSleepInhibitor()
        inhibitor._active = True
        mock_method = f"_uninhibit_{'windows' if sys.platform == 'win32' else 'darwin' if sys.platform == 'darwin' else 'linux'}"
        with patch.object(inhibitor, mock_method, side_effect=OSError("fail")):
            inhibitor.uninhibit()
            assert inhibitor.is_active is False


class TestScreenSleepInhibitorWindows:
    def test_inhibit_calls_set_thread_execution_state(self):
        if sys.platform != "win32":
            return
        inhibitor = ScreenSleepInhibitor()
        with patch("ctypes.windll.kernel32.SetThreadExecutionState") as mock:
            inhibitor._inhibit_windows()
            mock.assert_called_once()
            args = mock.call_args[0][0]
            assert args & 0x80000000  # ES_CONTINUOUS
            assert args & 0x00000002  # ES_DISPLAY_REQUIRED
            assert args & 0x00000001  # ES_SYSTEM_REQUIRED

    def test_uninhibit_calls_set_thread_execution_state_continuous(self):
        if sys.platform != "win32":
            return
        inhibitor = ScreenSleepInhibitor()
        with patch("ctypes.windll.kernel32.SetThreadExecutionState") as mock:
            inhibitor._uninhibit_windows()
            mock.assert_called_once_with(0x80000000)
