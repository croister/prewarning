# -*- coding: utf-8 -*-

"""
PreWarning main file.
"""

__author__ = 'Christian Lindblom croister@croister.se'
__version__ = '2.1.0'

import logging
import logging.config
import os
import socket
from datetime import timedelta, datetime
from pathlib import Path
from queue import Queue
from threading import Thread, Lock
from time import strftime, time
from typing import List, Dict

from ruamel import yaml
from watchdog.events import LoggingEventHandler, FileSystemEvent
from watchdog.observers import Observer
import wx
import wx.grid
import wx.lib.stattext

from punchsources import PUNCH_SOURCES, COMMON_PUNCH_SOURCE
from punchsources._base import PunchListener
from startlistsources import START_LIST_SOURCES, COMMON_START_LIST_SOURCE
from startlistsources.start_list_source_ola_mysql import StartListSourceOlaMySql
from utils.config import Config
from utils.config_consumer import ConfigConsumer
from utils.config_definitions import ConfigOptionDefinition, ConfigSectionDefinition, ConfigVerifierDefinition, \
    ConfigSectionOptionDefinition
from utils.config_dialog import ConfigDialog
from utils.constants import CONFIGURATION_DIR, APPLICATION_DIR
from utils.help_dialog import HelpDialog
from utils.hotkey_bindings import HotKeyBindingDefinition, HotKeyDefinition, key_event_to_str
from utils.sound import Sound, SoundFolder, verify_sound

# Column index names
COL_NR_TIME = 0
COL_NR_TEAM = 1
COL_NR_LEG = 2

# The first row
ROW_ZERO = 0

# Name of the logging configuration file
LOGGING_CONFIGURATION_FILE_NAME = 'logging.yaml'

# Logging configuration file location
LOGGING_CONFIGURATION_FILE = CONFIGURATION_DIR / LOGGING_CONFIGURATION_FILE_NAME

LOGGING_CONFIGURATION_FILE_FILTER_VALUES = {
    "APPLICATION_DIR": APPLICATION_DIR,
}


def _filter_logging_configuration(config_dict: dict):
    for key, value in config_dict.items():
        if isinstance(value, dict):
            _filter_logging_configuration(value)
        elif isinstance(value, str):
            value = value.format(**LOGGING_CONFIGURATION_FILE_FILTER_VALUES)
            if key == 'filename':
                value = str(Path(value).resolve())
            config_dict[key] = value


def _update_logging_configuration():
    # noinspection PyBroadException
    src_path = APPLICATION_DIR / LOGGING_CONFIGURATION_FILE
    try:
        with open(src_path, 'r') as f:
            config = yaml.safe_load(f.read())
            _filter_logging_configuration(config)
            logging.config.dictConfig(config)
    except PermissionError as e:
        logging.error('PermissionError in accessing the logging configuration file: "%s" %s', src_path, e)
    except OSError as e:
        logging.error('OSError in accessing the logging configuration file: "%s" %s', src_path, e)
    except Exception as e:
        logging.error('Exception in accessing the logging configuration file: "%s" %s', src_path, e)
    except BaseException as e:
        logging.error('BaseException in accessing the logging configuration file: "%s" %s', src_path, e)
    except:
        logging.error('Unknown exception in accessing the logging configuration file: "%s"', src_path)


_update_logging_configuration()


# Name of the configuration file
CONFIGURATION_FILE_NAME = 'prewarning.ini'

# Configuration file location
CONFIGURATION_FILE = CONFIGURATION_DIR / CONFIGURATION_FILE_NAME


class PreWarningMeta(type(wx.Frame), type(ConfigConsumer)):
    pass


class PreWarning(wx.Frame, ConfigConsumer, PunchListener, LoggingEventHandler, metaclass=PreWarningMeta):
    """
    The PreWarning main class
    """

    CONFIG_OPTION_INTERACTIVE_MODE = ConfigOptionDefinition(
        name='InteractiveMode',
        display_name='Interactive Mode',
        value_type=bool,
        description='Enables or disables the interactive mode. '
                    'If this is enabled the default method of configuration is via the GUI and if errors are detected '
                    'in the configuration the Settings Dialog is opened. '
                    'If this is disabled the configuration file is expected to be used as the means of changing the '
                    'configuration and if errors are detected in the configuration errors are written to the log '
                    'and the program exits.',
        default_value=True,
    )

    CONFIG_OPTION_ANNOUNCE_IP_ON_STARTUP = ConfigOptionDefinition(
        name='AnnounceIpOnStartup',
        display_name='Announce IP on Startup',
        value_type=bool,
        description='Enables or disables the readout of the current IP address at startup.',
        default_value=False,
    )

    CONFIG_OPTION_ENABLE_INTRO_SOUND = ConfigOptionDefinition(
        name='EnableIntroSound',
        display_name='Enable Intro Sound',
        value_type=bool,
        description='Enable or disable the intro sound played before the first team number is read after a timeout.',
        default_value=True,
    )

    CONFIG_OPTION_INTRO_SOUND_TRIGGER_TIMEOUT_SECONDS = ConfigOptionDefinition(
        name='IntroSoundTriggerTimeoutSeconds',
        display_name='Intro Sound Timeout',
        value_type=int,
        description='The timeout in seconds after the last announcement before the intro sound is played again before'
                    ' the next announcement.',
        default_value=10,
        valid_values=list(range(0, 121)),
        enabled_by=CONFIG_OPTION_ENABLE_INTRO_SOUND,
    )

    CONFIG_OPTION_INTRO_SOUND_FILE = ConfigOptionDefinition(
        name='IntroSoundFile',
        display_name='Intro Sound',
        value_type=Path,
        description='The path to the sound file to use as the intro sound before announcements.',
        default_value=Path('ding.mp3'),
        valid_values_gen=SoundFolder().get_all_sounds,
        enabled_by=CONFIG_OPTION_ENABLE_INTRO_SOUND,
    )

    CONFIG_OPTION_ENABLE_INTRO_SOUND.enables.append(CONFIG_OPTION_INTRO_SOUND_TRIGGER_TIMEOUT_SECONDS)
    CONFIG_OPTION_ENABLE_INTRO_SOUND.enables.append(CONFIG_OPTION_INTRO_SOUND_FILE)

    CONFIG_OPTION_TEST_SOUND_FILE = ConfigOptionDefinition(
        name='TestSoundFile',
        display_name='Test Sound',
        value_type=Path,
        description='The path to the sound file to use as the test sound.',
        default_value=Path('en/Testing.mp3'),
        valid_values_gen=SoundFolder().get_all_sounds,
    )

    CONFIG_OPTION_ADD_PRE_WARNINGS_TO_BOTTOM = ConfigOptionDefinition(
        name='AddPreWarningsToBottom',
        display_name='Add Pre-Warnings to Bottom',
        value_type=bool,
        description='Set to True if new Pre-Warnings should be added to the bottom of the screen.',
        default_value=False,
    )

    COMMON_CONFIG_SECTION_DEFINITION = ConfigSectionDefinition(
        name=Config.SECTION_COMMON,
        display_name=Config.SECTION_COMMON,
        option_definitions=[
            CONFIG_OPTION_INTERACTIVE_MODE,
            CONFIG_OPTION_ANNOUNCE_IP_ON_STARTUP,
            CONFIG_OPTION_ENABLE_INTRO_SOUND,
            CONFIG_OPTION_INTRO_SOUND_TRIGGER_TIMEOUT_SECONDS,
            CONFIG_OPTION_INTRO_SOUND_FILE,
            CONFIG_OPTION_TEST_SOUND_FILE,
            CONFIG_OPTION_ADD_PRE_WARNINGS_TO_BOTTOM,
        ],
        sort_key_prefix=0,
    )

    COMMON_CONFIG_SECTION_INTRO_SOUND_VERIFIER = ConfigVerifierDefinition(
        function=verify_sound,
        parameters=[
            ConfigSectionOptionDefinition(
                section_name=Config.SECTION_COMMON,
                option_definition=CONFIG_OPTION_INTRO_SOUND_FILE,
            ),
        ],
        message='The selected sound could not be played.',
    )

    CONFIG_OPTION_INTRO_SOUND_FILE.set_verifier(COMMON_CONFIG_SECTION_INTRO_SOUND_VERIFIER)

    COMMON_CONFIG_SECTION_TEST_SOUND_VERIFIER = ConfigVerifierDefinition(
        function=verify_sound,
        parameters=[
            ConfigSectionOptionDefinition(
                section_name=Config.SECTION_COMMON,
                option_definition=CONFIG_OPTION_TEST_SOUND_FILE,
            ),
        ],
        message='The selected sound could not be played.',
    )

    CONFIG_OPTION_TEST_SOUND_FILE.set_verifier(COMMON_CONFIG_SECTION_TEST_SOUND_VERIFIER)

    Config.register_config_section_definition(COMMON_CONFIG_SECTION_DEFINITION)

    @classmethod
    def config_section_definition(cls) -> ConfigSectionDefinition:
        return cls.COMMON_CONFIG_SECTION_DEFINITION

    display_lock = Lock()

    def __init__(self):
        # ensure the parent's __init__ is called
        wx.Frame.__init__(self, None, wx.ID_ANY, "PreWarning " + __version__)
        ConfigConsumer.__init__(self)
        PunchListener.__init__(self)

        self.observer = None

        self.logger = logging.getLogger(self.__class__.__name__)

        # Config variables
        self.interactive_mode = None
        self.announce_ip_on_Startup = None
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
                name='Settings',
                hotkey=HotKeyDefinition(key_code=ord('S')).with_ctrl(),
                handler=self._config_dialog,
                description="Opens the Settings Dialog",
                bitmap_name=wx.ART_EXECUTABLE_FILE,
            ),
            HotKeyBindingDefinition(
                name='Help',
                hotkey=HotKeyDefinition(key_code=wx.WXK_F1),
                handler=self._help_dialog,
                description="Opens the Help Dialog",
                alternate_hotkeys=[
                    HotKeyDefinition(key_code=ord('H')).with_ctrl(),
                ],
                bitmap_name=wx.ART_HELP,
            ),
            HotKeyBindingDefinition(
                name='Full Screen',
                hotkey=HotKeyDefinition(key_code=wx.WXK_F11),
                handler=self._toggle_full_screen,
                description="Switches full screen on and off",
                bitmap_name=wx.ART_FIND,
            ),
            HotKeyBindingDefinition(
                name='Fake Punch',
                hotkey=HotKeyDefinition(key_code=wx.WXK_SPACE).with_ctrl(),
                handler=self._simulate_punch,
                description="Simulates a pre-warning",
                alternate_hotkeys=[
                    HotKeyDefinition(key_code=ord('P')).with_ctrl(),
                ],
                bitmap_name=wx.ART_GO_DOWN,
            ),
            HotKeyBindingDefinition(
                name='Refresh Display',
                hotkey=HotKeyDefinition(key_code=wx.WXK_F5),
                handler=self._refresh,
                description="Refreshes the display",
                alternate_hotkeys=[
                    HotKeyDefinition(key_code=ord('R')).with_ctrl(),
                ],
                bitmap_name=wx.ART_LIST_VIEW,
            ),
            HotKeyBindingDefinition(
                name='Clear Display',
                hotkey=HotKeyDefinition(key_code=ord('C')).with_ctrl(),
                handler=self._clear,
                description="Clears the display from pre-warning entries",
                bitmap_name=wx.ART_DELETE,
            ),
            HotKeyBindingDefinition(
                name='Play Testing Sound',
                hotkey=HotKeyDefinition(key_code=ord('T')).with_ctrl(),
                handler=self._play_test_sound,
                description="Plays a test sound",
                bitmap_name=wx.ART_QUESTION,
            ),
            HotKeyBindingDefinition(
                name='Announce IP Address',
                hotkey=HotKeyDefinition(key_code=ord('I')).with_ctrl(),
                handler=self._notify_ip,
                description="Reads the IP (v4) address aloud section for section",
                bitmap_name=wx.ART_INFORMATION,
            ),
            HotKeyBindingDefinition(
                name='Print Sizes (debug)',
                hotkey=HotKeyDefinition(key_code=ord('V')).with_ctrl(),
                handler=self._print_sizes,
                description="Prints out sizes of GUI components (for debug purpose)",
                hidden=True,
                bitmap_name=wx.ART_TIP,
            ),
            HotKeyBindingDefinition(
                name='Increase Font Size',
                hotkey=HotKeyDefinition(key_code=wx.WXK_NUMPAD_ADD).with_ctrl(),
                handler=self._increase_font_size,
                description="Increases the font size",
                alternate_hotkeys=[
                    HotKeyDefinition(key_code=ord('+')).with_ctrl(),
                ],
                bitmap_name=wx.ART_PLUS,
            ),
            HotKeyBindingDefinition(
                name='Decrease Font Size',
                hotkey=HotKeyDefinition(key_code=wx.WXK_NUMPAD_SUBTRACT).with_ctrl(),
                handler=self._decrease_font_size,
                description="Decreases the font size",
                alternate_hotkeys=[
                    HotKeyDefinition(key_code=ord('-')).with_ctrl(),
                ],
                bitmap_name=wx.ART_MINUS,
            ),
            HotKeyBindingDefinition(
                name='Restore Font Size',
                hotkey=HotKeyDefinition(key_code=wx.WXK_NUMPAD0).with_ctrl(),
                handler=self._restore_font_size,
                description="Restores the font size to default",
                alternate_hotkeys=[
                    HotKeyDefinition(key_code=ord('0')).with_ctrl(),
                ],
                bitmap_name=wx.ART_UNDO,
            ),
            HotKeyBindingDefinition(
                name='Exit',
                hotkey=HotKeyDefinition(key_code=ord('X')).with_ctrl(),
                handler=self.Close,
                description="Exits the application",
                alternate_hotkeys=[
                    HotKeyDefinition(key_code=ord('Q')).with_ctrl(),
                    HotKeyDefinition(key_code=ord('D')).with_ctrl(),
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
                raise ValueError('The configuration contains the following errors: {}.'
                                 .format(str(validation_errors)))
        self._parse_config()

        # Init the sound util
        self.sound = Sound()

        # Set up the queues used for punches and announcements
        self.punch_queue = Queue()
        self.announcement_queue = Queue()

        # Init the thread used to process punches from the punch queue
        self.punch_processor = Thread(target=self._process_punches,
                                      daemon=True,
                                      name='PunchProcessorThread')

        # Init the thread used to process announcements from the announcement queue
        self.announcement_processor = Thread(target=self._process_announcements,
                                             daemon=True,
                                             name='AnnouncementProcessorThread')
        self.last_sound_time = None

        self.update_sources()

        self.observer = Observer()
        self.observer.name = 'LoggingConfFileObserverThread'
        self.observer.start()
        self.observer.schedule(event_handler=self, path=LOGGING_CONFIGURATION_FILE.parent.as_posix())

        if not self.interactive_mode:
            self._toggle_full_screen()

    def __del__(self):
        self.stop()

    def stop(self):
        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
        Config().stop()
        if self.punch_source is not None:
            self.punch_source.stop()
        if self.start_list_source is not None:
            self.start_list_source.stop()

    @staticmethod
    def _get_portrait_screen() -> wx.Display or None:
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
        self.logger.debug('Screen size: %dx%d', current_mode.GetWidth(), current_mode.GetHeight())
        client_area = display.GetClientArea()
        self.logger.debug('Client Area size: %dx%d', client_area.width, client_area.height)

        width = 600
        height = 800

        width = min(width, client_area.width)
        height = min(height, client_area.height)

        self.logger.debug('Frame size: %dx%d', width, height)

        self.SetMinSize((width, height))
        self.SetSize((width, height))
        self.Center()

    def on_modified(self, event: FileSystemEvent):
        super().on_modified(event)

        src_path = event.src_path
        if Path(src_path).resolve() == LOGGING_CONFIGURATION_FILE:
            logging.debug('Updating logging configuration - before')
            _update_logging_configuration()
            logging.debug('Updating logging configuration - after')

    def _create_gui(self):
        self.SetIcon(wx.Icon((APPLICATION_DIR / 'favicon.ico').as_posix()))

        # Create the main panel
        self.main_panel = wx.Panel(parent=self, id=wx.ID_ANY, style=wx.WANTS_CHARS)
        self.main_panel.SetDoubleBuffered(True)
        self.main_panel.Bind(wx.EVT_CHAR_HOOK, self._on_key_press)

        self.main_panel_sizer = wx.BoxSizer(wx.VERTICAL)

        # The color for the header
        self.header_color = wx.LIGHT_GREY

        # Create the header panel
        self.header_panel = wx.Panel(parent=self.main_panel, id=wx.ID_ANY, style=wx.BORDER_SIMPLE)
        self.header_panel.SetBackgroundColour(self.header_color)

        self.header_panel_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Create the header label
        self.header_label = wx.StaticText(self.header_panel, label='Förvarning', style=wx.ALIGN_CENTER)
        self.header_label.SetBackgroundColour(self.header_color)

        self.header_panel_sizer.Add(self.header_label, proportion=1, flag=wx.EXPAND)

        # Create the clock/time label
        self.time_label = wx.lib.stattext.GenStaticText(self.header_panel, label='00:00:00')
        self.time_label.SetBackgroundColour(self.header_color)

        self.header_panel_sizer.Add(self.time_label, proportion=0, flag=wx.RIGHT, border=5)

        self.header_panel.SetSizer(self.header_panel_sizer)

        self.main_panel_sizer.Add(self.header_panel, proportion=0, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=2)

        # Create the pre-warning grid panel
        self.grid_panel = wx.Panel(parent=self.main_panel, id=wx.ID_ANY)

        self.grid_panel_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Create the pre-warning grid
        self.prewarning_grid = wx.grid.Grid(self.grid_panel)
        self.prewarning_grid.CreateGrid(0, 3)
        self.prewarning_grid.SetColLabelValue(COL_NR_TIME, 'Tid')
        self.prewarning_grid.SetColLabelValue(COL_NR_TEAM, 'Lag')
        self.prewarning_grid.SetColLabelValue(COL_NR_LEG, 'Sträcka')
        self.prewarning_grid.SetColLabelAlignment(wx.LEFT, wx.CENTER)
        self.prewarning_grid.EnableEditing(False)
        self.prewarning_grid.EnableVisibleFocus(False)
        self.prewarning_grid.SetCellHighlightPenWidth(0)
        self.prewarning_grid.SetCellHighlightROPenWidth(0)
        self.prewarning_grid.SetSelectionBackground(self.prewarning_grid.GetDefaultCellBackgroundColour())
        self.prewarning_grid.SetSelectionForeground(self.prewarning_grid.GetDefaultCellTextColour())
        self.prewarning_grid.SetSelectionMode(wx.grid.Grid.GridSelectNone)
        self.prewarning_grid.DisableKeyboardScrolling()
        self.prewarning_grid.HideRowLabels()

        # Add filler row to get the column widths correct before any pre-warning arrives.
        self._add_filler_row()

        self.grid_panel_sizer.Add(self.prewarning_grid, proportion=1, flag=wx.EXPAND)

        self.grid_panel.SetSizer(self.grid_panel_sizer)

        self.main_panel_sizer.Add(self.grid_panel, proportion=1, flag=wx.EXPAND | wx.ALL, border=2)

        self.main_panel.SetSizer(self.main_panel_sizer)

        self.Bind(wx.EVT_CONTEXT_MENU, self._on_context_menu)

        self._calculate_sizes()

    # noinspection PyUnusedLocal
    def _on_timer(self, evt: wx.TimerEvent):
        new_time = strftime('%H:%M:%S')
        self.time_label.SetLabel(new_time)

    def _on_context_menu(self, event: wx.ContextMenuEvent):
        position = self.ScreenToClient(event.GetPosition())

        image_size = wx.Size(16, 16)

        menu = wx.Menu()
        for hotkey_binding in self.hotkey_bindings:
            if hotkey_binding.hidden:
                continue
            menu_item = wx.MenuItem(id=hotkey_binding.window_id,
                                    text=hotkey_binding.name,
                                    helpString=hotkey_binding.description)
            if hotkey_binding.bitmap_name is not None:
                menu_item.SetBitmap(wx.ArtProvider.GetBitmap(hotkey_binding.bitmap_name,
                                                             client=wx.ART_MENU,
                                                             size=image_size))
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
            self.logger.error('_on_event_menu: Event window id not found.')
            raise ValueError('_on_event_menu: Event window id not found.')

        self.logger.debug('_on_event_menu: %s', item.name)

        item.handler()

    def _add_pre_warning(self, punch_time: str, team: str, leg: str):
        self.logger.debug('_add_pre_warning: display_lock=%s', self.display_lock.locked())
        with self.display_lock:
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

    def _add_filler_row(self):
        self.prewarning_grid.InsertRows()
        self.prewarning_grid.SetCellValue(ROW_ZERO, COL_NR_TIME, '00:00:00')
        self.prewarning_grid.SetCellValue(ROW_ZERO, COL_NR_TEAM, '00')
        self.prewarning_grid.SetCellValue(ROW_ZERO, COL_NR_LEG, '0')
        self.prewarning_grid.SetCellTextColour(ROW_ZERO, COL_NR_TIME,
                                               self.prewarning_grid.GetCellBackgroundColour(ROW_ZERO, COL_NR_TIME))
        self.prewarning_grid.SetCellTextColour(ROW_ZERO, COL_NR_TEAM,
                                               self.prewarning_grid.GetCellBackgroundColour(ROW_ZERO, COL_NR_TEAM))
        self.prewarning_grid.SetCellTextColour(ROW_ZERO, COL_NR_LEG,
                                               self.prewarning_grid.GetCellBackgroundColour(ROW_ZERO, COL_NR_LEG))

    def _has_filler_row(self):
        return self.prewarning_grid.GetNumberRows() == 1\
               and self.prewarning_grid.GetCellTextColour(ROW_ZERO, COL_NR_TIME)\
               == self.prewarning_grid.GetCellBackgroundColour(ROW_ZERO, COL_NR_TIME)

    def _remove_non_visible_rows(self):
        if not self._has_filler_row():
            self.logger.debug('_remove_non_visible_rows: display_lock=%s', self.display_lock.locked())
            with self.display_lock:
                self.logger.debug('_remove_non_visible_rows: LOCKED display_lock=%s', self.display_lock.locked())
                last_row = self.prewarning_grid.GetNumberRows() - 1
                while last_row >= 0 and not self.prewarning_grid.IsVisible(self.prewarning_grid.GetNumberRows() - 1,
                                                                           COL_NR_TIME,
                                                                           wholeCellVisible=True):
                    if self.add_pre_warnings_to_bottom:
                        self.logger.debug('DELETE 0')
                        self.prewarning_grid.DeleteRows(ROW_ZERO)
                    else:
                        self.logger.debug('DELETE LAST %d', last_row)
                        self.prewarning_grid.DeleteRows(last_row)
                    last_row = self.prewarning_grid.GetNumberRows() - 1
                self.logger.debug('_remove_non_visible_rows: DONE display_lock=%s', self.display_lock.locked())
            self.logger.debug('_remove_non_visible_rows: END display_lock=%s', self.display_lock.locked())

    def _clear(self):
        self.logger.debug('_clear: display_lock=%s', self.display_lock.locked())
        with self.display_lock:
            self.prewarning_grid.DeleteRows(ROW_ZERO, self.prewarning_grid.GetNumberRows())
            self._add_filler_row()
            self._calculate_sizes()

    def _refresh(self):
        orig_size = self.GetSize()
        new_size = wx.Size(width=orig_size.GetWidth() + 1, height=orig_size.GetHeight() + 1)
        self.SetSize(new_size)
        self.SetSize(orig_size)

        self.logger.debug('_refresh: display_lock=%s', self.display_lock.locked())
        with self.display_lock:
            self._calculate_sizes()

    def _calculate_sizes(self):
        usable_size = wx.Window.GetClientSize(self)
        self.logger.debug('calculate_sizes: %dx%d', usable_size.GetWidth(), usable_size.GetHeight())

        # font_factor = 28
        font_factor = 27
        if usable_size.GetWidth() <= usable_size.GetHeight():
            # font_factor = 15
            font_factor = 16
        self.logger.debug('Font factor: %d', font_factor)
        font_factor += self.font_factor_offset
        self.logger.debug('Font factor with offset: %d', font_factor)

        default_font_size = int(usable_size.GetWidth() / font_factor)
        self.logger.debug('Font size: %d', default_font_size)

        header_font = self.header_label.GetFont()
        header_font.SetPointSize(default_font_size)
        header_font = header_font.Bold()
        self.header_label.SetFont(header_font)

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
        (grid_width, grid_height) = self.grid_panel.GetSize()

        col_size_leg = self.prewarning_grid.GetColSize(COL_NR_LEG)
        new_col_size_leg = col_size_leg + int(col_size_leg / 3)
        self.prewarning_grid.SetColSize(COL_NR_LEG, new_col_size_leg)

        col_size_team = self.prewarning_grid.GetColSize(COL_NR_TEAM)
        new_col_size_team = col_size_team + int(col_size_team / 3)
        self.prewarning_grid.SetColSize(COL_NR_TEAM, new_col_size_team)

        col_size_time = (grid_width - new_col_size_leg - new_col_size_team)
        col_size_time = max(10, col_size_time)
        self.prewarning_grid.SetColSize(COL_NR_TIME, col_size_time)
        self.prewarning_grid.Thaw()

    def _print_sizes(self):
        self.logger.debug('PRINT SIZES')
        (header_panel_width, header_panel_height) = self.header_panel.GetSize()
        self.logger.info('header_panel.GetSize(): %dx%d', header_panel_width, header_panel_height)
        (grid_panel_width, grid__panel_height) = self.grid_panel.GetSize()
        self.logger.info('grid_panel.GetSize(): %dx%d', grid_panel_width, grid__panel_height)
        (grid_width, grid_height) = self.prewarning_grid.GetSize()
        self.logger.info('prewarning_grid.GetSize(): %dx%d', grid_width, grid_height)

    def _on_resize(self, event: wx.SizeEvent):
        self.logger.debug('EventSize: %dx%d', event.GetSize().GetWidth(), event.GetSize().GetHeight())
        self.logger.debug('_on_resize: display_lock=%s', self.display_lock.locked())
        with self.display_lock:
            self._calculate_sizes()

        event.Skip()

    def _on_resize_head(self, event: wx.SizeEvent):
        self.logger.debug('HEAD EventSize: %dx%d', event.GetSize().GetWidth(), event.GetSize().GetHeight())
        self.logger.debug('_on_resize_head: display_lock=%s', self.display_lock.locked())
        with self.display_lock:
            self._calculate_sizes()

        event.Skip()

    def _help_dialog(self):
        self.logger.debug('Help Dialog')
        help_dialog = HelpDialog(self, app_version=__version__, hotkey_bindings=self.hotkey_bindings)
        help_dialog.Show()

    def _config_dialog(self, perform_validation: bool = False):
        start = time()
        settings_dialog = ConfigDialog(self.config, self, title='Settings')
        created = time()
        self.logger.debug('Config Dialog created: %d seconds', created - start)
        settings_dialog.Center()

        settings_dialog.TransferDataToWindow()

        if perform_validation:
            settings_dialog.Validate()

        res = settings_dialog.ShowModal()
        if res == wx.ID_CANCEL and perform_validation:
            exit(1)
        settings_dialog.Destroy()

    def _toggle_full_screen(self):
        self.logger.debug('Toggle Full Screen')
        if self.IsFullScreen():
            self.ShowFullScreen(False, style=wx.FULLSCREEN_ALL)
        else:
            self.ShowFullScreen(True, style=wx.FULLSCREEN_ALL)

    def _simulate_punch(self):
        self.logger.debug('Simulate Punch')
        self.test_bib_number += 10
        self.test_leg_number += 1
        self._add_pre_warning(strftime('%H:%M:%S'), str(self.test_bib_number), str(self.test_leg_number))
        self.announcement_queue.put({'language': None, 'sound': str(self.test_bib_number)})

    def _play_test_sound(self):
        self.logger.debug('Play Test Sound')
        self.sound.play_sound(self.test_sound_file)

    def _notify_ip(self):
        self.logger.debug('Notify IP')
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 0))  # connecting to a UDP address doesn't send packets
        local_ip_address = s.getsockname()[0]
        self.logger.debug('local_ip_address: %s', local_ip_address)
        for number in local_ip_address.split("."):
            self.announcement_queue.put({'language': 'en', 'sound': number})
            pass
        s.close()

    def _close(self, event=None):
        self.logger.debug('Close')
        self.stop()
        self.Unbind(wx.EVT_CLOSE, handler=self._close)
        self.Close(True)

    def _increase_font_size(self):
        self.logger.debug('Increase Font Size')
        self.font_factor_offset -= 1
        self.logger.debug('_increase_font_size: display_lock=%s', self.display_lock.locked())
        with self.display_lock:
            self._calculate_sizes()
        wx.CallAfter(self._refresh)

    def _decrease_font_size(self):
        self.logger.debug('Decrease Font Size')
        self.font_factor_offset += 1
        self.logger.debug('_decrease_font_size: display_lock=%s', self.display_lock.locked())
        with self.display_lock:
            self._calculate_sizes()
        wx.CallAfter(self._refresh)

    def _restore_font_size(self):
        self.logger.debug('Restore Font Size')
        self.font_factor_offset = 0
        self.logger.debug('_restore_font_size: display_lock=%s', self.display_lock.locked())
        with self.display_lock:
            self._calculate_sizes()
        wx.CallAfter(self._refresh)

    def _on_key_press(self, key_event: wx.KeyEvent):
        self.logger.debug(f'_on_key_press: {key_event_to_str(key_event)} pushed!')

        for key_binding in self.hotkey_bindings:
            if key_binding.matches(key_event):
                key_binding.handler()
                break

        key_event.Skip()

    def config_updated(self, section_names: List[str]):
        self._parse_config()
        self.update_sources()

    def update_sources(self):
        if self.punch_source_name not in PUNCH_SOURCES:
            self.logger.error('"%s" is not a valid Punch Source, valid values are: %s.',
                              self.punch_source_name, ', '.join(PUNCH_SOURCES))
            raise ValueError('"{}" is not a valid Punch Source, valid values are: {}.'.format(
                self.punch_source_name, ', '.join(PUNCH_SOURCES)))

        if self.punch_source is None:
            self.punch_source = PUNCH_SOURCES[self.punch_source_name]()
            self.punch_source.register_punch_listener(self)
        elif type(self.punch_source).name != self.punch_source_name:
            is_running = self.punch_source.is_running()
            self.punch_source.stop()
            del self.punch_source
            self.punch_source = PUNCH_SOURCES[self.punch_source_name]()
            self.punch_source.register_punch_listener(self)
            if is_running:
                self.punch_source.start()

        if self.start_list_source_name not in START_LIST_SOURCES:
            self.logger.error('"%s" is not a valid Start List Source, valid values are: %s.',
                              self.start_list_source_name, ', '.join(START_LIST_SOURCES))
            raise ValueError('"{}" is not a valid Start List Source, valid values are: {}.'.format(
                self.start_list_source_name, ', '.join(START_LIST_SOURCES)))

        if self.start_list_source is None:
            self.start_list_source = START_LIST_SOURCES[self.start_list_source_name]()
        elif type(self.start_list_source).name != self.start_list_source_name:
            is_running = self.start_list_source.is_running()
            self.start_list_source.stop()
            del self.start_list_source
            self.start_list_source = START_LIST_SOURCES[self.start_list_source_name]()
            if is_running:
                self.start_list_source.start()

    def _get_interactive_mode(self):
        config_section = Config().get_section(Config.SECTION_COMMON)
        self.interactive_mode = self.CONFIG_OPTION_INTERACTIVE_MODE.get_value(config_section)
        if self.interactive_mode is None:
            self.interactive_mode = True

    def _parse_config(self):
        config_section = self.config.get_section(Config.SECTION_COMMON)

        self.interactive_mode = self.CONFIG_OPTION_INTERACTIVE_MODE.get_value(config_section)
        self.announce_ip_on_Startup = self.CONFIG_OPTION_ANNOUNCE_IP_ON_STARTUP.get_value(config_section)

        seconds = self.CONFIG_OPTION_INTRO_SOUND_TRIGGER_TIMEOUT_SECONDS.get_value(config_section)
        self.intro_sound_trigger_timeout_seconds = timedelta(seconds=seconds)

        self.intro_sound_file = self.CONFIG_OPTION_INTRO_SOUND_FILE.get_value(config_section)

        self.test_sound_file = self.CONFIG_OPTION_TEST_SOUND_FILE.get_value(config_section)

        self.add_pre_warnings_to_bottom = self.CONFIG_OPTION_ADD_PRE_WARNINGS_TO_BOTTOM.get_value(config_section)

        self.punch_source_name = COMMON_PUNCH_SOURCE.get_value(config_section)
        self.start_list_source_name = COMMON_START_LIST_SOURCE.get_value(config_section)

    def start(self):
        if self.announce_ip_on_Startup:
            self._notify_ip()
        self.punch_processor.start()
        self.announcement_processor.start()
        self.punch_source.start()
        self.start_list_source.start()

    def punch_received(self, punch: Dict[str, str]):
        self.logger.debug('punch_received: %s', punch)
        self.punch_queue.put(punch)

    def _process_punches(self):
        while True:
            punch = self.punch_queue.get()
            self.logger.debug('Processing: %s from: %s', punch['cardNumber'], punch['controlCode'])

            if 'bibNumber' in punch:
                if self.start_list_source_name != StartListSourceOlaMySql.__qualname__:
                    pre_warn_data = self.start_list_source.lookup_from_card_number(punch['cardNumber'])
                    if pre_warn_data is None:
                        self.logger.debug('Could not find the team connected to the card number.'
                                          ' Using already existing data.')
                    else:
                        punch.update(pre_warn_data)
            else:
                pre_warn_data = self.start_list_source.lookup_from_card_number(punch['cardNumber'])
                if pre_warn_data is None:
                    self.logger.debug('Could not find the team connected to the card number. Skipping!')
                    continue
                else:
                    punch.update(pre_warn_data)

            language = None
            passed_time = self._to_str(punch['passedTime']).rpartition(' ')[2]
            bib_number = self._to_str(punch['bibNumber'])
            relay_leg = self._to_str(punch['relayLeg'])
            self._add_pre_warning(passed_time, bib_number, relay_leg)
            self.announcement_queue.put({'language': language, 'sound': bib_number})

    @staticmethod
    def _to_str(val: int or str or None) -> str:
        if val is None:
            return '-'
        return str(val)

    def _process_announcements(self):
        while True:
            self.logger.debug('process_announcements')
            sound = self.announcement_queue.get()
            self.logger.debug('last_sound_time: %s', self.last_sound_time)
            if self.last_sound_time is None\
                    or (datetime.now()-self.last_sound_time).total_seconds()\
                    >= self.intro_sound_trigger_timeout_seconds.total_seconds():
                self.logger.debug('intro_sound_file: %s', self.intro_sound_file)
                self.sound.play_sound(self.intro_sound_file)

            self.logger.debug('sound: %s', sound)
            self.sound.play_lang('{}.mp3'.format(sound['sound']), sound['language'])

            self.last_sound_time = datetime.now()


if __name__ == '__main__':
    app = wx.App()
    frm = PreWarning()
    frm.Show()
    frm.start()
    app.MainLoop()
