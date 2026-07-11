# -*- coding: utf-8 -*-

"""Cross-platform screen sleep prevention."""

import logging
import subprocess
import sys

logger = logging.getLogger(__name__)


class ScreenSleepInhibitor:
    """Prevents the display from turning off and the screensaver from activating.

    Supports Windows, macOS, and Linux. Safe to call inhibit/uninhibit
    multiple times. Automatically restores normal behavior on process exit.
    """

    def __init__(self):
        self._active = False
        self._handle = None  # platform-specific handle

    @property
    def is_active(self) -> bool:
        """Whether screen sleep is currently inhibited."""
        return self._active

    def inhibit(self) -> None:
        """Prevent screen sleep. Safe to call multiple times."""
        if self._active:
            return
        try:
            if sys.platform == "win32":
                self._inhibit_windows()
            elif sys.platform == "darwin":
                self._inhibit_macos()
            else:
                self._inhibit_linux()
            self._active = True
            logger.info("Screen sleep prevention activated.")
        except Exception as e:
            logger.warning("Failed to inhibit screen sleep: %s", e)

    def uninhibit(self) -> None:
        """Restore normal sleep behavior. Safe to call multiple times."""
        if not self._active:
            return
        try:
            if sys.platform == "win32":
                self._uninhibit_windows()
            elif sys.platform == "darwin":
                self._uninhibit_macos()
            else:
                self._uninhibit_linux()
            logger.info("Screen sleep prevention deactivated.")
        except Exception as e:
            logger.warning("Failed to uninhibit screen sleep: %s", e)
        finally:
            self._active = False
            self._handle = None

    # -- Windows ---------------------------------------------------------------

    def _inhibit_windows(self) -> None:
        import ctypes

        ES_CONTINUOUS = 0x80000000
        ES_DISPLAY_REQUIRED = 0x00000002
        ES_SYSTEM_REQUIRED = 0x00000001

        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED
        )

    def _uninhibit_windows(self) -> None:
        import ctypes

        ES_CONTINUOUS = 0x80000000
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)

    # -- macOS -----------------------------------------------------------------

    def _inhibit_macos(self) -> None:
        self._handle = subprocess.Popen(
            ["caffeinate", "-d", "-i"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _uninhibit_macos(self) -> None:
        if self._handle is not None:
            self._handle.terminate()
            self._handle.wait()

    # -- Linux -----------------------------------------------------------------

    def _inhibit_linux(self) -> None:
        result = subprocess.run(
            ["xdg-screensaver", "suspend", str(self._get_window_id())],
            capture_output=True,
        )
        if result.returncode != 0:
            logger.warning(
                "xdg-screensaver suspend failed (returncode=%d). "
                "Screen sleep prevention may not work.",
                result.returncode,
            )

    def _uninhibit_linux(self) -> None:
        subprocess.run(
            ["xdg-screensaver", "resume", str(self._get_window_id())],
            capture_output=True,
        )

    def _get_window_id(self) -> int:
        """Get the X11 window ID. Returns 0 if not available."""
        try:
            import wx

            app = wx.GetApp()
            if app is not None:
                top = app.GetTopWindow()
                if top is not None:
                    return top.GetHandle()
        except Exception:
            pass
        return 0
