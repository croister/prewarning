# -*- coding: utf-8 -*-

import logging
import os
import subprocess
from threading import Lock

from natsort import natsorted
from subprocess import run
from typing import List
from watchdog.events import LoggingEventHandler, FileSystemEvent
from watchdog.observers import Observer

from utils.config import ConfigConsumer, ConfigSectionDefinition, ConfigOptionDefinition, Config
from utils.config_definitions import Path
from utils.singleton import Singleton


SOUNDS_DIR = 'sounds'


class SoundFolder(LoggingEventHandler, Singleton):
    """
    Util for managing the sound folder.
    """

    def __repr__(self) -> str:
        return f'SoundFolder(sounds_dir_location={self._sounds_dir_location})'

    def __str__(self) -> str:
        return repr(self)

    def __init__(self):
        super().__init__()

        self.logger = logging.getLogger(self.__class__.__name__)

        self._sounds_dir_location = None

        self._languages = None
        self._languages_mutex = Lock()

        self._all_sounds = None
        self._all_sounds_mutex = Lock()

        self.observer = Observer()
        self.observer.name = 'SoundsDirObserverThread'
        self.observer.start()
        self.observer.schedule(event_handler=self, path=self.get_sounds_dir().as_posix())

        self.logger.debug(self)

    def __del__(self):
        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join()

    def on_moved(self, event):
        super().on_moved(event)

        self._reset()

    def on_created(self, event):
        super().on_created(event)

        self._reset()

    def on_deleted(self, event):
        super().on_deleted(event)

        self._reset()

    def on_modified(self, event: FileSystemEvent):
        super().on_modified(event)

        self._reset()

    def _reset(self):
        self.logger.debug('Reset')

        self._languages_mutex.acquire()
        self._all_sounds_mutex.acquire()
        try:
            self._languages = None
            self._all_sounds = None
        finally:
            self._languages_mutex.release()
            self._all_sounds_mutex.release()

    def get_sounds_dir(self) -> Path:
        if self._sounds_dir_location is None:
            self._sounds_dir_location = Path(__file__).resolve().parent.parent.absolute() / SOUNDS_DIR
        return self._sounds_dir_location

    def get_languages(self) -> List[str]:
        self._languages_mutex.acquire()
        try:
            if self._languages is None:
                sounds_dir_location = self.get_sounds_dir()
                self._languages = []
                for child in sounds_dir_location.iterdir():
                    if child.is_dir():
                        self._languages.append(child.name)
                self._languages = natsorted(self._languages)
        finally:
            self._languages_mutex.release()

        return self._languages

    @staticmethod
    def _path_sort_key(path: Path) -> str:
        return path.as_posix()

    def get_all_sounds(self) -> List[Path]:

        def _get_all_sounds_rec(current_dir: Path) -> List[Path]:
            all_sounds = []
            files = []
            directories = []
            for child in current_dir.iterdir():
                if child.is_dir():
                    directories.append(child)
                else:
                    files.append(child.relative_to(sounds_dir_location))

            files = natsorted(files, key=SoundFolder._path_sort_key)
            all_sounds.extend(files)

            directories = natsorted(directories, key=SoundFolder._path_sort_key)
            for directory in directories:
                all_sounds.extend(_get_all_sounds_rec(current_dir / directory))

            return all_sounds

        self._all_sounds_mutex.acquire()
        try:
            if self._all_sounds is None:
                sounds_dir_location = self.get_sounds_dir()
                self._all_sounds = _get_all_sounds_rec(sounds_dir_location)
        finally:
            self._all_sounds_mutex.release()
        return self._all_sounds


LOGGER_NAME = 'Sound'


class _SoundMeta(type(ConfigConsumer), type(Singleton)):
    pass


class Sound(ConfigConsumer, Singleton, metaclass=_SoundMeta):
    """
    Util for playing sounds.
    """

    @classmethod
    def play(cls, sound: str, override: bool = False):
        Sound().play_sound(sound, override)

    @classmethod
    def play_lang(cls, sound: str, lang: str, override: bool = False):
        Sound().play_sound_lang(sound, lang, override)

    @classmethod
    def play_default_lang(cls, sound: str, override: bool = False):
        Sound().play_sound_default_lang(sound, override)

    """@classmethod
    def play_default_foreign_lang(cls, sound: str, override: bool = False):
        Sound().play_sound_default_foreign_lang(sound, override)"""

    def _run_cmd(self, cmd: List[str]) -> int:
        self.logger.debug('_run_cmd(%s)', cmd)
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        result = run(cmd, capture_output=True, text=True, startupinfo=si)
        self.logger.debug('_run_cmd(%s) -> %d', cmd, result.returncode)
        if result.stdout:
            self.logger.debug('_run_cmd(%s) stdout: %s', cmd, result.stdout)
        if result.stderr:
            self.logger.error('_run_cmd(%s) stderr: %s', cmd, result.stderr)
        result.check_returncode()
        return result.returncode

    def _get_player_command(self) -> str:
        try:
            self._run_cmd(['mpg123', '--version'])
            return 'mpg123'
        except FileNotFoundError:
            try:
                self._run_cmd(['../mpg123/win/mpg123', '--version'])
                return '../mpg123/win/mpg123'
            except FileNotFoundError:
                self.logger.error('Unable to locate the mpg123 binary, please install it and add it to the path.')
                raise FileNotFoundError('Unable to locate the mpg123 binary, please install it and add it to the path.')

    name = __qualname__

    CONFIG_OPTION_SOUND_ENABLED = ConfigOptionDefinition(
        name='SoundEnabled',
        display_name='Enable Sound',
        value_type=bool,
        description='Enables or disables the playback of sounds.',
        default_value=True,
    )

    CONFIG_OPTION_DEFAULT_LANGUAGE = ConfigOptionDefinition(
        name='DefaultLanguage',
        display_name='Default Language',
        value_type=str,
        description='Selects the default language to use for sounds.',
        valid_values_gen=SoundFolder().get_languages,
        default_value='sv',
        enabled_by=CONFIG_OPTION_SOUND_ENABLED,
    )

    """CONFIG_OPTION_FOREIGN_DEFAULT_LANGUAGE = ConfigOptionDefinition(
        name='DefaultForeignLanguage',
        display_name='Default Foreign Language',
        value_type=str,
        description='Selects the default language to use for foreign runners for sounds.',
        valid_values=get_languages(),
        default_value='en'
    )"""

    SOUND_CONFIG_SECTION_DEFINITION = ConfigSectionDefinition(
        name=name,
        display_name=name,
        option_definitions=[
            CONFIG_OPTION_SOUND_ENABLED,
            CONFIG_OPTION_DEFAULT_LANGUAGE,
            # CONFIG_OPTION_FOREIGN_DEFAULT_LANGUAGE,
        ],
        sort_key_prefix=10,
    )

    Config.register_config_section_definition(SOUND_CONFIG_SECTION_DEFINITION)

    @classmethod
    def config_section_definition(cls) -> ConfigSectionDefinition:
        return cls.SOUND_CONFIG_SECTION_DEFINITION

    def __repr__(self) -> str:
        return f'Sound(sound_enabled={self.sound_enabled},' \
               f' default_language={self.default_language})'

    def __str__(self) -> str:
        return repr(self)

    def __init__(self):
        super().__init__()

        if LOGGER_NAME != self.__class__.__name__:
            raise ValueError('LOGGER_NAME not correct: {} vs {}'.format(LOGGER_NAME, self.__class__.__name__))

        self.logger = logging.getLogger(self.__class__.__name__)

        self.sound_enabled = None
        self.default_language = None
        # self.default_foreign_language = None

        self.player_command = self._get_player_command()

        self.sound_folder = SoundFolder()

        self._parse_config()

        self.logger.debug(self)

    def config_updated(self, section_names: List[str]):
        self._parse_config()

    def _parse_config(self):
        config_section = Config().get_section(self.name)

        self.sound_enabled = self.CONFIG_OPTION_SOUND_ENABLED.get_value(config_section)

        self.default_language = self.CONFIG_OPTION_DEFAULT_LANGUAGE.get_value(config_section)

        # self.default_foreign_language = self.CONFIG_OPTION_FOREIGN_DEFAULT_LANGUAGE.get_value(config_section)

    def play_sound(self, sound: str, override: bool = False):
        self.logger.debug('Play requested: %s', sound)
        if self.sound_enabled or override:
            sound_file = self.sound_folder.get_sounds_dir() / sound
            if not os.path.exists(sound_file):
                self.logger.error('The requested sound does not exist: %s', sound_file)
                sound_file = self.sound_folder.get_sounds_dir() / 'ding.mp3'
            self._run_cmd([self.player_command, '-q', sound_file.as_posix()])
        else:
            self.logger.debug('Sound playback disabled, not playing.')

    def play_sound_lang(self, sound: str, lang: str, override: bool = False):
        self.logger.debug('Play lang requested: %s Lang: %s', sound, lang)
        if lang is None:
            lang = self.default_language
        lang_sound = Path(lang) / sound
        self.play_sound(lang_sound.as_posix(), override)

    def play_sound_default_lang(self, sound: str, override: bool = False):
        self.logger.debug('Play default lang requested: %s', sound)
        self.play_sound_lang(sound, self.default_language, override)

    """def play_sound_default_foreign_lang(self, sound: str):
        self.logger.debug('Play default foreign lang requested: %s', sound)
        self.play_sound_lang(sound, self.default_foreign_language)"""


def verify_sound(sound: str):
    try:
        Sound.play(sound, True)
        return True
    except Exception as e:
        logging.getLogger(LOGGER_NAME).debug('verify_sound: %s', e)
        return False
