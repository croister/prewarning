"""
PreWarning main file.
"""

__author__ = "Christian Lindblom croister@croister.se"

import logging
import logging.config
import socket
import sys
from datetime import datetime, timedelta
from pathlib import Path
from queue import Queue
from threading import Lock, Thread
from time import strftime, time

import pycountry
import wx
import wx.grid
import wx.lib.stattext
from babel import Locale
from ruamel.yaml import YAML
from watchdog.events import DirModifiedEvent, FileModifiedEvent, LoggingEventHandler
from watchdog.observers import Observer

from punchsources import COMMON_PUNCH_SOURCE, PUNCH_SOURCES
from punchsources._base import PunchListener
from startlistsources import COMMON_START_LIST_SOURCE, START_LIST_SOURCES
from utils.about_dialog import AboutDialog
from utils.config import Config
from utils.config_consumer import ConfigConsumer
from utils.config_definitions import (
    ConfigOptionDefinition,
    ConfigSectionDefinition,
    ConfigSectionOptionDefinition,
    ConfigVerifierDefinition,
)
from utils.config_dialog import ConfigDialog
from utils.constants import (
    APPLICATION_DIR,
    AUDIO_EXTENSION,
    COLOUR_ERROR,
    COLOUR_OK,
    COLOUR_OK_TEXT,
    COLOUR_WARNING,
    CONFIGURATION_DIR,
    DING_FILENAME,
    PUNCH_KEY_BIB_NUMBER,
    PUNCH_KEY_CARD_NUMBER,
    PUNCH_KEY_CONTROL_CODE,
    PUNCH_KEY_COUNTRY,
    PUNCH_KEY_IS_LAST_LEG,
    PUNCH_KEY_PASSED_TIME,
    PUNCH_KEY_RELAY_LEG,
    TESTING_FILENAME,
)
from utils.control_window import ControlWindow
from utils.health import HealthAction, HealthIssue, HealthMonitor, HealthStatus
from utils.help_dialog import HelpDialog
from utils.hotkey_bindings import (
    HotKeyBindingDefinition,
    HotKeyDefinition,
    key_event_to_str,
)
from utils.i18n import N_, _, set_language
from utils.meos_info_server import MeosInfoServer
from utils.screen_sleep import ScreenSleepInhibitor
from utils.sound import Sound, get_all_sounds, verify_sound
from utils.version import __version__
from utils.voice_manager_dialog import VoiceManagerDialog

# Column index names
COL_NR_TIME = 0
COL_NR_TEAM = 1
COL_NR_LEG = 2

# The first row
ROW_ZERO = 0

# Name of the logging configuration file
LOGGING_CONFIGURATION_FILE_NAME = "logging.yaml"

# Logging configuration file location
LOGGING_CONFIGURATION_FILE = CONFIGURATION_DIR / LOGGING_CONFIGURATION_FILE_NAME

_logger = logging.getLogger(__name__)

LOGGING_CONFIGURATION_FILE_FILTER_VALUES = {
    "APPLICATION_DIR": APPLICATION_DIR,
}

# Ensure logs directory exists before logging is configured
(APPLICATION_DIR / "logs").mkdir(exist_ok=True)


def _filter_logging_configuration(config_dict: dict):
    for key, value in config_dict.items():
        if isinstance(value, dict):
            _filter_logging_configuration(value)
        elif isinstance(value, str):
            value = value.format(**LOGGING_CONFIGURATION_FILE_FILTER_VALUES)
            if key == "filename":
                value = str(Path(value).resolve())
            config_dict[key] = value


def _update_logging_configuration():
    # noinspection PyBroadException
    src_path = APPLICATION_DIR / LOGGING_CONFIGURATION_FILE
    try:
        yaml = YAML(typ="safe", pure=True)
        with open(src_path, "r") as f:
            config = yaml.load(f.read())
            _filter_logging_configuration(config)
            logging.config.dictConfig(config)
    except PermissionError as e:
        _logger.error(
            'PermissionError in accessing the logging configuration file: "%s" %s',
            src_path,
            e,
        )
    except OSError as e:
        _logger.error(
            'OSError in accessing the logging configuration file: "%s" %s', src_path, e
        )
    except Exception as e:  # noqa: BLE001 - broad catch intentional; libraries raise diverse exceptions
        _logger.error(
            'Exception in accessing the logging configuration file: "%s" %s',
            src_path,
            e,
        )


_update_logging_configuration()


# Name of the configuration file
CONFIGURATION_FILE_NAME = "prewarning.ini"

# Configuration file location
CONFIGURATION_FILE = CONFIGURATION_DIR / CONFIGURATION_FILE_NAME

# Announcement queue dict keys
_ANNOUNCE_KEY_VOICE = "voice"
_ANNOUNCE_KEY_SOUND = "sound"


def _get_supported_languages() -> list[str]:
    """Discover supported languages from the locales directory, plus 'en' (source)."""
    locales_dir = Path(__file__).resolve().parent / "locales"
    languages = ["en"]
    if locales_dir.is_dir():
        for entry in sorted(locales_dir.iterdir()):
            if entry.is_dir() and entry.name != "__pycache__":
                languages.append(entry.name)
    return languages


_SUPPORTED_LANGUAGES = _get_supported_languages()


def _language_display_name(code: str) -> str:
    """Return a display name for a language code, e.g. 'Svenska (Swedish)'."""
    native = Locale(code).get_display_name(code)
    lang = pycountry.languages.get(alpha_2=code)
    english = lang.name if lang else code
    if native and native.lower() != english.lower():
        return f"{native.title()} ({english})"
    return english


class _NoHighlightGrid(wx.grid.Grid):
    """A wx.Grid subclass that never highlights column labels.

    Newer wxPython versions (4.3+/wxWidgets 3.3+) draw the column header of
    the grid cursor's column with a different (highlighted) background when
    the grid has focus. Since DrawColLabel is not virtual in the Python
    bindings, this subclass uses a custom EVT_PAINT handler on the column
    label window to draw all headers uniformly.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.GetGridColLabelWindow().Bind(wx.EVT_PAINT, self._on_paint_col_labels)

    def _on_paint_col_labels(self, event: wx.PaintEvent) -> None:
        """Paint column labels without any focus/current-column highlight."""
        win = self.GetGridColLabelWindow()
        dc = wx.PaintDC(win)
        dc.SetBackground(wx.Brush(self.GetLabelBackgroundColour()))
        dc.Clear()

        dc.SetFont(self.GetLabelFont())
        dc.SetTextForeground(self.GetLabelTextColour())

        num_cols = self.GetNumberCols()
        label_height = self.GetColLabelSize()
        border_colour = wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DSHADOW)

        for col in range(num_cols):
            col_left = self.GetColLeft(col) - self.GetScrollPos(wx.HORIZONTAL)
            col_width = self.GetColSize(col)
            rect = wx.Rect(col_left, 0, col_width, label_height)

            # Draw border lines
            dc.SetPen(wx.Pen(border_colour))
            dc.DrawLine(rect.GetRight(), 0, rect.GetRight(), label_height)
            dc.DrawLine(
                rect.GetLeft(), label_height - 1, rect.GetRight(), label_height - 1
            )

            # Draw label text
            text = self.GetColLabelValue(col)
            text_rect = wx.Rect(rect)
            text_rect.Deflate(4, 0)
            hAlign, vAlign = self.GetColLabelAlignment()
            align_flags = 0
            if hAlign == wx.ALIGN_LEFT:
                align_flags |= wx.ALIGN_LEFT
            elif hAlign == wx.ALIGN_RIGHT:
                align_flags |= wx.ALIGN_RIGHT
            else:
                align_flags |= wx.ALIGN_CENTER_HORIZONTAL
            if vAlign == wx.ALIGN_TOP:
                align_flags |= wx.ALIGN_TOP
            elif vAlign == wx.ALIGN_BOTTOM:
                align_flags |= wx.ALIGN_BOTTOM
            else:
                align_flags |= wx.ALIGN_CENTER_VERTICAL
            dc.DrawLabel(text, text_rect, align_flags)


class PreWarningMeta(type(wx.Frame), type(ConfigConsumer)):  # type: ignore[misc]
    pass


class PreWarning(
    wx.Frame,
    ConfigConsumer,
    PunchListener,
    LoggingEventHandler,
    metaclass=PreWarningMeta,
):
    """
    The PreWarning main class
    """

    CONFIG_OPTION_LANGUAGE = ConfigOptionDefinition(
        name="Language",
        display_name=N_("Language"),
        value_type=str,
        description=N_("The language used for the application UI."),
        default_value="en",
        valid_values=_SUPPORTED_LANGUAGES,
        valid_values_display={
            code: _language_display_name(code) for code in _SUPPORTED_LANGUAGES
        },
    )

    CONFIG_OPTION_INTERACTIVE_MODE = ConfigOptionDefinition(
        name="InteractiveMode",
        display_name=N_("Interactive Mode"),
        value_type=bool,
        description=N_(
            "Enables or disables the interactive mode. "
            "If this is enabled the default method of configuration is via the GUI and if errors are detected "
            "in the configuration the Settings Dialog is opened. "
            "If this is disabled the configuration file is expected to be used as the means of changing the "
            "configuration and if errors are detected in the configuration errors are written to the log "
            "and the program exits."
        ),
        default_value=True,
    )

    CONFIG_OPTION_ANNOUNCE_IP_ON_STARTUP = ConfigOptionDefinition(
        name="AnnounceIpOnStartup",
        display_name=N_("Announce IP on Startup"),
        value_type=bool,
        description=N_(
            "Enables or disables the readout of the current IP address at startup."
        ),
        default_value=False,
    )

    CONFIG_OPTION_ENABLE_INTRO_SOUND = ConfigOptionDefinition(
        name="EnableIntroSound",
        display_name=N_("Enable Intro Sound"),
        value_type=bool,
        description=N_(
            "Enable or disable the intro sound played before the first team number is read after a timeout."
        ),
        default_value=True,
    )

    CONFIG_OPTION_INTRO_SOUND_TRIGGER_TIMEOUT_SECONDS = ConfigOptionDefinition(
        name="IntroSoundTriggerTimeoutSeconds",
        display_name=N_("Intro Sound Timeout"),
        value_type=int,
        description=N_(
            "The timeout in seconds after the last announcement before the intro sound is played again before"
            " the next announcement."
        ),
        default_value=10,
        valid_values=list(range(121)),
        enabled_by=CONFIG_OPTION_ENABLE_INTRO_SOUND,
    )

    CONFIG_OPTION_INTRO_SOUND_FILE = ConfigOptionDefinition(
        name="IntroSoundFile",
        display_name=N_("Intro Sound"),
        value_type=Path,
        description=N_(
            "The path to the sound file to use as the intro sound before announcements."
        ),
        default_value=Path(DING_FILENAME),
        valid_values_gen=get_all_sounds,
        enabled_by=CONFIG_OPTION_ENABLE_INTRO_SOUND,
    )

    CONFIG_OPTION_ENABLE_INTRO_SOUND.enables.append(
        CONFIG_OPTION_INTRO_SOUND_TRIGGER_TIMEOUT_SECONDS
    )
    CONFIG_OPTION_ENABLE_INTRO_SOUND.enables.append(CONFIG_OPTION_INTRO_SOUND_FILE)

    CONFIG_OPTION_TEST_SOUND_FILE = ConfigOptionDefinition(
        name="TestSoundFile",
        display_name=N_("Test Sound"),
        value_type=Path,
        description=N_("The path to the sound file to use as the test sound."),
        default_value=Path(TESTING_FILENAME),
        valid_values_gen=get_all_sounds,
    )

    CONFIG_OPTION_ADD_PRE_WARNINGS_TO_BOTTOM = ConfigOptionDefinition(
        name="AddPreWarningsToBottom",
        display_name=N_("Add Pre-Warnings to Bottom"),
        value_type=bool,
        description=N_(
            "Set to True if new Pre-Warnings should be added to the bottom of the screen."
        ),
        default_value=False,
    )

    CONFIG_OPTION_ANNOUNCE_LAST_LEG = ConfigOptionDefinition(
        name="AnnounceLastLeg",
        display_name=N_("Announce Last Leg"),
        value_type=bool,
        description=N_(
            "If disabled, pre-warnings for the last leg are suppressed "
            "(not displayed or announced)."
        ),
        default_value=False,
    )

    CONFIG_OPTION_PREVENT_SCREEN_SLEEP = ConfigOptionDefinition(
        name="PreventScreenSleep",
        display_name=N_("Prevent Screen Sleep"),
        value_type=bool,
        description=N_(
            "Prevents the display from turning off and the screensaver from "
            "activating while the application is running."
        ),
        default_value=True,
    )

    CONFIG_OPTION_ENABLE_CONTROL_WINDOW = ConfigOptionDefinition(
        name="EnableControlWindow",
        display_name=N_("Control Window"),
        value_type=bool,
        description=N_(
            "Open a control window on the secondary landscape display for "
            "monitoring and configuration."
        ),
        default_value=True,
    )

    CONFIG_OPTION_DEDUP_CARD_CONTROL = ConfigOptionDefinition(
        name="DedupCardControl",
        display_name=N_("Deduplicate by Card + Control"),
        value_type=bool,
        description=N_(
            "Skip re-announcement when the same SI card punches the same control code again."
        ),
        default_value=False,
    )

    CONFIG_OPTION_DEDUP_BIB_LEG = ConfigOptionDefinition(
        name="DedupBibLeg",
        display_name=N_("Deduplicate by Bib + Leg"),
        value_type=bool,
        description=N_(
            "Skip re-announcement when the same team bib number appears on the same relay leg again."
        ),
        default_value=False,
    )

    CONFIG_OPTION_DEDUP_TIMEOUT_SECONDS = ConfigOptionDefinition(
        name="DedupTimeoutSeconds",
        display_name=N_("Dedup Timeout (seconds)"),
        value_type=int,
        description=N_("How long a dedup key remains active. 0 = forever (session)."),
        default_value=0,
        valid_values=list(range(3601)),
    )

    COMMON_CONFIG_SECTION_DEFINITION = ConfigSectionDefinition(
        name=Config.SECTION_COMMON,
        display_name=N_("Common"),
        option_definitions=[
            CONFIG_OPTION_LANGUAGE,
            CONFIG_OPTION_INTERACTIVE_MODE,
            CONFIG_OPTION_ANNOUNCE_IP_ON_STARTUP,
            CONFIG_OPTION_ENABLE_INTRO_SOUND,
            CONFIG_OPTION_INTRO_SOUND_TRIGGER_TIMEOUT_SECONDS,
            CONFIG_OPTION_INTRO_SOUND_FILE,
            CONFIG_OPTION_TEST_SOUND_FILE,
            CONFIG_OPTION_ADD_PRE_WARNINGS_TO_BOTTOM,
            CONFIG_OPTION_ANNOUNCE_LAST_LEG,
            CONFIG_OPTION_PREVENT_SCREEN_SLEEP,
            CONFIG_OPTION_ENABLE_CONTROL_WINDOW,
        ],
        sort_key_prefix=0,
    )

    DEDUP_CONFIG_SECTION_DEFINITION = ConfigSectionDefinition(
        name=Config.SECTION_DEDUPLICATION,
        display_name=N_("Deduplication"),
        option_definitions=[
            CONFIG_OPTION_DEDUP_CARD_CONTROL,
            CONFIG_OPTION_DEDUP_BIB_LEG,
            CONFIG_OPTION_DEDUP_TIMEOUT_SECONDS,
        ],
        sort_key_prefix=1,
    )

    DATA_SOURCES_CONFIG_SECTION_DEFINITION = ConfigSectionDefinition(
        name=Config.SECTION_DATA_SOURCES,
        display_name=N_("Data Sources"),
        option_definitions=[],
        sort_key_prefix=12,
    )

    COMMON_CONFIG_SECTION_INTRO_SOUND_VERIFIER = ConfigVerifierDefinition(
        function=verify_sound,
        parameters=[
            ConfigSectionOptionDefinition(
                section_name=Config.SECTION_COMMON,
                option_definition=CONFIG_OPTION_INTRO_SOUND_FILE,
            ),
        ],
        message="The selected sound could not be played.",
    )

    CONFIG_OPTION_INTRO_SOUND_FILE.set_verifier(
        COMMON_CONFIG_SECTION_INTRO_SOUND_VERIFIER
    )

    COMMON_CONFIG_SECTION_TEST_SOUND_VERIFIER = ConfigVerifierDefinition(
        function=verify_sound,
        parameters=[
            ConfigSectionOptionDefinition(
                section_name=Config.SECTION_COMMON,
                option_definition=CONFIG_OPTION_TEST_SOUND_FILE,
            ),
        ],
        message="The selected sound could not be played.",
    )

    CONFIG_OPTION_TEST_SOUND_FILE.set_verifier(
        COMMON_CONFIG_SECTION_TEST_SOUND_VERIFIER
    )

    Config.register_config_section_definition(COMMON_CONFIG_SECTION_DEFINITION)
    Config.register_config_section_definition(DEDUP_CONFIG_SECTION_DEFINITION)
    Config.register_config_section_definition(DATA_SOURCES_CONFIG_SECTION_DEFINITION)

    @classmethod
    def config_section_definition(cls) -> ConfigSectionDefinition:
        return cls.COMMON_CONFIG_SECTION_DEFINITION

    @classmethod
    def get_config_section_definitions(cls) -> list[ConfigSectionDefinition]:
        return [
            cls.COMMON_CONFIG_SECTION_DEFINITION,
            cls.DEDUP_CONFIG_SECTION_DEFINITION,
            cls.DATA_SOURCES_CONFIG_SECTION_DEFINITION,
        ]

    def __init__(self):
        # ensure the parent's __init__ is called
        wx.Frame.__init__(self, None, wx.ID_ANY, "PreWarning " + __version__)
        ConfigConsumer.__init__(self)
        PunchListener.__init__(self)

        self.observer = None

        self.logger = logging.getLogger(self.__class__.__name__)

        # Lock for thread-safe last_sound_time access
        self._last_sound_time_lock = Lock()

        # Deduplication state
        self._dedup_lock = Lock()
        self._dedup_card_control: dict = {}
        self._dedup_bib_leg: dict = {}
        self._dedup_card_control_enabled: bool = False
        self._dedup_bib_leg_enabled: bool = False
        self._dedup_timeout: int = 0

        # Config variables
        self.interactive_mode = None
        self.announce_ip_on_startup = None
        self.intro_sound_trigger_timeout_seconds = None
        self.intro_sound_file = None
        self.test_sound_file = None
        self.add_pre_warnings_to_bottom = None
        self.punch_source_name = None
        self.start_list_source_name = None

        # Offset used to change the font size
        self.font_factor_offset = 0

        self.punch_source = None
        self.start_list_source = None

        # Hotkey binding definitions
        self.hotkey_bindings = [
            HotKeyBindingDefinition(
                name=N_("Settings"),
                hotkey=HotKeyDefinition(key_code=ord("S")).with_ctrl(),
                handler=self._config_dialog,
                description=N_("Opens the Settings Dialog"),
                bitmap_name=wx.ART_EXECUTABLE_FILE,
            ),
            HotKeyBindingDefinition(
                name=N_("Voice Manager"),
                hotkey=HotKeyDefinition(key_code=ord("M")).with_ctrl().with_shift(),
                handler=self._open_voice_manager,
                description=N_("Opens the Voice Manager dialog"),
                bitmap_name=wx.ART_CDROM,
            ),
            HotKeyBindingDefinition(
                name=N_("Control Window"),
                hotkey=HotKeyDefinition(key_code=ord("W")).with_ctrl(),
                handler=self._toggle_control_window,
                description=N_("Shows or hides the control window"),
                bitmap_name=wx.ART_REPORT_VIEW,
            ),
            HotKeyBindingDefinition(
                name=N_("Help"),
                hotkey=HotKeyDefinition(key_code=wx.WXK_F1),
                handler=self._help_dialog,
                description=N_("Opens the Help Dialog"),
                alternate_hotkeys=[
                    HotKeyDefinition(key_code=ord("H")).with_ctrl(),
                ],
                bitmap_name=wx.ART_HELP,
            ),
            HotKeyBindingDefinition(
                name=N_("About"),
                hotkey=HotKeyDefinition(key_code=ord("A")).with_ctrl(),
                handler=self._about_dialog,
                description=N_("Opens the About Dialog"),
                bitmap_name=wx.ART_INFORMATION,
            ),
            HotKeyBindingDefinition(
                name=N_("Full Screen"),
                hotkey=HotKeyDefinition(key_code=wx.WXK_F11),
                handler=self._toggle_full_screen,
                description=N_("Switches full screen on and off"),
                bitmap_name=wx.ART_FIND,
            ),
            HotKeyBindingDefinition(
                name=N_("Fake Punch"),
                hotkey=HotKeyDefinition(key_code=wx.WXK_SPACE).with_ctrl(),
                handler=self._simulate_punch,
                description=N_("Simulates a pre-warning"),
                alternate_hotkeys=[
                    HotKeyDefinition(key_code=ord("P")).with_ctrl(),
                ],
                bitmap_name=wx.ART_GO_DOWN,
            ),
            HotKeyBindingDefinition(
                name=N_("Refresh Display"),
                hotkey=HotKeyDefinition(key_code=wx.WXK_F5),
                handler=self._refresh,
                description=N_("Refreshes the display"),
                alternate_hotkeys=[
                    HotKeyDefinition(key_code=ord("R")).with_ctrl(),
                ],
                bitmap_name=wx.ART_LIST_VIEW,
            ),
            HotKeyBindingDefinition(
                name=N_("Clear Display"),
                hotkey=HotKeyDefinition(key_code=ord("C")).with_ctrl(),
                handler=self._clear,
                description=N_("Clears the display from pre-warning entries"),
                bitmap_name=wx.ART_DELETE,
            ),
            HotKeyBindingDefinition(
                name=N_("Play Testing Sound"),
                hotkey=HotKeyDefinition(key_code=ord("T")).with_ctrl(),
                handler=self._play_test_sound,
                description=N_("Plays a test sound"),
                bitmap_name=wx.ART_QUESTION,
            ),
            HotKeyBindingDefinition(
                name=N_("Announce IP Address"),
                hotkey=HotKeyDefinition(key_code=ord("I")).with_ctrl(),
                handler=self._notify_ip,
                description=N_("Reads the IP (v4) address aloud section for section"),
                bitmap_name=wx.ART_INFORMATION,
            ),
            HotKeyBindingDefinition(
                name="Print Sizes (debug)",
                hotkey=HotKeyDefinition(key_code=ord("V")).with_ctrl(),
                handler=self._print_sizes,
                description="Prints out sizes of GUI components (for debug purpose)",
                hidden=True,
                bitmap_name=wx.ART_TIP,
            ),
            HotKeyBindingDefinition(
                name=N_("Increase Font Size"),
                hotkey=HotKeyDefinition(key_code=wx.WXK_NUMPAD_ADD).with_ctrl(),
                handler=self._increase_font_size,
                description=N_("Increases the font size"),
                alternate_hotkeys=[
                    HotKeyDefinition(key_code=ord("+")).with_ctrl(),
                ],
                bitmap_name=wx.ART_PLUS,
            ),
            HotKeyBindingDefinition(
                name=N_("Decrease Font Size"),
                hotkey=HotKeyDefinition(key_code=wx.WXK_NUMPAD_SUBTRACT).with_ctrl(),
                handler=self._decrease_font_size,
                description=N_("Decreases the font size"),
                alternate_hotkeys=[
                    HotKeyDefinition(key_code=ord("-")).with_ctrl(),
                ],
                bitmap_name=wx.ART_MINUS,
            ),
            HotKeyBindingDefinition(
                name=N_("Restore Font Size"),
                hotkey=HotKeyDefinition(key_code=wx.WXK_NUMPAD0).with_ctrl(),
                handler=self._restore_font_size,
                description=N_("Restores the font size to default"),
                alternate_hotkeys=[
                    HotKeyDefinition(key_code=ord("0")).with_ctrl(),
                ],
                bitmap_name=wx.ART_UNDO,
            ),
            HotKeyBindingDefinition(
                name=N_("Exit"),
                hotkey=HotKeyDefinition(key_code=ord("X")).with_ctrl(),
                handler=self.Close,
                description=N_("Exits the application"),
                alternate_hotkeys=[
                    HotKeyDefinition(key_code=ord("Q")).with_ctrl(),
                    HotKeyDefinition(key_code=ord("D")).with_ctrl(),
                ],
                bitmap_name=wx.ART_QUIT,
            ),
        ]

        self._set_screen_and_size()

        # Used for manual tests.
        self.test_bib_number = 0
        self.test_leg_number = 0

        # Create the UI
        self._create_gui()

        # Start a timer to update the time on the clock.
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_timer, self.timer)
        self.timer.Start(200)

        self.Bind(wx.EVT_SIZE, self._on_resize)
        self.header_panel.Bind(wx.EVT_SIZE, self._on_resize_head)

        # Catch Clicking on the Corner X to close
        self.Bind(wx.EVT_CLOSE, self._close)

        # Pre-init attributes that may be accessed if the config dialog triggers
        # async events (timer ticks, config updates) during the validation loop.
        self._control_window: ControlWindow | None = None
        self._screen_sleep_inhibitor = ScreenSleepInhibitor()
        self._health_tick_counter = 0
        self._stats_punches_received = 0
        self._stats_punches_matched = 0
        self._stats_announcements = 0
        self._stats_dedup_skipped = 0
        self._last_punch_time: datetime | None = None
        self.health_monitor = HealthMonitor()

        # Read the configuration
        self.config = Config(CONFIGURATION_FILE)
        self.config.start()
        self._get_interactive_mode()
        validation_errors = self.config.validate()
        while len(validation_errors):
            if self.interactive_mode:
                self._config_dialog(True)
                validation_errors = self.config.validate()
            else:
                raise ValueError(
                    f"The configuration contains the following errors: {validation_errors!s}."
                )
        self._parse_config()

        # Init the sound util
        self.sound = Sound()

        # Init the control window
        self._init_control_window()

        self._apply_screen_sleep_setting()

        # Set up the queues used for punches and announcements
        self.punch_queue: Queue = Queue()
        self.announcement_queue: Queue = Queue()

        # Init the thread used to process punches from the punch queue
        self.punch_processor = Thread(
            target=self._process_punches, daemon=True, name="PunchProcessorThread"
        )

        # Init the thread used to process announcements from the announcement queue
        self.announcement_processor = Thread(
            target=self._process_announcements,
            daemon=True,
            name="AnnouncementProcessorThread",
        )
        self.last_sound_time = None

        self.update_sources()

        # Verify the configured control codes exist in the punch source
        self._verify_control_codes_at_startup()

        # Register health checks
        self.health_monitor.register_check(self._check_punch_source_health)
        self.health_monitor.register_check(self._check_start_list_source_health)
        self.health_monitor.register_check(self._check_voice_health)

        self.observer = Observer()
        self.observer.name = "LoggingConfFileObserverThread"
        self.observer.start()
        self.observer.schedule(
            event_handler=self, path=LOGGING_CONFIGURATION_FILE.parent.as_posix()
        )

        if not self.interactive_mode:
            self._toggle_full_screen()

    def __del__(self):
        self.stop()

    def stop(self):
        self.timer.Stop()
        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
        Config().stop()
        if self.punch_source is not None:
            self.punch_source.stop()
        if self.start_list_source is not None:
            self.start_list_source.stop()
        self._screen_sleep_inhibitor.uninhibit()
        if self._control_window is not None:
            self._control_window.Destroy()
            self._control_window = None

    @staticmethod
    def _get_portrait_screen() -> wx.Display | None:
        for display in (wx.Display(i) for i in range(wx.Display.GetCount())):
            geometry = display.GetGeometry()
            if geometry.GetHeight() > geometry.GetWidth():
                return display
        return None

    def _set_screen_and_size(self):
        display = self._get_portrait_screen()
        if display is None:
            display = wx.Display(self)

        self.SetPosition(display.GetClientArea().GetTopLeft())

        current_mode = display.GetCurrentMode()
        self.logger.debug(
            "Screen size: %dx%d", current_mode.GetWidth(), current_mode.GetHeight()
        )
        client_area = display.GetClientArea()
        self.logger.debug(
            "Client Area size: %dx%d", client_area.width, client_area.height
        )

        width = 600
        height = 800

        width = min(width, client_area.width)
        height = min(height, client_area.height)

        self.logger.debug("Frame size: %dx%d", width, height)

        self.SetMinSize(wx.Size(width, height))
        self.SetSize(wx.Size(width, height))
        self.Center()

    def on_modified(self, event: DirModifiedEvent | FileModifiedEvent):
        super().on_modified(event)

        src_path = event.src_path
        if Path(str(src_path)).resolve() == LOGGING_CONFIGURATION_FILE:
            _logger.debug("Updating logging configuration - before")
            _update_logging_configuration()
            _logger.debug("Updating logging configuration - after")

    def _create_gui(self):
        self.SetIcon(wx.Icon((APPLICATION_DIR / "favicon.ico").as_posix()))

        # Create the main panel
        self.main_panel = wx.Panel(parent=self, id=wx.ID_ANY, style=wx.WANTS_CHARS)
        self.main_panel.SetDoubleBuffered(True)
        self.main_panel.Bind(wx.EVT_CHAR_HOOK, self._on_key_press)

        self.main_panel_sizer = wx.BoxSizer(wx.VERTICAL)

        # The color for the header
        self.header_color = wx.LIGHT_GREY

        # Create the header panel
        self.header_panel = wx.Panel(
            parent=self.main_panel, id=wx.ID_ANY, style=wx.BORDER_SIMPLE
        )
        self.header_panel.SetBackgroundColour(self.header_color)

        self.header_panel_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Create the header label
        self.header_label = wx.StaticText(self.header_panel, label=_("Pre-Warning"))
        self.header_label.SetBackgroundColour(self.header_color)

        self.header_panel_sizer.Add(
            self.header_label, proportion=0, flag=wx.ALIGN_CENTER_VERTICAL
        )

        # Create the health indicator
        self.health_indicator = wx.StaticText(self.header_panel, label=" \u2b24 ")
        self.health_indicator.SetBackgroundColour(self.header_color)
        self.health_indicator.SetForegroundColour(COLOUR_OK)
        self.health_indicator.SetToolTip(_("All systems OK"))
        self.health_indicator.Bind(wx.EVT_LEFT_DOWN, self._on_health_indicator_click)
        self.header_panel_sizer.Add(
            self.health_indicator,
            proportion=0,
            flag=wx.ALIGN_CENTER_VERTICAL,
        )

        # Spacer to push clock to the right
        self.header_panel_sizer.AddStretchSpacer()

        # Create the clock/time label
        self.time_label = wx.lib.stattext.GenStaticText(
            self.header_panel, label="00:00:00"
        )
        self.time_label.SetBackgroundColour(self.header_color)

        self.header_panel_sizer.Add(
            self.time_label, proportion=0, flag=wx.RIGHT, border=5
        )

        self.header_panel.SetSizer(self.header_panel_sizer)

        self.main_panel_sizer.Add(
            self.header_panel,
            proportion=0,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT,
            border=2,
        )

        # Create the pre-warning grid panel
        self.grid_panel = wx.Panel(parent=self.main_panel, id=wx.ID_ANY)

        self.grid_panel_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Create the pre-warning grid
        self.prewarning_grid = _NoHighlightGrid(self.grid_panel)
        self.prewarning_grid.CreateGrid(0, 3)
        self.prewarning_grid.SetColLabelValue(COL_NR_TIME, _("Time"))
        self.prewarning_grid.SetColLabelValue(COL_NR_TEAM, _("Team"))
        self.prewarning_grid.SetColLabelValue(COL_NR_LEG, _("Leg"))
        self.prewarning_grid.SetColLabelAlignment(wx.LEFT, wx.CENTER)
        self.prewarning_grid.EnableEditing(False)
        self.prewarning_grid.EnableVisibleFocus(False)
        self.prewarning_grid.SetCellHighlightPenWidth(0)
        self.prewarning_grid.SetCellHighlightROPenWidth(0)
        self.prewarning_grid.SetSelectionBackground(
            self.prewarning_grid.GetDefaultCellBackgroundColour()
        )
        self.prewarning_grid.SetSelectionForeground(
            self.prewarning_grid.GetDefaultCellTextColour()
        )
        self.prewarning_grid.SetSelectionMode(wx.grid.Grid.GridSelectNone)
        self.prewarning_grid.DisableKeyboardScrolling()
        self.prewarning_grid.HideRowLabels()

        # Add filler row to get the column widths correct before any pre-warning arrives.
        self._add_filler_row()

        self.grid_panel_sizer.Add(self.prewarning_grid, proportion=1, flag=wx.EXPAND)

        self.grid_panel.SetSizer(self.grid_panel_sizer)

        self.main_panel_sizer.Add(
            self.grid_panel, proportion=1, flag=wx.EXPAND | wx.ALL, border=2
        )

        self.main_panel.SetSizer(self.main_panel_sizer)

        self.Bind(wx.EVT_CONTEXT_MENU, self._on_context_menu)

        self._calculate_sizes()

    # noinspection PyUnusedLocal
    def _on_timer(self, evt: wx.TimerEvent):
        new_time = strftime("%H:%M:%S")
        self.time_label.SetLabel(new_time)

        # Refresh health every 30 seconds (150 ticks * 200ms)
        self._health_tick_counter += 1
        if self._health_tick_counter >= 150:
            self._health_tick_counter = 0
            self._refresh_health()

    def _on_context_menu(self, event: wx.ContextMenuEvent):
        position = self.ScreenToClient(event.GetPosition())

        image_size = wx.Size(16, 16)

        menu = wx.Menu()
        for hotkey_binding in self.hotkey_bindings:
            if hotkey_binding.hidden:
                continue
            menu_item = wx.MenuItem(
                id=hotkey_binding.window_id,
                text=_(hotkey_binding.name),
                helpString=_(hotkey_binding.description),
            )
            if hotkey_binding.bitmap_name is not None:
                menu_item.SetBitmap(
                    wx.ArtProvider.GetBitmapBundle(
                        hotkey_binding.bitmap_name, client=wx.ART_MENU, size=image_size
                    )
                )
            menu_item = menu.Append(menu_item)
            self.Bind(wx.EVT_MENU, self._on_event_menu, menu_item)

        self.PopupMenu(menu, position)

        menu.Destroy()

    def _on_event_menu(self, event: wx.CommandEvent):
        item = None
        for hotkey_binding in self.hotkey_bindings:
            if hotkey_binding.window_id == event.GetId():
                item = hotkey_binding
                break
        if item is None:
            self.logger.error("_on_event_menu: Event window id not found.")
            raise ValueError("_on_event_menu: Event window id not found.")

        self.logger.debug("_on_event_menu: %s", item.name)

        item.handler()

    def _add_pre_warning(self, punch_time: str, team: str, leg: str):
        if self._has_filler_row():
            self.prewarning_grid.DeleteRows(ROW_ZERO)

        new_row = ROW_ZERO

        if self.add_pre_warnings_to_bottom:
            new_row = self.prewarning_grid.GetNumberRows()

        self.prewarning_grid.InsertRows(pos=new_row)

        self.prewarning_grid.SetCellValue(new_row, COL_NR_TIME, punch_time)
        self.prewarning_grid.SetCellValue(new_row, COL_NR_TEAM, team)
        self.prewarning_grid.SetCellValue(new_row, COL_NR_LEG, leg)

        self._update_column_sizes()

        self._remove_non_visible_rows()

        # Forward to control window
        if self._control_window is not None and self._control_window.IsShown():
            wx.CallAfter(self._control_window.add_prewarning, punch_time, team, leg)

    def _add_pre_warning_with_refresh(
        self, passed_time: str, bib_number: str, relay_leg: str
    ):
        self._add_pre_warning(passed_time, bib_number, relay_leg)
        self.prewarning_grid.Refresh()
        self.prewarning_grid.Update()

    def _add_filler_row(self):
        self.prewarning_grid.InsertRows()
        self.prewarning_grid.SetCellValue(ROW_ZERO, COL_NR_TIME, "00:00:00")
        self.prewarning_grid.SetCellValue(ROW_ZERO, COL_NR_TEAM, "00")
        self.prewarning_grid.SetCellValue(ROW_ZERO, COL_NR_LEG, "0")
        self.prewarning_grid.SetCellTextColour(
            ROW_ZERO,
            COL_NR_TIME,
            self.prewarning_grid.GetCellBackgroundColour(ROW_ZERO, COL_NR_TIME),
        )
        self.prewarning_grid.SetCellTextColour(
            ROW_ZERO,
            COL_NR_TEAM,
            self.prewarning_grid.GetCellBackgroundColour(ROW_ZERO, COL_NR_TEAM),
        )
        self.prewarning_grid.SetCellTextColour(
            ROW_ZERO,
            COL_NR_LEG,
            self.prewarning_grid.GetCellBackgroundColour(ROW_ZERO, COL_NR_LEG),
        )

    def _has_filler_row(self):
        return (
            self.prewarning_grid.GetNumberRows() == 1
            and self.prewarning_grid.GetCellTextColour(ROW_ZERO, COL_NR_TIME)
            == self.prewarning_grid.GetCellBackgroundColour(ROW_ZERO, COL_NR_TIME)
        )

    def _remove_non_visible_rows(self):
        if not self._has_filler_row():
            last_row = self.prewarning_grid.GetNumberRows() - 1
            while last_row >= 0 and not self.prewarning_grid.IsVisible(
                self.prewarning_grid.GetNumberRows() - 1,
                COL_NR_TIME,
                wholeCellVisible=True,
            ):
                if self.add_pre_warnings_to_bottom:
                    self.logger.debug("DELETE 0")
                    self.prewarning_grid.DeleteRows(ROW_ZERO)
                else:
                    self.logger.debug("DELETE LAST %d", last_row)
                    self.prewarning_grid.DeleteRows(last_row)
                last_row = self.prewarning_grid.GetNumberRows() - 1

    def _clear(self):
        self.prewarning_grid.DeleteRows(ROW_ZERO, self.prewarning_grid.GetNumberRows())
        self._add_filler_row()
        self._calculate_sizes()

    def _refresh(self):
        orig_size = self.GetSize()
        new_size = wx.Size(
            width=orig_size.GetWidth() + 1, height=orig_size.GetHeight() + 1
        )
        self.SetSize(new_size)
        self.SetSize(orig_size)

        self._calculate_sizes()

    def _calculate_sizes(self):
        usable_size = wx.Window.GetClientSize(self)
        self.logger.debug(
            "calculate_sizes: %dx%d", usable_size.GetWidth(), usable_size.GetHeight()
        )

        # font_factor = 28
        font_factor = 27
        if usable_size.GetWidth() <= usable_size.GetHeight():
            # font_factor = 15
            font_factor = 16
        self.logger.debug("Font factor: %d", font_factor)
        font_factor += self.font_factor_offset
        self.logger.debug("Font factor with offset: %d", font_factor)

        default_font_size = int(usable_size.GetWidth() / font_factor)
        self.logger.debug("Font size: %d", default_font_size)

        header_font = self.header_label.GetFont()
        header_font.SetPointSize(default_font_size)
        header_font = header_font.Bold()
        self.header_label.SetFont(header_font)

        self.health_indicator.SetFont(header_font)

        self.time_label.SetFont(header_font)

        label_font = self.prewarning_grid.GetLabelFont()
        label_font_size = int(default_font_size / 5)
        label_font_size = max(9, label_font_size)
        label_font.SetPointSize(label_font_size)
        self.prewarning_grid.SetLabelFont(label_font)

        cell_font = self.prewarning_grid.GetDefaultCellFont()
        cell_font.SetPointSize(default_font_size)
        cell_font = cell_font.Bold()
        self.prewarning_grid.SetDefaultCellFont(cell_font)

        self._update_column_sizes()

        wx.CallAfter(self._remove_non_visible_rows)

    def _update_column_sizes(self):
        self.prewarning_grid.Freeze()
        self.prewarning_grid.AutoSizeRows()
        self.prewarning_grid.AutoSizeColumns()

        self._print_sizes()
        (grid_width, _grid_height) = self.grid_panel.GetSize()

        col_size_leg = self.prewarning_grid.GetColSize(COL_NR_LEG)
        new_col_size_leg = col_size_leg + int(col_size_leg / 3)
        self.prewarning_grid.SetColSize(COL_NR_LEG, new_col_size_leg)

        col_size_team = self.prewarning_grid.GetColSize(COL_NR_TEAM)
        new_col_size_team = col_size_team + int(col_size_team / 3)
        self.prewarning_grid.SetColSize(COL_NR_TEAM, new_col_size_team)

        col_size_time = grid_width - new_col_size_leg - new_col_size_team
        col_size_time = max(10, col_size_time)
        self.prewarning_grid.SetColSize(COL_NR_TIME, col_size_time)
        self.prewarning_grid.Thaw()

    def _print_sizes(self):
        self.logger.debug("PRINT SIZES")
        (header_panel_width, header_panel_height) = self.header_panel.GetSize()
        self.logger.info(
            "header_panel.GetSize(): %dx%d", header_panel_width, header_panel_height
        )
        (grid_panel_width, grid__panel_height) = self.grid_panel.GetSize()
        self.logger.info(
            "grid_panel.GetSize(): %dx%d", grid_panel_width, grid__panel_height
        )
        (grid_width, grid_height) = self.prewarning_grid.GetSize()
        self.logger.info("prewarning_grid.GetSize(): %dx%d", grid_width, grid_height)

    def _on_resize(self, event: wx.SizeEvent):
        self.logger.debug(
            "EventSize: %dx%d", event.GetSize().GetWidth(), event.GetSize().GetHeight()
        )
        self._calculate_sizes()

        event.Skip()

    def _on_resize_head(self, event: wx.SizeEvent):
        self.logger.debug(
            "HEAD EventSize: %dx%d",
            event.GetSize().GetWidth(),
            event.GetSize().GetHeight(),
        )
        self._calculate_sizes()

        event.Skip()

    def _about_dialog(self):
        self.logger.debug("About Dialog")
        about_dialog = AboutDialog(self, app_version=__version__)
        about_dialog.Show()

    def _help_dialog(self):
        self.logger.debug("Help Dialog")
        help_dialog = HelpDialog(
            self, app_version=__version__, hotkey_bindings=self.hotkey_bindings
        )
        help_dialog.Show()

    def _update_labels(self):
        """Refresh all translated labels on the main window."""
        self.header_label.SetLabel(_("Pre-Warning"))
        self.header_panel.Layout()
        self.prewarning_grid.SetColLabelValue(COL_NR_TIME, _("Time"))
        self.prewarning_grid.SetColLabelValue(COL_NR_TEAM, _("Team"))
        self.prewarning_grid.SetColLabelValue(COL_NR_LEG, _("Leg"))

    def _config_dialog(
        self,
        perform_validation: bool = False,
        assist_option_location: tuple[str, str] | None = None,
    ):
        start = time()
        state_providers = {}

        dialog_parent = self
        control_was_active = (
            self._control_window is not None
            and self._control_window.IsShown()
            and self._control_window.IsActive()
        )
        if self.punch_source is not None:
            state_providers[self.punch_source.name] = self.punch_source
        if MeosInfoServer.has_instance():
            state_providers[MeosInfoServer.CONFIG_SECTION_MEOS] = MeosInfoServer()

        old_lang = self.config.get_section(Config.SECTION_COMMON).get(
            self.CONFIG_OPTION_LANGUAGE.name,
            self.CONFIG_OPTION_LANGUAGE.default_value,
        )
        saved_lang = [old_lang]  # mutable so the save callback can update it

        def _on_language_changed(value):
            set_language(value)
            self._update_labels()
            if self._control_window is not None:
                self._control_window.refresh_translations()
                self._update_control_window()
            if settings_dialog:
                settings_dialog.refresh_translations()

        def _on_save():
            saved_lang[0] = self.config.get_section(Config.SECTION_COMMON).get(
                self.CONFIG_OPTION_LANGUAGE.name,
                self.CONFIG_OPTION_LANGUAGE.default_value,
            )

        self.CONFIG_OPTION_LANGUAGE.on_change = _on_language_changed

        settings_dialog = ConfigDialog(
            self.config,
            dialog_parent,
            title=_("Settings"),
            state_providers=state_providers,
            on_save=_on_save,
        )
        created = time()
        self.logger.debug("Config Dialog created: %d seconds", created - start)

        if control_was_active and self._control_window is not None:
            settings_dialog.CenterOnParent()
            # Move to control window's display
            ctrl_display = wx.Display(wx.Display.GetFromWindow(self._control_window))
            area = ctrl_display.GetClientArea()
            dlg_size = settings_dialog.GetSize()
            x = area.GetLeft() + (area.GetWidth() - dlg_size.GetWidth()) // 2
            y = area.GetTop() + (area.GetHeight() - dlg_size.GetHeight()) // 2
            settings_dialog.SetPosition(wx.Point(x, y))
        else:
            settings_dialog.Center()

        settings_dialog.TransferDataToWindow()

        if perform_validation:
            settings_dialog.Validate()

        if assist_option_location is not None:
            section_name, option_name = assist_option_location
            wx.CallAfter(settings_dialog.assist_option, section_name, option_name)

        res = settings_dialog.ShowModal()

        if res == wx.ID_CANCEL and perform_validation:
            sys.exit(1)
        settings_dialog.Destroy()

        self.CONFIG_OPTION_LANGUAGE.on_change = None

        if res == wx.ID_CANCEL:
            # Revert to the last saved language (initial or after Save was clicked)
            set_language(saved_lang[0])
            self._update_labels()
            if self._control_window is not None:
                self._control_window.refresh_translations()
                self._update_control_window()
            self.config.get_section(Config.SECTION_COMMON)[
                self.CONFIG_OPTION_LANGUAGE.name
            ] = saved_lang[0]
        self._refresh_health()

        if control_was_active and self._control_window is not None:
            self._control_window.Raise()

    # -- Health indicator --------------------------------------------------

    def _check_punch_source_health(self) -> list[HealthIssue]:
        issues: list[HealthIssue] = []
        if self.punch_source is None:
            issues.append(
                HealthIssue(
                    message=_("No punch source configured."),
                    status=HealthStatus.ERROR,
                    action=HealthAction.SETTINGS,
                )
            )
        elif not self.punch_source.is_running():
            issues.append(
                HealthIssue(
                    message=_("Punch source is not running."),
                    status=HealthStatus.ERROR,
                    action=HealthAction.SETTINGS,
                )
            )
        else:
            source_status, source_msg = self.punch_source.health_status
            if source_status == HealthStatus.ERROR:
                issues.append(
                    HealthIssue(
                        message=_("Punch source error: {message}").format(
                            message=source_msg
                        ),
                        status=HealthStatus.ERROR,
                        action=HealthAction.SETTINGS,
                    )
                )
        return issues

    def _check_start_list_source_health(self) -> list[HealthIssue]:
        issues: list[HealthIssue] = []
        if self.start_list_source is None:
            issues.append(
                HealthIssue(
                    message=_("No start list source configured."),
                    status=HealthStatus.ERROR,
                    action=HealthAction.SETTINGS,
                )
            )
        elif not self.start_list_source.is_running():
            issues.append(
                HealthIssue(
                    message=_("Start list source is not running."),
                    status=HealthStatus.ERROR,
                    action=HealthAction.SETTINGS,
                )
            )
        else:
            # Check source-reported health
            source_status, source_msg = self.start_list_source.health_status
            if source_status == HealthStatus.ERROR:
                issues.append(
                    HealthIssue(
                        message=_("Start list source error: {message}").format(
                            message=source_msg
                        ),
                        status=HealthStatus.ERROR,
                        action=HealthAction.SETTINGS,
                    )
                )
            # Check for non-relay competition: runners exist but no teams
            runner_count = self.start_list_source.get_runner_count()
            team_count = self.start_list_source.get_team_count()
            if runner_count is not None and runner_count > 0 and team_count is None:
                issues.append(
                    HealthIssue(
                        message=_(
                            "Start list has no team data. "
                            "The competition is probably not a relay."
                        ),
                        status=HealthStatus.ERROR,
                        action=HealthAction.SETTINGS,
                    )
                )
            elif (
                team_count is not None
                and team_count > 0
                and (runner_count is None or runner_count == 0)
            ):
                issues.append(
                    HealthIssue(
                        message=_(
                            "Start list has no runners with SI cards registered."
                        ),
                        status=HealthStatus.ERROR,
                        action=HealthAction.SETTINGS,
                    )
                )
            elif (team_count is None or team_count == 0) and (
                runner_count is None or runner_count == 0
            ):
                issues.append(
                    HealthIssue(
                        message=_(
                            "Start list has no data. "
                            "The competition may be empty or not loaded."
                        ),
                        status=HealthStatus.ERROR,
                        action=HealthAction.SETTINGS,
                    )
                )
        return issues

    def _check_voice_health(self) -> list[HealthIssue]:
        from utils.voice_manager_dialog import (
            CONFIG_OPTION_EXTRA_RANGES,
            DEFAULT_RANGE_END,
            DEFAULT_RANGE_START,
            VOICEMANAGER_SECTION_NAME,
            _list_installed_voices,
            get_installed_voice_shortnames,
            parse_extra_ranges,
        )

        issues: list[HealthIssue] = []

        # Check if any voices are installed
        voices = get_installed_voice_shortnames()
        if not voices:
            issues.append(
                HealthIssue(
                    message=_("No voices installed."),
                    status=HealthStatus.WARNING,
                    action=HealthAction.VOICE_MANAGER,
                )
            )
        else:
            # Check if installed voices are complete
            installed = _list_installed_voices()
            incomplete = [iv for iv in installed if not iv.complete]
            if incomplete:
                names = ", ".join(iv.shortname for iv in incomplete)
                issues.append(
                    HealthIssue(
                        message=_("Incomplete voices: {names}").format(names=names),
                        status=HealthStatus.WARNING,
                        action=HealthAction.VOICE_MANAGER,
                    )
                )

        # Check bib range coverage
        if self.start_list_source is not None:
            bib_range = self.start_list_source.get_bib_range()
            if bib_range is not None:
                bib_min, bib_max = bib_range
                vm_section = Config().get_section(VOICEMANAGER_SECTION_NAME)
                ranges = [(DEFAULT_RANGE_START, DEFAULT_RANGE_END)]
                extra = parse_extra_ranges(
                    vm_section.get(CONFIG_OPTION_EXTRA_RANGES.name, "")
                )
                ranges.extend(extra)

                uncovered: set[int] = set(range(bib_min, bib_max + 1))
                for r_start, r_end in ranges:
                    uncovered -= set(range(r_start, r_end + 1))

                if uncovered:
                    issues.append(
                        HealthIssue(
                            message=_(
                                "Bib number range ({min} - {max}) not fully covered by voice number ranges."
                            ).format(min=bib_min, max=bib_max),
                            status=HealthStatus.WARNING,
                            action=HealthAction.VOICE_MANAGER,
                        )
                    )

        return issues

    def _refresh_health(self) -> None:
        """Re-evaluate health and update the indicator."""
        status, issues = self.health_monitor.evaluate()

        # Build stats section
        stats_lines: list[str] = []

        # Source info
        ps_name = type(self.punch_source).display_name if self.punch_source else "-"
        ps_status = (
            _("Running")
            if self.punch_source and self.punch_source.is_running()
            else _("Stopped")
        )
        stats_lines.append(f"{_('Punch source')}: {ps_name} ({ps_status})")

        sls_name = (
            type(self.start_list_source).display_name if self.start_list_source else "-"
        )
        sls_status = (
            _("Running")
            if self.start_list_source and self.start_list_source.is_running()
            else _("Stopped")
        )
        stats_lines.append(f"{_('Start list source')}: {sls_name} ({sls_status})")

        # Bib range
        if self.start_list_source is not None:
            bib_range = self.start_list_source.get_bib_range()
            if bib_range is not None:
                stats_lines.append(f"{_('Bib range')}: {bib_range[0]} - {bib_range[1]}")
            else:
                stats_lines.append(f"{_('Bib range')}: -")
            team_count = self.start_list_source.get_team_count()
            if team_count is not None:
                stats_lines.append(f"{_('Teams')}: {team_count}")
            else:
                stats_lines.append(f"{_('Teams')}: -")
            runner_count = self.start_list_source.get_runner_count()
            if runner_count is not None:
                stats_lines.append(f"{_('Runners (SI card)')}: {runner_count}")
            else:
                stats_lines.append(f"{_('Runners (SI card)')}: -")

        # Voices
        from utils.voice_manager_dialog import get_installed_voice_shortnames

        voice_count = len(get_installed_voice_shortnames())
        stats_lines.append(f"{_('Installed voices')}: {voice_count}")

        # Session stats
        stats_lines.append(f"{_('Punches received')}: {self._stats_punches_received}")
        stats_lines.append(f"{_('Punches matched')}: {self._stats_punches_matched}")
        stats_lines.append(f"{_('Announcements')}: {self._stats_announcements}")

        # Screen sleep status
        if self._screen_sleep_inhibitor.is_active:
            stats_lines.append(f"{_('Screen sleep')}: {_('Prevented')}")
        else:
            stats_lines.append(f"{_('Screen sleep')}: {_('Normal')}")

        # Build tooltip
        if status == HealthStatus.OK:
            self.health_indicator.SetForegroundColour(COLOUR_OK)
            tooltip = _("All systems OK") + "\n\n" + "\n".join(stats_lines)
        elif status == HealthStatus.WARNING:
            self.health_indicator.SetForegroundColour(COLOUR_WARNING)
            issue_lines = "\n".join(f"\u2022 {i.message}" for i in issues)
            tooltip = issue_lines + "\n\n" + "\n".join(stats_lines)
        else:
            self.health_indicator.SetForegroundColour(COLOUR_ERROR)
            issue_lines = "\n".join(f"\u2022 {i.message}" for i in issues)
            tooltip = issue_lines + "\n\n" + "\n".join(stats_lines)

        self.health_indicator.SetToolTip(tooltip)
        if status == HealthStatus.OK:
            self.health_indicator.SetCursor(wx.Cursor(wx.CURSOR_ARROW))
        else:
            self.health_indicator.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        self.health_indicator.Refresh()

        self._update_control_window()

    def _on_health_indicator_click(self, event: wx.MouseEvent) -> None:
        """Open the relevant dialog based on current health issues."""
        self._on_health_indicator_click_action()

    def _on_health_indicator_click_action(self):
        """Open the relevant dialog based on current health issues."""
        _, issues = self.health_monitor.evaluate()
        action = self.health_monitor.get_primary_action(issues)
        if action == HealthAction.VOICE_MANAGER:
            self._open_voice_manager()
        elif action == HealthAction.SETTINGS:
            self._config_dialog()

    def _apply_screen_sleep_setting(self) -> None:
        """Enable or disable screen sleep prevention based on config."""
        config_section = self.config.get_section(Config.SECTION_COMMON)
        prevent = self.CONFIG_OPTION_PREVENT_SCREEN_SLEEP.get_value(config_section)
        if prevent:
            self._screen_sleep_inhibitor.inhibit()
        else:
            self._screen_sleep_inhibitor.uninhibit()
        self._update_control_window()

    def _init_control_window(self) -> None:
        """Create and show the control window if enabled and a landscape display exists."""
        config_section = self.config.get_section(Config.SECTION_COMMON)
        enabled = self.CONFIG_OPTION_ENABLE_CONTROL_WINDOW.get_value(config_section)
        if not enabled:
            return
        if wx.Display.GetCount() < 2:
            return

        main_display = wx.Display(wx.Display.GetFromWindow(self))
        landscape = ControlWindow.find_landscape_display(main_display)
        if landscape is None:
            return

        self._control_window = ControlWindow(
            parent=self,
            action_handlers={
                "settings": self._config_dialog,
                "voice_manager": self._open_voice_manager,
                "clear": self._clear,
                "fake_punch": self._simulate_punch,
                "test_sound": self._play_test_sound,
                "full_screen": self._toggle_full_screen,
                "health_dot_click": self._on_health_indicator_click_action,
                "exit": self.Close,
            },
            update_callback=self._refresh_health,
            key_handler=self._on_key_press,
        )
        self._control_window.position_on_display(landscape)
        self._control_window.Show()

    def _toggle_control_window(self) -> None:
        """Show or hide the control window."""
        if self._control_window is None:
            # Create it if it doesn't exist yet
            main_display = wx.Display(wx.Display.GetFromWindow(self))
            landscape = ControlWindow.find_landscape_display(main_display)
            self._control_window = ControlWindow(
                parent=self,
                action_handlers={
                    "settings": self._config_dialog,
                    "voice_manager": self._open_voice_manager,
                    "clear": self._clear,
                    "fake_punch": self._simulate_punch,
                    "test_sound": self._play_test_sound,
                    "full_screen": self._toggle_full_screen,
                    "health_dot_click": self._on_health_indicator_click_action,
                    "exit": self.Close,
                },
                update_callback=self._refresh_health,
                key_handler=self._on_key_press,
            )
            if landscape is not None:
                self._control_window.position_on_display(landscape)
            self._control_window.Show()
            self._update_control_window()
        elif self._control_window.IsShown():
            self._control_window.Hide()
        else:
            self._control_window.Show()
            self._control_window.Raise()

    def _update_control_window(self) -> None:
        """Push current health/stats data to the control window."""
        if self._control_window is None or not self._control_window.IsShown():
            return

        # Health items
        health_items: list[tuple[str, str, wx.Colour | None, str]] = []

        # Punch source — always show name and status
        ps_name = _(type(self.punch_source).display_name) if self.punch_source else "-"
        ps_status = (
            _("Running")
            if self.punch_source and self.punch_source.is_running()
            else _("Stopped")
        )
        punch_issues = self._check_punch_source_health()
        if punch_issues:
            colour = (
                COLOUR_ERROR
                if punch_issues[0].status == HealthStatus.ERROR
                else COLOUR_WARNING
            )
        else:
            colour = COLOUR_OK_TEXT
        health_items.append(
            (
                _("Punch source"),
                f"{ps_name} ({ps_status})",
                colour,
                _("The configured punch source and its current status."),
            )
        )
        for issue in punch_issues:
            issue_colour = (
                COLOUR_ERROR if issue.status == HealthStatus.ERROR else COLOUR_WARNING
            )
            health_items.append(
                (
                    "",
                    issue.message,
                    issue_colour,
                    issue.message,
                )
            )

        # Control codes used for pre-warning
        control_codes = (
            self.punch_source.get_control_codes() if self.punch_source else []
        )
        health_items.append(
            (
                _("Control codes"),
                " ".join(control_codes) if control_codes else "-",
                None,
                _("The control codes used to select punches for pre-warning."),
            )
        )

        # Start list source — always show name and status
        sls_name = (
            _(type(self.start_list_source).display_name)
            if self.start_list_source
            else "-"
        )
        sls_status = (
            _("Running")
            if self.start_list_source and self.start_list_source.is_running()
            else _("Stopped")
        )
        sls_issues = self._check_start_list_source_health()
        if sls_issues:
            colour = (
                COLOUR_ERROR
                if sls_issues[0].status == HealthStatus.ERROR
                else COLOUR_WARNING
            )
        else:
            colour = COLOUR_OK_TEXT
        health_items.append(
            (
                _("Start list source"),
                f"{sls_name} ({sls_status})",
                colour,
                _("The configured start list source and its current status."),
            )
        )
        for issue in sls_issues:
            issue_colour = (
                COLOUR_ERROR if issue.status == HealthStatus.ERROR else COLOUR_WARNING
            )
            health_items.append(
                (
                    "",
                    issue.message,
                    issue_colour,
                    issue.message,
                )
            )

        # IP address
        health_items.append(
            (
                _("IP address"),
                self._get_local_ip(),
                None,
                _("The local network IP address of this computer."),
            )
        )

        if self._screen_sleep_inhibitor.is_active:
            health_items.append(
                (
                    _("Screen sleep"),
                    _("Prevented"),
                    COLOUR_OK_TEXT,
                    _("Whether the display is prevented from turning off."),
                )
            )
        else:
            health_items.append(
                (
                    _("Screen sleep"),
                    _("Normal"),
                    None,
                    _("Whether the display is prevented from turning off."),
                )
            )

        # Full screen status
        fs_hotkey = ""
        for binding in self.hotkey_bindings:
            if binding.handler == self._toggle_full_screen:
                fs_hotkey = str(binding.hotkey)
                break
        fs_tooltip = _(
            "Whether the main window is in full screen mode. Toggle with {hotkey}."
        ).format(hotkey=fs_hotkey)
        if self.IsFullScreen():
            health_items.append(
                (
                    _("Full Screen"),
                    _("Yes"),
                    None,
                    fs_tooltip,
                )
            )
        else:
            health_items.append(
                (
                    _("Full Screen"),
                    _("No"),
                    None,
                    fs_tooltip,
                )
            )

        # Health check results
        status, issues = self.health_monitor.evaluate()

        voice_issues = self._check_voice_health()

        if voice_issues:
            issue = voice_issues[0]
            colour = (
                COLOUR_ERROR if issue.status == HealthStatus.ERROR else COLOUR_WARNING
            )
            health_items.append(
                (
                    _("Voice check"),
                    issue.message,
                    colour,
                    _("Checks that voices are installed and complete."),
                )
            )
        else:
            health_items.append(
                (
                    _("Voice check"),
                    _("OK"),
                    COLOUR_OK_TEXT,
                    _("Checks that voices are installed and complete."),
                )
            )

        self._control_window.update_health(health_items)

        # Stats items
        stats_items: list[tuple[str, str, str]] = []
        stats_items.append(
            (
                _("Punches received"),
                str(self._stats_punches_received),
                _("Total number of punches received from the punch source."),
            )
        )
        stats_items.append(
            (
                _("Punches matched"),
                str(self._stats_punches_matched),
                _("Punches successfully matched to a team in the start list."),
            )
        )
        stats_items.append(
            (
                _("Announcements"),
                str(self._stats_announcements),
                _("Number of pre-warnings announced (displayed and read aloud)."),
            )
        )
        stats_items.append(
            (
                _("Dedup skipped"),
                str(self._stats_dedup_skipped),
                _("Punches skipped by deduplication rules."),
            )
        )
        stats_items.append(
            (
                _("Last punch received"),
                self._last_punch_time.strftime("%H:%M:%S")
                if self._last_punch_time
                else "-",
                _("Time when the last punch was received by the system."),
            )
        )

        if self.start_list_source is not None:
            bib_range = self.start_list_source.get_bib_range()
            if bib_range is not None:
                stats_items.append(
                    (
                        _("Bib range"),
                        f"{bib_range[0]} - {bib_range[1]}",
                        _("The range of team bib numbers in the start list."),
                    )
                )
            else:
                stats_items.append(
                    (
                        _("Bib range"),
                        "-",
                        _("The range of team bib numbers in the start list."),
                    )
                )
            team_count = self.start_list_source.get_team_count()
            stats_items.append(
                (
                    _("Teams"),
                    str(team_count) if team_count is not None else "-",
                    _("Number of teams in the start list."),
                )
            )
            runner_count = self.start_list_source.get_runner_count()
            stats_items.append(
                (
                    _("Runners (SI card)"),
                    str(runner_count) if runner_count is not None else "-",
                    _(
                        "Number of runners with an SI card registered in the start list."
                    ),
                )
            )
        else:
            stats_items.append(
                (
                    _("Bib range"),
                    "-",
                    _("The range of team bib numbers in the start list."),
                )
            )
            stats_items.append(
                (
                    _("Teams"),
                    "-",
                    _("Number of teams in the start list."),
                )
            )
            stats_items.append(
                (
                    _("Runners (SI card)"),
                    "-",
                    _(
                        "Number of runners with an SI card registered in the start list."
                    ),
                )
            )

        from utils.voice_manager_dialog import get_installed_voice_shortnames

        voice_count = len(get_installed_voice_shortnames())
        stats_items.append(
            (
                _("Installed voices"),
                str(voice_count),
                _("Number of TTS voices installed for announcements."),
            )
        )

        self._control_window.update_stats(stats_items)

        # Status dot (reuses status/issues from above)
        if status == HealthStatus.OK:
            dot_colour = COLOUR_OK
            dot_tooltip = _("All systems OK")
        elif status == HealthStatus.WARNING:
            dot_colour = COLOUR_WARNING
            dot_tooltip = "\n".join(f"\u2022 {i.message}" for i in issues)
        else:
            dot_colour = COLOUR_ERROR
            dot_tooltip = "\n".join(f"\u2022 {i.message}" for i in issues)
        self._control_window.update_status_dot(
            dot_colour, dot_tooltip, actionable=status != HealthStatus.OK
        )

    def _toggle_full_screen(self):
        self.logger.debug("Toggle Full Screen")
        if self.IsFullScreen():
            self.ShowFullScreen(False, style=wx.FULLSCREEN_ALL)
        else:
            self.ShowFullScreen(True, style=wx.FULLSCREEN_ALL)
        self._update_control_window()

    def _simulate_punch(self):
        self.logger.debug("Simulate Punch")
        self.test_bib_number += 10
        self.test_leg_number += 1
        self._add_pre_warning(
            strftime("%H:%M:%S"), str(self.test_bib_number), str(self.test_leg_number)
        )
        self.announcement_queue.put(
            {
                _ANNOUNCE_KEY_VOICE: self.sound.resolve_voice(None),
                _ANNOUNCE_KEY_SOUND: str(self.test_bib_number),
            }
        )

    def _play_test_sound(self):
        self.logger.debug("Play Test Sound")
        voice = self.sound.resolve_voice(None)
        test_file = (
            self.test_sound_file.as_posix()
            if self.test_sound_file
            else TESTING_FILENAME
        )
        self.sound.play_voice_sound(test_file, voice)

    def _open_voice_manager(self):
        self.logger.debug("Open Voice Manager")
        dialog_parent = self
        control_was_active = (
            self._control_window is not None
            and self._control_window.IsShown()
            and self._control_window.IsActive()
        )
        bib_range = None
        if self.start_list_source is not None:
            bib_range = self.start_list_source.get_bib_range()
        dlg = VoiceManagerDialog(dialog_parent, bib_range=bib_range)
        if control_was_active and self._control_window is not None:
            ctrl_display = wx.Display(wx.Display.GetFromWindow(self._control_window))
            area = ctrl_display.GetClientArea()
            dlg_size = dlg.GetSize()
            x = area.GetLeft() + (area.GetWidth() - dlg_size.GetWidth()) // 2
            y = area.GetTop() + (area.GetHeight() - dlg_size.GetHeight()) // 2
            dlg.SetPosition(wx.Point(x, y))
        dlg.ShowModal()
        dlg.Destroy()
        self._refresh_health()
        if control_was_active and self._control_window is not None:
            self._control_window.Raise()

    def _notify_ip(self):
        self.logger.debug("Notify IP")
        local_ip_address = self._get_local_ip()
        self.logger.debug("local_ip_address: %s", local_ip_address)
        for number in local_ip_address.split("."):
            self.announcement_queue.put(
                {_ANNOUNCE_KEY_VOICE: None, _ANNOUNCE_KEY_SOUND: number}
            )

    @staticmethod
    def _get_local_ip() -> str:
        """Get the local IPv4 address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # RFC 5737 TEST-NET-1 address — reserved for documentation, never routable.
            # Connecting a UDP socket to any address determines the local interface
            # without sending any packets.
            s.connect(("192.0.2.1", 1))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except OSError:
            return "-"

    def _close(self, event=None):
        self.logger.debug("Close")
        self.stop()
        self.Unbind(wx.EVT_CLOSE, handler=self._close)
        self.Close(True)

    def _increase_font_size(self):
        self.logger.debug("Increase Font Size")
        self.font_factor_offset -= 1
        self._calculate_sizes()
        wx.CallAfter(self._refresh)

    def _decrease_font_size(self):
        self.logger.debug("Decrease Font Size")
        self.font_factor_offset += 1
        self._calculate_sizes()
        wx.CallAfter(self._refresh)

    def _restore_font_size(self):
        self.logger.debug("Restore Font Size")
        self.font_factor_offset = 0
        self._calculate_sizes()
        wx.CallAfter(self._refresh)

    def _on_key_press(self, key_event: wx.KeyEvent):
        self.logger.debug("_on_key_press: %s pushed!", key_event_to_str(key_event))

        for key_binding in self.hotkey_bindings:
            if key_binding.matches(key_event):
                key_binding.handler()
                return

        key_event.Skip()

    def config_updated(self, section_names: list[str]):
        wx.CallAfter(self._apply_config_update)

    def _on_start_list_health_changed(self) -> None:
        """Called when start list source health status changes."""
        wx.CallAfter(self._refresh_health)

    def _on_punch_source_health_changed(self) -> None:
        """Called when punch source health status changes."""
        wx.CallAfter(self._refresh_health)

    def _on_start_list_data_changed(self) -> None:
        """Called when start list data is loaded or refreshed."""
        wx.CallAfter(self._refresh_health)

    def _apply_config_update(self):
        self._parse_config()
        self.update_sources()
        if self.punch_source is not None and not self.punch_source.is_running():
            self.punch_source.start()
        start_not_running = (
            self.start_list_source is not None
            and not self.start_list_source.is_running()
        )
        if start_not_running and self.start_list_source is not None:
            self.start_list_source.start()
        self._apply_screen_sleep_setting()
        self._refresh_health()

    def _verify_control_codes_at_startup(self) -> None:
        """Verify the configured control codes exist in the punch source.

        Mirrors the config validation loop: in interactive mode the operator
        is shown the settings dialog to correct the configuration and the
        check is repeated; in non-interactive mode a failure raises.

        Sources that cannot verify controls (e.g. OLResultat.se) return None
        and are skipped.
        """
        while self.punch_source is not None:
            result = self.punch_source.verify_control_codes()
            if result is None or result.status:
                break
            self.logger.error("Control code verification failed: %s", result.message)
            if self.interactive_mode:
                location = self.punch_source.control_codes_config_location()
                self._config_dialog(True, assist_option_location=location)
                self.update_sources()
            else:
                raise ValueError(f"Control code verification failed: {result.message}")

    def update_sources(self):
        if self.punch_source_name not in PUNCH_SOURCES:
            self.logger.error(
                '"%s" is not a valid Punch Source, valid values are: %s.',
                self.punch_source_name,
                ", ".join(PUNCH_SOURCES),
            )
            raise ValueError(
                '"{}" is not a valid Punch Source, valid values are: {}.'.format(
                    self.punch_source_name, ", ".join(PUNCH_SOURCES)
                )
            )

        if self.punch_source is None:
            self.punch_source = PUNCH_SOURCES[self.punch_source_name]()
            self.punch_source.register_punch_listener(self)
            self.punch_source.register_health_listener(
                self._on_punch_source_health_changed
            )
        elif type(self.punch_source).name != self.punch_source_name:
            is_running = self.punch_source.is_running()
            self.punch_source.stop()
            del self.punch_source
            self.punch_source = PUNCH_SOURCES[self.punch_source_name]()
            self.punch_source.register_punch_listener(self)
            self.punch_source.register_health_listener(
                self._on_punch_source_health_changed
            )
            if is_running:
                self.punch_source.start()

        if self.start_list_source_name not in START_LIST_SOURCES:
            self.logger.error(
                '"%s" is not a valid Start List Source, valid values are: %s.',
                self.start_list_source_name,
                ", ".join(START_LIST_SOURCES),
            )
            raise ValueError(
                '"{}" is not a valid Start List Source, valid values are: {}.'.format(
                    self.start_list_source_name, ", ".join(START_LIST_SOURCES)
                )
            )

        if self.start_list_source is None:
            self.start_list_source = START_LIST_SOURCES[self.start_list_source_name]()
            self.start_list_source.register_health_listener(
                self._on_start_list_health_changed
            )
            self.start_list_source.register_data_listener(
                self._on_start_list_data_changed
            )
        elif type(self.start_list_source).name != self.start_list_source_name:
            is_running = self.start_list_source.is_running()
            self.start_list_source.stop()
            del self.start_list_source
            self.start_list_source = START_LIST_SOURCES[self.start_list_source_name]()
            self.start_list_source.register_health_listener(
                self._on_start_list_health_changed
            )
            self.start_list_source.register_data_listener(
                self._on_start_list_data_changed
            )
            if is_running:
                self.start_list_source.start()

    def _get_interactive_mode(self):
        config_section = Config().get_section(Config.SECTION_COMMON)
        self.interactive_mode = self.CONFIG_OPTION_INTERACTIVE_MODE.get_value(
            config_section
        )
        if self.interactive_mode is None:
            self.interactive_mode = True

    def _parse_config(self):
        config_section = self.config.get_section(Config.SECTION_COMMON)

        self.interactive_mode = self.CONFIG_OPTION_INTERACTIVE_MODE.get_value(
            config_section
        )
        self.announce_ip_on_startup = (
            self.CONFIG_OPTION_ANNOUNCE_IP_ON_STARTUP.get_value(config_section)
        )

        seconds = self.CONFIG_OPTION_INTRO_SOUND_TRIGGER_TIMEOUT_SECONDS.get_value(
            config_section
        )
        sound_file = self.CONFIG_OPTION_INTRO_SOUND_FILE.get_value(config_section)
        with self._last_sound_time_lock:
            self.intro_sound_trigger_timeout_seconds = timedelta(seconds=seconds)
            self.intro_sound_file = sound_file

        self.test_sound_file = self.CONFIG_OPTION_TEST_SOUND_FILE.get_value(
            config_section
        )

        self.add_pre_warnings_to_bottom = (
            self.CONFIG_OPTION_ADD_PRE_WARNINGS_TO_BOTTOM.get_value(config_section)
        )

        self._announce_last_leg = self.CONFIG_OPTION_ANNOUNCE_LAST_LEG.get_value(
            config_section
        )

        self._dedup_card_control_enabled = (
            self.CONFIG_OPTION_DEDUP_CARD_CONTROL.get_value(
                self.config.get_section(Config.SECTION_DEDUPLICATION)
            )
        )
        self._dedup_bib_leg_enabled = self.CONFIG_OPTION_DEDUP_BIB_LEG.get_value(
            self.config.get_section(Config.SECTION_DEDUPLICATION)
        )
        self._dedup_timeout = self.CONFIG_OPTION_DEDUP_TIMEOUT_SECONDS.get_value(
            self.config.get_section(Config.SECTION_DEDUPLICATION)
        )

        data_sources_section = self.config.get_section(Config.SECTION_DATA_SOURCES)
        self.punch_source_name = COMMON_PUNCH_SOURCE.get_value(data_sources_section)
        self.start_list_source_name = COMMON_START_LIST_SOURCE.get_value(
            data_sources_section
        )

    def start(self):
        if self.announce_ip_on_startup:
            self._notify_ip()
        self.punch_processor.start()
        self.announcement_processor.start()
        if self.punch_source is not None:
            self.punch_source.start()
        if self.start_list_source is not None:
            self.start_list_source.start()
        wx.CallLater(1000, self._refresh_health)

    def punch_received(self, punch: dict[str, str]):
        self.logger.debug("punch_received: %s", punch)
        self.punch_queue.put(punch)

    def _is_deduped(
        self,
        cache: dict[tuple[str, str], float],
        key: tuple[str, str],
        current_passed_time: float,
    ) -> bool:
        timestamp = cache.get(key)
        if timestamp is None:
            return False
        if self._dedup_timeout == 0:
            return True
        if current_passed_time - timestamp >= self._dedup_timeout:
            del cache[key]
            return False
        return True

    @staticmethod
    def _parse_passed_time(passed_time: datetime | None) -> float:
        if passed_time is None:
            return time()
        return passed_time.timestamp()

    def _process_punches(self):
        while True:
            punch = self.punch_queue.get()
            self._stats_punches_received += 1
            self._last_punch_time = datetime.now()  # noqa: DTZ005 - local elapsed-time comparison, no cross-timezone logic
            self.logger.debug(
                "Processing: %s from: %s",
                punch[PUNCH_KEY_CARD_NUMBER],
                punch[PUNCH_KEY_CONTROL_CODE],
            )

            punch_passed_time = self._parse_passed_time(punch[PUNCH_KEY_PASSED_TIME])

            if self._dedup_card_control_enabled:
                key = (
                    str(punch[PUNCH_KEY_CARD_NUMBER]),
                    str(punch[PUNCH_KEY_CONTROL_CODE]),
                )
                with self._dedup_lock:
                    if self._is_deduped(
                        self._dedup_card_control, key, punch_passed_time
                    ):
                        self.logger.debug("Skipping duplicate card+control: %s", key)
                        self._stats_dedup_skipped += 1
                        continue

            source = self.start_list_source
            source_name = self.start_list_source_name
            if source is None or source_name is None:
                self.logger.warning(
                    "Start list source not yet initialized, deferring punch."
                )
                continue

            has_all_fields = (
                PUNCH_KEY_BIB_NUMBER in punch
                and PUNCH_KEY_RELAY_LEG in punch
                and PUNCH_KEY_IS_LAST_LEG in punch
                and PUNCH_KEY_COUNTRY in punch
            )

            if has_all_fields:
                self._stats_punches_matched += 1
            elif PUNCH_KEY_BIB_NUMBER in punch:
                # Partial data - enrich via lookup
                self._stats_punches_matched += 1
                pre_warn_data = source.lookup_from_card_number(
                    punch[PUNCH_KEY_CARD_NUMBER]
                )
                if pre_warn_data is None:
                    self.logger.debug(
                        "Could not find the team connected to the card number."
                        " Using already existing data."
                    )
                else:
                    punch.update(pre_warn_data)
            else:
                # No bib - lookup is mandatory
                pre_warn_data = source.lookup_from_card_number(
                    punch[PUNCH_KEY_CARD_NUMBER]
                )
                if pre_warn_data is None:
                    self.logger.debug(
                        "Could not find the team connected to the card number. Skipping!"
                    )
                    continue
                else:
                    self._stats_punches_matched += 1
                    punch.update(pre_warn_data)

            if not self._announce_last_leg and punch.get(PUNCH_KEY_IS_LAST_LEG):
                self.logger.debug(
                    "Skipping last leg punch: bib=%s", punch.get(PUNCH_KEY_BIB_NUMBER)
                )
                continue

            passed_time = self._to_str(punch[PUNCH_KEY_PASSED_TIME]).rpartition(" ")[2]
            bib_number = self._to_str(punch[PUNCH_KEY_BIB_NUMBER])
            relay_leg = self._to_str(punch[PUNCH_KEY_RELAY_LEG])

            if self._dedup_bib_leg_enabled:
                key = (bib_number, relay_leg)
                with self._dedup_lock:
                    if self._is_deduped(self._dedup_bib_leg, key, punch_passed_time):
                        self.logger.debug("Skipping duplicate bib+leg: %s", key)
                        self._stats_dedup_skipped += 1
                        continue

            country = punch.get(PUNCH_KEY_COUNTRY)
            voice = self.sound.resolve_voice(country)
            self._stats_announcements += 1
            self.announcement_queue.put(
                {_ANNOUNCE_KEY_VOICE: voice, _ANNOUNCE_KEY_SOUND: bib_number}
            )
            wx.CallAfter(
                self._add_pre_warning_with_refresh, passed_time, bib_number, relay_leg
            )
            wx.CallAfter(self._update_control_window)

            if self._dedup_card_control_enabled:
                key = (punch[PUNCH_KEY_CARD_NUMBER], punch[PUNCH_KEY_CONTROL_CODE])
                with self._dedup_lock:
                    if key not in self._dedup_card_control:
                        self._dedup_card_control[key] = punch_passed_time

            if self._dedup_bib_leg_enabled:
                key = (bib_number, relay_leg)
                with self._dedup_lock:
                    if key not in self._dedup_bib_leg:
                        self._dedup_bib_leg[key] = punch_passed_time

    @staticmethod
    def _to_str(val: int | str | None) -> str:
        if val is None:
            return "-"
        return str(val)

    def _process_announcements(self):
        while True:
            self.logger.debug("process_announcements")
            sound = self.announcement_queue.get()
            with self._last_sound_time_lock:
                self.logger.debug("last_sound_time: %s", self.last_sound_time)
                assert self.intro_sound_trigger_timeout_seconds is not None
                assert self.intro_sound_file is not None
                if (
                    self.last_sound_time is None
                    or (datetime.now() - self.last_sound_time).total_seconds()  # noqa: DTZ005 - local elapsed-time comparison, no cross-timezone logic
                    >= self.intro_sound_trigger_timeout_seconds.total_seconds()
                ):
                    self.logger.debug("intro_sound_file: %s", self.intro_sound_file)
                    self.sound.play_sound(self.intro_sound_file)

                self.logger.debug("sound: %s", sound)
                if sound[_ANNOUNCE_KEY_SOUND] == "-":
                    self.sound.play_sound(self.intro_sound_file)
                else:
                    self.sound.play_voice_sound(
                        f"{sound[_ANNOUNCE_KEY_SOUND]}{AUDIO_EXTENSION}",
                        sound.get(_ANNOUNCE_KEY_VOICE),
                    )

                self.last_sound_time = datetime.now()  # noqa: DTZ005 - local elapsed-time comparison, no cross-timezone logic


def _init_language():
    """Read the language setting from the config file and activate i18n."""
    from configparser import ConfigParser

    config = ConfigParser()
    config.read(CONFIGURATION_FILE)
    lang = config.get(
        Config.SECTION_COMMON,
        PreWarning.CONFIG_OPTION_LANGUAGE.name,
        fallback=PreWarning.CONFIG_OPTION_LANGUAGE.default_value,
    )
    set_language(lang)


def main():
    _init_language()
    app = wx.App()
    frm = PreWarning()
    frm.Show()
    frm.start()
    app.MainLoop()


if __name__ == "__main__":
    main()
