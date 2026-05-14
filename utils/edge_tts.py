import asyncio
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import edge_tts
from edge_tts.typing import Voice

from utils.constants import AUDIO_EXTENSION

logger = logging.getLogger(__name__)


@dataclass
class VoiceFile:
    stem: str
    text: str


class EdgeTTSError(Exception):
    """Raised when an edge-tts operation fails."""


class _EdgeTTS:
    """Internal wrapper that manages a dedicated asyncio event loop in a
    background thread. All public methods are synchronous — they submit
    coroutines to the event loop via run_coroutine_threadsafe and block
    on the result."""

    def __init__(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()

    def list_voices(self) -> list[Voice]:
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._list_voices(),
                self._loop,
            )
            return future.result()
        except Exception:
            logger.exception("Failed to fetch voices from edge-tts")
            return []

    def generate(self, shortname: str, text: str, target: Path) -> None:
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._generate(shortname, text, target),
                self._loop,
            )
            future.result()
        except EdgeTTSError:
            raise
        except Exception:
            logger.exception("Failed to generate audio for '%s': '%s'", shortname, text)
            raise EdgeTTSError(
                f"Failed to generate audio for '{shortname}': '{text}'"
            ) from None

    def generate_range(
        self,
        shortname: str,
        numbers: range,
        texts: list[VoiceFile],
        target_dir: Path,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> None:
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._generate_files(
                    shortname,
                    numbers,
                    texts,
                    target_dir,
                    skip_existing=False,
                    progress_callback=progress_callback,
                ),
                self._loop,
            )
            future.result()
        except EdgeTTSError:
            raise
        except Exception:
            logger.exception("Failed to generate range for '%s'", shortname)
            raise EdgeTTSError(f"Failed to generate range for '{shortname}'") from None

    def generate_missing(
        self,
        shortname: str,
        numbers: range,
        texts: list[VoiceFile],
        target_dir: Path,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> None:
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._generate_files(
                    shortname,
                    numbers,
                    texts,
                    target_dir,
                    skip_existing=True,
                    progress_callback=progress_callback,
                ),
                self._loop,
            )
            future.result()
        except EdgeTTSError:
            raise
        except Exception:
            logger.exception("Failed to repair voice '%s'", shortname)
            raise EdgeTTSError(f"Failed to repair voice '{shortname}'") from None

    def run_coro(self, coro) -> None:
        """Run an arbitrary coroutine on the internal event loop.
        Returns the coroutine's return value."""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    async def _list_voices(self) -> list[Voice]:
        return await edge_tts.list_voices()

    async def _generate(self, shortname: str, text: str, target: Path) -> None:
        communicate = edge_tts.Communicate(text, shortname)
        await communicate.save(str(target))

    async def _generate_files(
        self,
        shortname: str,
        numbers: range,
        texts: list[VoiceFile],
        target_dir: Path,
        skip_existing: bool = False,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> None:
        target_dir.mkdir(parents=True, exist_ok=True)
        total = len(numbers) + len(texts)
        done = 0
        for n in numbers:
            file = target_dir / f"{n}{AUDIO_EXTENSION}"
            if not (skip_existing and file.exists()):
                await self._generate(shortname, str(n), file)
            done += 1
            if progress_callback:
                progress_callback(done, total)
        for vf in texts:
            file = target_dir / f"{vf.stem}{AUDIO_EXTENSION}"
            if not (skip_existing and file.exists()):
                await self._generate(shortname, vf.text, file)
            done += 1
            if progress_callback:
                progress_callback(done, total)


_engine = _EdgeTTS()


def list_voices() -> list[Voice]:
    return _engine.list_voices()


def generate(shortname: str, text: str, target: Path) -> None:
    _engine.generate(shortname, text, target)


def generate_range(
    shortname: str,
    numbers: range,
    texts: list[VoiceFile],
    target_dir: Path,
    progress_callback: Callable[[int, int], None] | None = None,
) -> None:
    _engine.generate_range(shortname, numbers, texts, target_dir, progress_callback)


def generate_missing(
    shortname: str,
    numbers: range,
    texts: list[VoiceFile],
    target_dir: Path,
    progress_callback: Callable[[int, int], None] | None = None,
) -> None:
    _engine.generate_missing(shortname, numbers, texts, target_dir, progress_callback)


def run_coro(coro):
    """Run an arbitrary coroutine on the shared event loop.
    Used by callers outside edge_tts (e.g. translation)."""
    return _engine.run_coro(coro)
