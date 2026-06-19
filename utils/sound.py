# -*- coding: utf-8 -*-

import logging
import os
from threading import Event, Lock

import miniaudio
from natsort import natsorted
from typing import List

from watchdog.events import (
    LoggingEventHandler,
    DirMovedEvent,
    FileMovedEvent,
    DirCreatedEvent,
    FileCreatedEvent,
    DirDeletedEvent,
    FileDeletedEvent,
    DirModifiedEvent,
    FileModifiedEvent,
)
from watchdog.observers import Observer

from utils.config import (
    ConfigConsumer,
    ConfigSectionDefinition,
    ConfigOptionDefinition,
    Config,
)
from utils.config_definitions import Path, VerificationResult
from utils.constants import AUDIO_EXTENSION, DING_FILENAME
from utils.singleton import Singleton

SOUNDS_DIR = "sounds"


_VM_KEY_DEFAULT_COUNTRY = "defaultcountry"
_VM_KEY_DEFAULT_VOICE = "defaultvoice"
_VM_KEY_FALLBACK_VOICE = "fallbackvoice"
_VM_SECTION_NAME = "VoiceManager"


class SoundFolder(LoggingEventHandler, Singleton):
    """
    Util for managing the sound folder.
    """

    def __repr__(self) -> str:
        return f"SoundFolder(sounds_dir_location={self._sounds_dir_location})"

    def __str__(self) -> str:
        return repr(self)

    def __init__(self):
        super().__init__()

        self.logger = logging.getLogger(self.__class__.__name__)

        self._sounds_dir_location = None

        self._all_sounds = None

        self._lock = Lock()

        self.observer = Observer()
        self.observer.name = "SoundsDirObserverThread"
        self.observer.start()
        self.observer.schedule(
            event_handler=self, path=self.get_sounds_dir().as_posix()
        )

        self.logger.debug(self)

    def __del__(self):
        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join()

    def on_moved(self, event: DirMovedEvent | FileMovedEvent):
        super().on_moved(event)

        self._reset()

    def on_created(self, event: DirCreatedEvent | FileCreatedEvent):
        super().on_created(event)

        self._reset()

    def on_deleted(self, event: DirDeletedEvent | FileDeletedEvent):
        super().on_deleted(event)

        self._reset()

    def on_modified(self, event: DirModifiedEvent | FileModifiedEvent):
        super().on_modified(event)

        self._reset()

    def _reset(self):
        self.logger.debug("Reset")

        with self._lock:
            self._all_sounds = None

    def get_sounds_dir(self) -> Path:
        if self._sounds_dir_location is None:
            self._sounds_dir_location = (
                Path(__file__).resolve().parent.parent.absolute() / SOUNDS_DIR
            )
        return self._sounds_dir_location

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
                elif child.suffix.lower() == AUDIO_EXTENSION:
                    files.append(child.relative_to(sounds_dir_location))

            files = natsorted(files, key=SoundFolder._path_sort_key)
            all_sounds.extend(files)
            for f in files:
                bare = Path(f.name)
                if bare not in all_sounds:
                    all_sounds.append(bare)

            directories = natsorted(directories, key=SoundFolder._path_sort_key)
            for directory in directories:
                all_sounds.extend(_get_all_sounds_rec(current_dir / directory))

            return all_sounds

        with self._lock:
            if self._all_sounds is None:
                sounds_dir_location = self.get_sounds_dir()
                self._all_sounds = _get_all_sounds_rec(sounds_dir_location)
            return self._all_sounds


LOGGER_NAME = "Sound"


class _SoundMeta(type(ConfigConsumer), type(Singleton)):  # type: ignore[misc]
    pass


class Sound(ConfigConsumer, Singleton, metaclass=_SoundMeta):
    """
    Util for playing sounds.
    """

    @classmethod
    def play(cls, sound: str, override: bool = False):
        Sound().play_sound(sound, override)

    @classmethod
    def play_voice(cls, sound: str, voice: str | None, override: bool = False):
        Sound().play_voice_sound(sound, voice, override)

    @classmethod
    def play_file(cls, path: str | Path, override: bool = False):
        Sound().play_file_path(path, override)

    def _play_audio(self, file_path: str) -> None:
        """Play an audio file using miniaudio (blocking until finished)."""
        self.logger.debug("_play_audio(%s)", file_path)
        info = miniaudio.get_file_info(file_path)
        end_event = Event()
        stream = miniaudio.stream_with_callbacks(
            miniaudio.stream_file(
                file_path,
                output_format=info.sample_format,
                nchannels=info.nchannels,
                sample_rate=info.sample_rate,
                frames_to_read=4096,
            ),
            end_callback=lambda: end_event.set(),
        )
        next(stream)
        device = miniaudio.PlaybackDevice(
            output_format=info.sample_format,
            nchannels=info.nchannels,
            sample_rate=info.sample_rate,
            buffersize_msec=200,
        )
        device.start(stream)
        end_event.wait()
        device.close()

    name = __qualname__

    CONFIG_OPTION_SOUND_ENABLED = ConfigOptionDefinition(
        name="SoundEnabled",
        display_name="Enable Sound",
        value_type=bool,
        description="Enables or disables the playback of sounds.",
        default_value=True,
    )

    SOUND_CONFIG_SECTION_DEFINITION = ConfigSectionDefinition(
        name=name,
        display_name=name,
        option_definitions=[
            CONFIG_OPTION_SOUND_ENABLED,
        ],
        sort_key_prefix=10,
    )

    Config.register_config_section_definition(SOUND_CONFIG_SECTION_DEFINITION)

    @classmethod
    def config_section_definition(cls) -> ConfigSectionDefinition:
        return cls.SOUND_CONFIG_SECTION_DEFINITION

    def __repr__(self) -> str:
        return f"Sound(sound_enabled={self.sound_enabled})"

    def __str__(self) -> str:
        return repr(self)

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        super().__init__()

        if LOGGER_NAME != self.__class__.__name__:
            raise ValueError(
                "LOGGER_NAME not correct: {} vs {}".format(
                    LOGGER_NAME, self.__class__.__name__
                )
            )

        self.logger = logging.getLogger(self.__class__.__name__)

        self._sound_lock = Lock()

        self.sound_enabled = None

        self.sound_folder = SoundFolder()

        self._parse_config()

        self.logger.debug(self)

        self._initialized = True

    def config_updated(self, section_names: List[str]):
        self._parse_config()

    def _parse_config(self):
        with self._sound_lock:
            config_section = Config().get_section(self.name)

            self.sound_enabled = self.CONFIG_OPTION_SOUND_ENABLED.get_value(
                config_section
            )

            voice_section = Config().get_section(_VM_SECTION_NAME)
            self.default_country = voice_section.get(_VM_KEY_DEFAULT_COUNTRY, "SWE")
            self.default_voice = voice_section.get(_VM_KEY_DEFAULT_VOICE, "")
            self.fallback_voice = voice_section.get(_VM_KEY_FALLBACK_VOICE, "")

    def play_sound(self, sound: str, override: bool = False):
        self.logger.debug("Play requested: %s", sound)
        with self._sound_lock:
            if self.sound_enabled or override:
                sound_file = self.sound_folder.get_sounds_dir() / sound
                if not os.path.exists(sound_file):
                    self.logger.error(
                        "The requested sound does not exist: %s", sound_file
                    )
                    sound_file = self.sound_folder.get_sounds_dir() / DING_FILENAME
                self._play_audio(str(sound_file))
            else:
                self.logger.debug("Sound playback disabled, not playing.")

    def play_voice_sound(self, sound: str, voice: str | None, override: bool = False):
        self.logger.debug("Play voice requested: %s Voice: %s", sound, voice)
        if voice is None:
            voice = self.default_voice or None
        if voice is None:
            self.play_sound(sound, override)
        else:
            voice_sound = Path(voice) / sound
            self.play_sound(voice_sound.as_posix(), override)

    def play_file_path(self, path: str | Path, override: bool = False):
        self.logger.debug("Play file requested: %s", path)
        with self._sound_lock:
            if self.sound_enabled or override:
                sound_file = Path(path)
                if not os.path.exists(sound_file):
                    self.logger.error(
                        "The requested file does not exist: %s", sound_file
                    )
                    sound_file = self.sound_folder.get_sounds_dir() / DING_FILENAME
                self._play_audio(str(sound_file))
            else:
                self.logger.debug("Sound playback disabled, not playing.")

    def resolve_voice(self, runner_country: str | None) -> str | None:
        if not runner_country:
            return self.default_voice or None
        elif runner_country.upper() == self.default_country.upper():
            return self.default_voice or None
        return self.fallback_voice or None


def resolve_sound_for_voice(sound: str, voice: str | None) -> str:
    """Resolve a bare filename for voice playback.

    For bare filenames (no directory component), checks root sounds/ first.
    Falls back to {voice}/{sound} if available.
    For paths with a directory component, returns as-is.
    """
    sound_path = Path(sound)
    if sound_path.parent == Path("."):
        folder = SoundFolder()
        if (folder.get_sounds_dir() / sound).is_file():
            return sound
    if voice:
        return (Path(voice) / sound).as_posix()
    return sound


def verify_sound(sound: str):
    voice = None
    try:
        from utils.config import Config

        section = Config().get_section(_VM_SECTION_NAME)
        voice = section.get(_VM_KEY_DEFAULT_VOICE, None)
    except Exception:
        pass
    resolved = resolve_sound_for_voice(sound, voice)
    folder = SoundFolder()
    if not (folder.get_sounds_dir() / resolved).is_file():
        return VerificationResult(
            message=f'The sound file "{resolved}" does not exist.', status=False
        )
    try:
        Sound.play(resolved, True)
        return True
    except Exception as e:
        logging.getLogger(LOGGER_NAME).debug("verify_sound: %s", e)
        return False


def get_all_sounds():
    """Lazy wrapper that creates SoundFolder on first call, not at import time."""
    return SoundFolder().get_all_sounds()
