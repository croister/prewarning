import json
import logging
import shutil
import threading
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Final

import pycountry
import wx
import wx.lib.scrolledpanel
from edge_tts.typing import Voice
from gpytranslate import Translator as GpyTranslator

from utils.config import Config, ConfigOptionDefinition, ConfigSectionDefinition
from utils.config_definitions import (
    ConfigSectionOptionDefinition,
    ConfigSelectorDefinition,
    ConfigVerifierDefinition,
    SelectionData,
    SelectionResult,
    SelectionType,
    VerificationResult,
)
from utils.constants import AUDIO_EXTENSION, TESTING_FILENAME
from utils.country_dict_by_ioc import COUNTRIES
from utils.edge_tts import (
    EdgeTTSError,
    VoiceFile,
    generate,
    generate_missing,
    generate_range,
    list_voices,
    run_coro,
)
from utils.i18n import N_, _
from utils.sound import Sound
from validators.validation_error import ValidationError

logger = logging.getLogger(__name__)

# Edge-tts Voice dict keys
_VOICE_KEY_SHORT_NAME: Final = "ShortName"
_VOICE_KEY_GENDER: Final = "Gender"
_VOICE_KEY_LOCALE: Final = "Locale"

# Country dict key
_COUNTRY_KEY_NAME = "name"

_REFRESH_ICON = (
    Path(__file__).resolve().parent.parent
    / "resources"
    / "icons"
    / "View-refresh.svg.png"
)
_AUDIO_CARD_ICON = (
    Path(__file__).resolve().parent.parent
    / "resources"
    / "icons"
    / "Audio-card.svg.png"
)

STATUS_COMPLETE = "✓"
STATUS_INCOMPLETE = "⚠"
STAR_FILLED = "★"
STAR_EMPTY = "☆"

COLOR_PLAY_GREEN = wx.Colour(0, 160, 0)
COLOR_PLAY_GRAY = wx.Colour(140, 140, 140)
COLOR_NOTE_TEXT = wx.Colour(140, 140, 140)
COLOR_DIM_LABEL = wx.Colour(100, 100, 100)
COLOR_INCOMPLETE_ROW = wx.Colour(255, 220, 100)
COLOR_RANGE_ERROR = wx.Colour(255, 200, 200)

PLAY_COL_WIDTH = 28
SHORTNAME_COL_WIDTH = 220
LANG_COL_WIDTH = 120
GENDER_COL_WIDTH = 70
STATUS_COL_WIDTH = 52
STAR_COL_WIDTH = 56

# Column header labels
_COL_HEADER_SHORT_NAME = N_("Short Name")
_COL_HEADER_LANGUAGE = N_("Language")
_COL_HEADER_GENDER = N_("Gender")
_COL_HEADER_STATUS = N_("Status")
_COL_HEADER_DEFAULT = N_("Default")
_COL_HEADER_FALLBACK = N_("Fallback")

VOICE_METADATA_FILENAME = "voice.json"


def parse_extra_ranges(value: str | None) -> list[tuple[int, int]]:
    if not value:
        return []
    ranges: list[tuple[int, int]] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" not in part:
            continue
        try:
            start_str, end_str = part.split("-", 1)
            start = int(start_str.strip())
            end = int(end_str.strip())
            if start < 0 or end < 0 or start > end:
                continue
            ranges.append((start, end))
        except ValueError, TypeError:
            continue
    return ranges


DEFAULT_RANGE_START = 0
DEFAULT_RANGE_END = 999
DEFAULT_EXTRA_RANGE = "1000-9999"

DLG_DEFAULT_COUNTRY_CAPTION = N_("Select Default Country")
DLG_DEFAULT_COUNTRY_MESSAGE = N_("Select a country:")
MSG_SELECT_COUNTRY = N_("Select a country code.")
ERR_COUNTRY_VERIFY = N_("The selected country code is not a valid IOC code.")
ERR_DEFAULT_VOICE_VERIFY = N_("The default voice is not installed.")
ERR_FALLBACK_VOICE_VERIFY = N_("The fallback voice is not installed.")
ERR_EXTRA_RANGES_VERIFY = N_("The extra ranges format is invalid.")
ERR_EXTRA_RANGES_FORMAT = N_(
    "Invalid extra ranges format. Expected comma-separated ranges like '1000-1999, 2000-2999'."
)
ERR_EXTRA_RANGES_OVERLAP = N_(
    "Extra ranges must not overlap with the default range ({start}-{end})."
)
ERR_EXTRA_RANGES_REVERSED = N_("Start of a range must not be greater than its end.")


def _get_extra_ranges_error(value: str) -> str | None:
    """Returns an error message if invalid, None if valid."""
    if not value:
        return None
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" not in part:
            return _(ERR_EXTRA_RANGES_FORMAT)
        try:
            start_str, end_str = part.split("-", 1)
            start = int(start_str.strip())
            end = int(end_str.strip())
            if start < 0 or end < 0:
                return _(ERR_EXTRA_RANGES_FORMAT)
            if start > end:
                return _(ERR_EXTRA_RANGES_REVERSED)
            if start <= DEFAULT_RANGE_END:
                return _(ERR_EXTRA_RANGES_OVERLAP).format(
                    start=DEFAULT_RANGE_START, end=DEFAULT_RANGE_END
                )
        except ValueError, TypeError:
            return _(ERR_EXTRA_RANGES_FORMAT)
    return None


def _is_valid_extra_ranges_format(value: str) -> bool:
    return _get_extra_ranges_error(value) is None


def validate_extra_ranges(value: str) -> bool | ValidationError:
    error = _get_extra_ranges_error(value)
    if error is not None:
        return ValidationError(validate_extra_ranges, error, [("value", value)])
    return True


def _verify_extra_ranges(value: str) -> bool | VerificationResult:
    error = _get_extra_ranges_error(value)
    if error is not None:
        return VerificationResult(message=error, status=False)
    return True


def _verify_default_country(country_code: str) -> bool:
    return bool(country_code) and country_code.upper() in COUNTRIES


def _verify_voice(shortname: str) -> bool:
    if not shortname:
        return False
    voice_dir = SOUNDS_DIR / shortname
    return voice_dir.is_dir() and (voice_dir / VOICE_METADATA_FILENAME).is_file()


def _select_default_country() -> SelectionResult:
    result = SelectionResult(
        caption=_(DLG_DEFAULT_COUNTRY_CAPTION),
        message=_(DLG_DEFAULT_COUNTRY_MESSAGE),
        selection_type=SelectionType.SINGLE,
    )
    for ioc_code, data in sorted(
        COUNTRIES.items(), key=lambda x: x[1][_COUNTRY_KEY_NAME]
    ):
        result.add_value(
            SelectionData(ioc_code, f"{data[_COUNTRY_KEY_NAME]} ({ioc_code})")
        )
    return result


_cancel_event = threading.Event()


class _InstallCancelled(EdgeTTSError):
    """Raised when an install/repair job is cancelled by the user."""


def _remove_voice_dir(voice_dir: Path) -> None:
    for attempt in range(5):
        try:
            shutil.rmtree(voice_dir)
            return
        except PermissionError:
            if attempt < 4:
                threading.Event().wait(0.2)
            else:
                raise


def _drain_queue(q: Queue) -> None:
    while not q.empty():
        try:
            q.get_nowait()
        except Empty:
            break


SOUNDS_DIR = Path(__file__).resolve().parent.parent / "sounds"

SAMPLE_NUMBERS = (7, 104, 999)  # demo samples played when clicking "Play"
TESTING_TEXT = "Testing, one two three"

TOOLTIP_PLAY_SAMPLE = N_("Play sample")
TOOLTIP_DEFAULT = ""
TOOLTIP_REFRESH_EDGE_TTS = N_("Refresh from edge-tts")

FILTER_ALL = N_("All")
_GENDER_ALL = "All"
_GENDER_MALE = "Male"
_GENDER_FEMALE = "Female"
GENDER_CHOICES = (
    (_GENDER_ALL, N_("All")),
    (_GENDER_MALE, N_("Male")),
    (_GENDER_FEMALE, N_("Female")),
)
NO_TOOLTIP_KEY = (-1, -1)
TOOLTIP_IS_DEFAULT = N_("Current default voice")
TOOLTIP_SET_DEFAULT = N_("Set as Default")
TOOLTIP_IS_FALLBACK = N_("Current fallback voice")
TOOLTIP_SET_FALLBACK = N_("Set as Fallback")

UI_SECTION_BORDER = 8
UI_SMALL_BORDER = 4
PLAY_ICON_SIZE = 16
MIN_ICON_SIZE = 16
ICON_SIZE_PADDING = 8

# Discovered list columns
COL_DISC_PLAY = 0
COL_DISC_SHORTNAME = 1
COL_DISC_LANGUAGE = 2
COL_DISC_GENDER = 3

# Installed list columns
COL_INST_PLAY = 0
COL_INST_SHORTNAME = 1
COL_INST_LANGUAGE = 2
COL_INST_GENDER = 3
COL_INST_STATUS = 4
COL_INST_DEFAULT = 5
COL_INST_FALLBACK = 6

VOICEMANAGER_SECTION_NAME = "VoiceManager"


def _is_valid_voice_dirname(dirname: str) -> bool:
    parts = dirname.split("-")
    return len(parts) >= 2 and len(parts[0]) == 2


def get_installed_voice_shortnames() -> list[str]:
    """Return installed voice shortnames for use as valid_values_gen."""
    shortnames: list[str] = []
    if not SOUNDS_DIR.is_dir():
        return shortnames
    for d in sorted(SOUNDS_DIR.iterdir()):
        if not d.is_dir():
            continue
        if not _is_valid_voice_dirname(d.name):
            continue
        if not (d / VOICE_METADATA_FILENAME).is_file():
            continue
        shortnames.append(d.name)
    return shortnames


CONFIG_OPTION_DEFAULT_COUNTRY = ConfigOptionDefinition(
    name="defaultcountry",
    display_name=N_("Default Country"),
    value_type=str,
    description=N_("IOC 3-letter code for the home nation."),
    default_value="SWE",
    valid_values=list(COUNTRIES.keys()),
)

CONFIG_OPTION_DEFAULT_VOICE = ConfigOptionDefinition(
    name="defaultvoice",
    display_name=N_("Default Voice"),
    value_type=str,
    description=N_("ShortName of the voice for home-country runners."),
    mandatory=True,
    valid_values_gen=get_installed_voice_shortnames,
)

CONFIG_OPTION_FALLBACK_VOICE = ConfigOptionDefinition(
    name="fallbackvoice",
    display_name=N_("Fallback Voice"),
    value_type=str,
    description=N_("ShortName of the voice for foreign runners."),
    mandatory=True,
    valid_values_gen=get_installed_voice_shortnames,
)

CONFIG_OPTION_EXTRA_RANGES = ConfigOptionDefinition(
    name="extraranges",
    display_name=N_("Extra Ranges"),
    value_type=str,
    description=N_(
        "Comma-separated list of extra number ranges (e.g. {default_extra_range})."
    ),
    description_format_args={"default_extra_range": DEFAULT_EXTRA_RANGE},
    default_value="",
    validator=validate_extra_ranges,
)

VOICEMANAGER_SECTION = ConfigSectionDefinition(
    name=VOICEMANAGER_SECTION_NAME,
    display_name=N_("Voice Manager"),
    option_definitions=[
        CONFIG_OPTION_DEFAULT_COUNTRY,
        CONFIG_OPTION_DEFAULT_VOICE,
        CONFIG_OPTION_FALLBACK_VOICE,
        CONFIG_OPTION_EXTRA_RANGES,
    ],
    sort_key_prefix=11,
)

Config.register_config_section_definition(VOICEMANAGER_SECTION)

VOICE_MANAGER_DEFAULT_COUNTRY_VERIFIER = ConfigVerifierDefinition(
    function=_verify_default_country,
    parameters=[
        ConfigSectionOptionDefinition(
            section_name=VOICEMANAGER_SECTION_NAME,
            option_definition=CONFIG_OPTION_DEFAULT_COUNTRY,
        ),
    ],
    message=ERR_COUNTRY_VERIFY,
)
CONFIG_OPTION_DEFAULT_COUNTRY.set_verifier(VOICE_MANAGER_DEFAULT_COUNTRY_VERIFIER)

VOICE_MANAGER_DEFAULT_COUNTRY_SELECTOR = ConfigSelectorDefinition(
    function=_select_default_country,
    parameters=[],
    message=MSG_SELECT_COUNTRY,
)
CONFIG_OPTION_DEFAULT_COUNTRY.set_selector(VOICE_MANAGER_DEFAULT_COUNTRY_SELECTOR)

VOICE_MANAGER_DEFAULT_VOICE_VERIFIER = ConfigVerifierDefinition(
    function=_verify_voice,
    parameters=[
        ConfigSectionOptionDefinition(
            section_name=VOICEMANAGER_SECTION_NAME,
            option_definition=CONFIG_OPTION_DEFAULT_VOICE,
        ),
    ],
    message=ERR_DEFAULT_VOICE_VERIFY,
)
CONFIG_OPTION_DEFAULT_VOICE.set_verifier(VOICE_MANAGER_DEFAULT_VOICE_VERIFIER)

VOICE_MANAGER_FALLBACK_VOICE_VERIFIER = ConfigVerifierDefinition(
    function=_verify_voice,
    parameters=[
        ConfigSectionOptionDefinition(
            section_name=VOICEMANAGER_SECTION_NAME,
            option_definition=CONFIG_OPTION_FALLBACK_VOICE,
        ),
    ],
    message=ERR_FALLBACK_VOICE_VERIFY,
)
CONFIG_OPTION_FALLBACK_VOICE.set_verifier(VOICE_MANAGER_FALLBACK_VOICE_VERIFIER)

VOICE_MANAGER_EXTRA_RANGES_VERIFIER = ConfigVerifierDefinition(
    function=_verify_extra_ranges,
    parameters=[
        ConfigSectionOptionDefinition(
            section_name=VOICEMANAGER_SECTION_NAME,
            option_definition=CONFIG_OPTION_EXTRA_RANGES,
        ),
    ],
    message=ERR_EXTRA_RANGES_VERIFY,
)
CONFIG_OPTION_EXTRA_RANGES.set_verifier(VOICE_MANAGER_EXTRA_RANGES_VERIFIER)


@dataclass
class InstalledVoice:
    shortname: str
    lang: str
    gender: str
    complete: bool


def _locale_to_language_name(locale: str) -> str:
    lang_code = locale.split("-")[0].lower() if locale else ""
    if lang_code:
        try:
            lang = pycountry.languages.get(alpha_2=lang_code)
            if lang is not None and hasattr(lang, "name"):
                return lang.name
        except LookupError:
            pass
    return locale


def _lang_from_shortname(shortname: str) -> str | None:
    lang = shortname.split("-")[0]
    return lang if len(lang) == 2 else None


def _is_voice_complete(voice_dir: Path, extra_ranges: list[tuple[int, int]]) -> bool:
    if not voice_dir.is_dir():
        return False
    try:
        files = {f.name for f in voice_dir.iterdir()}
    except OSError:
        return False
    checks = [(DEFAULT_RANGE_START, DEFAULT_RANGE_END)]
    checks.extend(extra_ranges)
    for start, end in checks:
        for n in range(start, end + 1):
            if f"{n}{AUDIO_EXTENSION}" not in files:
                return False
    return TESTING_FILENAME in files


def _voice_status_detail(voice_dir: Path, extra_ranges: list[tuple[int, int]]) -> str:
    if not voice_dir.is_dir():
        return _("Voice directory not found")
    try:
        files = {f.name for f in voice_dir.iterdir()}
    except OSError:
        return _("Could not read voice directory")
    missing: list[str] = []
    expected = 0
    checks = [(DEFAULT_RANGE_START, DEFAULT_RANGE_END)]
    checks.extend(extra_ranges)
    for start, end in checks:
        for n in range(start, end + 1):
            expected += 1
            fn = f"{n}{AUDIO_EXTENSION}"
            if fn not in files:
                missing.append(fn)
    expected += 1
    if TESTING_FILENAME not in files:
        missing.append(TESTING_FILENAME)
    present = expected - len(missing)
    if not missing:
        return _("Complete: {present} files present").format(present=present)
    if len(missing) <= 5:
        return _(
            "Incomplete: {present}/{expected} files present, missing {missing_files}"
        ).format(
            present=present,
            expected=expected,
            missing_files=", ".join(missing),
        )
    return _(
        "Incomplete: {present}/{expected} files present, missing {missing_count} files"
        " (e.g. {examples}...)"
    ).format(
        present=present,
        expected=expected,
        missing_count=len(missing),
        examples=", ".join(missing[:3]),
    )


def _list_installed_voices(
    edge_voices: list[Voice] | None = None,
) -> list[InstalledVoice]:
    gender_lookup: dict[str, str] = {}
    if edge_voices:
        for v in edge_voices:
            gender_lookup[v[_VOICE_KEY_SHORT_NAME]] = v.get(_VOICE_KEY_GENDER, "")
    metadata = _load_metadata()
    result: list[InstalledVoice] = []
    if not SOUNDS_DIR.is_dir():
        return result
    config_section = Config().get_section(VOICEMANAGER_SECTION_NAME)
    extra_ranges = parse_extra_ranges(
        config_section.get(CONFIG_OPTION_EXTRA_RANGES.name, "")
    )
    for d in sorted(SOUNDS_DIR.iterdir()):
        if not d.is_dir():
            continue
        if not _is_valid_voice_dirname(d.name):
            continue
        shortname = d.name
        meta = metadata.get(shortname, {})
        locale = meta.get(_VOICE_KEY_LOCALE, "")
        lang = (
            _locale_to_language_name(locale)
            if locale
            else _lang_from_shortname(shortname) or ""
        )
        gender = meta.get(_VOICE_KEY_GENDER, gender_lookup.get(shortname, _("Unknown")))
        complete = _is_voice_complete(d, extra_ranges)
        result.append(
            InstalledVoice(
                shortname=shortname,
                lang=lang or "",
                gender=gender,
                complete=complete,
            )
        )
    return result


def _load_metadata() -> dict[str, Any]:
    """Load metadata from per-voice voice.json files."""
    result: dict[str, Any] = {}
    if not SOUNDS_DIR.is_dir():
        return result
    for d in SOUNDS_DIR.iterdir():
        if not d.is_dir():
            continue
        vf = d / VOICE_METADATA_FILENAME
        if vf.is_file():
            try:
                data = json.loads(vf.read_text("utf-8"))
                shortname = data.get(_VOICE_KEY_SHORT_NAME, d.name)
                result[shortname] = data
            except json.JSONDecodeError, OSError:
                logger.exception("Failed to load voice metadata for %s", d.name)
    return result


def _save_metadata_entry(voice_data: Voice):
    shortname = voice_data.get(_VOICE_KEY_SHORT_NAME, "")
    target_dir = SOUNDS_DIR / shortname
    target_dir.mkdir(parents=True, exist_ok=True)
    vf = target_dir / VOICE_METADATA_FILENAME
    vf.write_text(json.dumps(voice_data, indent=2), "utf-8")


def _toggle_default_voice(shortname: str):
    config = Config()
    section = config.get_section(VOICEMANAGER_SECTION_NAME)
    if section.get(CONFIG_OPTION_DEFAULT_VOICE.name, "") != shortname:
        section[CONFIG_OPTION_DEFAULT_VOICE.name] = shortname
        config.write()


def _toggle_fallback_voice(shortname: str):
    config = Config()
    section = config.get_section(VOICEMANAGER_SECTION_NAME)
    if section.get(CONFIG_OPTION_FALLBACK_VOICE.name, "") != shortname:
        section[CONFIG_OPTION_FALLBACK_VOICE.name] = shortname
        config.write()


def _is_default_voice(shortname: str) -> bool:
    section = Config().get_section(VOICEMANAGER_SECTION_NAME)
    return section.get(CONFIG_OPTION_DEFAULT_VOICE.name, "") == shortname


def _is_fallback_voice(shortname: str) -> bool:
    section = Config().get_section(VOICEMANAGER_SECTION_NAME)
    return section.get(CONFIG_OPTION_FALLBACK_VOICE.name, "") == shortname


def _install_voice(
    voice_data: Voice,
    ranges: list[tuple[int, int]],
    progress_callback=None,
):
    shortname = voice_data[_VOICE_KEY_SHORT_NAME]
    target_dir = SOUNDS_DIR / shortname
    _save_metadata_entry(voice_data)
    testing_text = _translate_testing_text(shortname)
    texts = [VoiceFile("Testing", testing_text)]
    for i, (start, end) in enumerate(ranges):
        generate_range(
            shortname,
            range(start, end + 1),
            texts if i == 0 else [],
            target_dir,
            progress_callback,
        )


def _repair_voice(
    shortname: str,
    ranges: list[tuple[int, int]],
    progress_callback=None,
    voice_data: Voice | None = None,
):
    target_dir = SOUNDS_DIR / shortname
    if not target_dir.is_dir():
        logger.warning("Voice '%s' is not installed, skipping repair.", shortname)
        return
    testing_text = _translate_testing_text(shortname)
    texts = [VoiceFile("Testing", testing_text)]
    for i, (start, end) in enumerate(ranges):
        generate_missing(
            shortname,
            range(start, end + 1),
            texts if i == 0 else [],
            target_dir,
            progress_callback,
        )
    if voice_data:
        _save_metadata_entry(voice_data)
    else:
        meta = _load_metadata().get(shortname, {})
        _save_metadata_entry(meta)


def _translate_testing_text(shortname: str) -> str:
    lang = shortname.split("-")[0].lower()
    if lang == "en":
        return TESTING_TEXT
    try:
        translator = GpyTranslator()
        result = run_coro(translator.translate(TESTING_TEXT, targetlang=lang))
        try:
            return result.text
        except AttributeError:
            return str(result)
    except Exception:  # noqa: BLE001 - broad catch intentional; libraries raise diverse exceptions
        logger.warning("Translation failed for '%s', using English fallback.", lang)
        return TESTING_TEXT


def _do_play_sample_async(shortname: str, tmp: Path) -> None:
    text = _translate_testing_text(shortname)
    generate(shortname, text, tmp)


def _process_job(
    job: _InstallJob,
    update_progress_cb: Callable[[int, str], None],
    action: str,
):
    def progress(done: int, total: int):
        if _cancel_event.is_set():
            raise _InstallCancelled
        pct = int(done / total * 100) if total else 0
        wx.CallAfter(
            update_progress_cb,
            pct,
            f"{action} {job.shortname}... ({done}/{total})",
        )

    if job.repair:
        _repair_voice(job.shortname, job.ranges, progress, job.voice_data)
    else:
        _install_voice(job.voice_data, job.ranges, progress)


class _InstallJob:
    def __init__(
        self,
        shortname: str,
        ranges: list[tuple[int, int]],
        voice_data: Voice,
        repair: bool = False,
    ):
        self.shortname = shortname
        self.ranges = ranges
        self.voice_data = voice_data
        self.repair = repair


class _DiscoveredVoiceList(wx.ListCtrl):
    def __init__(self, parent, dialog, **kwargs):
        super().__init__(parent, **kwargs)
        self._dialog = dialog
        self._green_play_idx = -1
        self._gray_play_idx = -1
        self._header_icon_idx = -1
        self._init_play_images()

    def _init_play_images(self):
        size = PLAY_ICON_SIZE
        bg = wx.SystemSettings.GetColour(wx.SYS_COLOUR_LISTBOX)

        def _make_bmp(color):
            bmp = wx.Bitmap(size, size)
            dc = wx.MemoryDC()
            dc.SelectObject(bmp)
            dc.SetBackground(wx.Brush(bg))
            dc.Clear()
            dc.SetBrush(wx.Brush(color))
            dc.SetPen(wx.Pen(color))
            m = size // 5
            dc.DrawPolygon(
                [wx.Point(m, m), wx.Point(m, size - m), wx.Point(size - m, size // 2)]
            )
            dc.SelectObject(wx.NullBitmap)
            return bmp

        image_list = wx.ImageList(size, size)
        self._green_play_idx = image_list.Add(_make_bmp(COLOR_PLAY_GREEN))
        self._gray_play_idx = image_list.Add(_make_bmp(COLOR_PLAY_GRAY))
        if _AUDIO_CARD_ICON.is_file():
            audio_img = wx.Image(str(_AUDIO_CARD_ICON))
            audio_img.Rescale(size, size, wx.IMAGE_QUALITY_HIGH)
            self._header_icon_idx = image_list.Add(wx.Bitmap(audio_img))
        self.AssignImageList(image_list, wx.IMAGE_LIST_SMALL)

    def OnGetItemText(self, row, col):
        return self._dialog._on_get_discovered_text(row, col)

    def OnGetItemImage(self, row):
        if self._dialog._play_in_progress:
            return self._gray_play_idx
        return self._green_play_idx


class VoiceManagerDialog(wx.Dialog):
    def __init__(
        self,
        parent: wx.Window | None = None,
        bib_range: tuple[int, int] | None = None,
    ):
        super().__init__(parent, title=_("Voice Manager"), size=wx.Size(800, 850))
        icon = wx.Icon()
        icon.CopyFromBitmap(
            wx.ArtProvider.GetBitmap(
                wx.ART_CDROM,
                client=wx.ART_FRAME_ICON,
                size=wx.Size(PLAY_ICON_SIZE, PLAY_ICON_SIZE),
            )
        )
        self.SetIcon(icon)

        self._bib_range = bib_range

        self.discovered_voices: list[Voice] = []
        self.filtered_voices: list[Voice] = []
        self.installed_voices: list[InstalledVoice] = []

        self._vm_section = Config().get_section(VOICEMANAGER_SECTION_NAME)
        self.install_queue: Queue[_InstallJob] = Queue()
        self.queue_active = False
        self._current_job_shortname: str | None = None
        self._removed_shortnames: set[str] = set()
        self._play_in_progress = False
        self._showing_play_tooltip = False
        self._range_start_ctrls: list[wx.TextCtrl] = []
        self._range_end_ctrls: list[wx.TextCtrl] = []
        self._installed_tooltip_key = NO_TOOLTIP_KEY
        self._lang_combo_updating = False

        self._build_ui()
        self._load_data()

        self.Bind(wx.EVT_CLOSE, self._on_close)

    # -- UI building -----------------------------------------------

    def _build_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        self._bib_range_sizer = self._build_bib_range_section()
        if self._bib_range_sizer is not None:
            main_sizer.Add(
                self._bib_range_sizer,
                flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP,
                border=UI_SECTION_BORDER,
            )

        main_sizer.Add(
            self._build_ranges_section(),
            flag=wx.EXPAND | wx.ALL,
            border=UI_SECTION_BORDER,
        )
        main_sizer.Add(
            self._build_filter_bar(),
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            border=UI_SECTION_BORDER,
        )
        main_sizer.Add(
            self._build_discovered_section(),
            proportion=1,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            border=UI_SECTION_BORDER,
        )
        main_sizer.Add(
            self._build_installed_section(),
            proportion=1,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            border=UI_SECTION_BORDER,
        )
        main_sizer.Add(
            self._build_progress_section(),
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            border=UI_SECTION_BORDER,
        )
        main_sizer.Add(
            self._build_close_button(),
            flag=wx.ALIGN_RIGHT | wx.ALL,
            border=UI_SECTION_BORDER,
        )

        self.SetSizer(main_sizer)

    def _build_ranges_section(self):
        box = wx.StaticBoxSizer(wx.VERTICAL, self, _("Number Ranges to Generate"))
        self.range_panel = wx.lib.scrolledpanel.ScrolledPanel(
            box.GetStaticBox(), style=wx.TAB_TRAVERSAL
        )
        self.range_panel.SetMinSize(wx.Size(-1, 80))
        self.range_panel.SetMaxSize(wx.Size(-1, 200))
        self.range_sizer = wx.BoxSizer(wx.VERTICAL)
        self.range_panel.SetSizer(self.range_sizer)
        box.Add(self.range_panel, flag=wx.EXPAND)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        add_btn = wx.Button(box.GetStaticBox(), label=_("Add Range"))
        add_btn.Bind(wx.EVT_BUTTON, self._on_add_range)
        btn_sizer.Add(add_btn)
        box.Add(btn_sizer, flag=wx.TOP, border=UI_SMALL_BORDER)

        self._rebuild_range_rows()
        return box

    def _rebuild_range_rows(self):
        self.range_sizer.Clear(True)
        self._range_start_ctrls.clear()
        self._range_end_ctrls.clear()
        section = self._vm_section

        fixed_row = wx.BoxSizer(wx.HORIZONTAL)
        fixed_label = wx.StaticText(
            self.range_panel,
            label=f"{DEFAULT_RANGE_START} - {DEFAULT_RANGE_END}",
        )
        fixed_label.SetForegroundColour(COLOR_DIM_LABEL)
        fixed_row.Add(fixed_label)
        fixed_note = wx.StaticText(
            self.range_panel, label="  " + _("(always generated)")
        )
        fixed_note.SetForegroundColour(COLOR_NOTE_TEXT)
        fixed_row.Add(fixed_note)
        self.range_sizer.Add(fixed_row, flag=wx.BOTTOM, border=6)

        extra = parse_extra_ranges(section.get(CONFIG_OPTION_EXTRA_RANGES.name, ""))
        for i, (start, end) in enumerate(extra):
            row = wx.BoxSizer(wx.HORIZONTAL)
            start_txt = wx.TextCtrl(
                self.range_panel,
                value=str(start),
                size=wx.Size(60, -1),
                style=wx.TE_PROCESS_ENTER,
            )
            start_txt.Bind(wx.EVT_KILL_FOCUS, self._on_range_value_changed)
            start_txt.Bind(wx.EVT_TEXT_ENTER, self._on_range_enter)
            start_txt.Bind(wx.EVT_TEXT, self._on_range_text)
            self._range_start_ctrls.append(start_txt)
            dash = wx.StaticText(self.range_panel, label="  -  ")
            row.Add(start_txt)
            row.Add(dash, flag=wx.ALIGN_CENTER_VERTICAL)
            end_txt = wx.TextCtrl(
                self.range_panel,
                value=str(end),
                size=wx.Size(60, -1),
                style=wx.TE_PROCESS_ENTER,
            )
            end_txt.Bind(wx.EVT_KILL_FOCUS, self._on_range_value_changed)
            end_txt.Bind(wx.EVT_TEXT_ENTER, self._on_range_enter)
            end_txt.Bind(wx.EVT_TEXT, self._on_range_text)
            self._range_end_ctrls.append(end_txt)
            row.Add(end_txt)
            remove_btn = wx.Button(
                self.range_panel, label=_("Remove"), size=wx.Size(70, -1)
            )
            remove_btn.Bind(wx.EVT_BUTTON, partial(self._on_remove_range, i))
            row.Add(remove_btn, flag=wx.LEFT, border=UI_SECTION_BORDER)
            self.range_sizer.Add(row, flag=wx.BOTTOM, border=UI_SMALL_BORDER)

        self.range_panel.Layout()
        self.range_panel.SetupScrolling(scroll_x=False)
        self._validate_all_range_rows()
        self._update_bib_range_status()

    def _is_bib_range_covered(self) -> bool:
        """Check if the bib range is fully covered by the configured ranges."""
        if self._bib_range is None:
            return True
        bib_min, bib_max = self._bib_range
        ranges = [(DEFAULT_RANGE_START, DEFAULT_RANGE_END)]
        extra = parse_extra_ranges(
            self._vm_section.get(CONFIG_OPTION_EXTRA_RANGES.name, "")
        )
        ranges.extend(extra)
        for r_start, r_end in ranges:
            if r_start <= bib_min and r_end >= bib_max:
                return True
        # Check if combined ranges cover the full bib range
        covered = set()
        for r_start, r_end in ranges:
            for n in range(max(r_start, bib_min), min(r_end, bib_max) + 1):
                covered.add(n)
        return len(covered) >= (bib_max - bib_min + 1)

    def _build_bib_range_section(self) -> wx.BoxSizer | None:
        """Build the bib range info section shown above the ranges section."""
        if self._bib_range is None:
            return None

        bib_min, bib_max = self._bib_range

        sizer = wx.BoxSizer(wx.HORIZONTAL)

        label_text = _("Start list bibs: {min} - {max}").format(
            min=bib_min, max=bib_max
        )
        label = wx.StaticText(self, label=label_text)
        sizer.Add(label, flag=wx.ALIGN_CENTER_VERTICAL)

        self._bib_status_label = wx.StaticText(self, label="")
        sizer.Add(
            self._bib_status_label,
            flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
            border=UI_SECTION_BORDER,
        )

        self._bib_add_range_btn = wx.Button(self, label=_("Add Range"))
        self._bib_add_range_btn.Bind(wx.EVT_BUTTON, self._on_add_bib_range)
        sizer.Add(
            self._bib_add_range_btn,
            flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
            border=UI_SECTION_BORDER,
        )

        self._update_bib_range_status()
        return sizer

    def _update_bib_range_status(self) -> None:
        """Update the bib range coverage status label, tooltip, and button state."""
        if self._bib_range is None:
            return

        bib_min, bib_max = self._bib_range
        ranges = [(DEFAULT_RANGE_START, DEFAULT_RANGE_END)]
        extra = parse_extra_ranges(
            self._vm_section.get(CONFIG_OPTION_EXTRA_RANGES.name, "")
        )
        ranges.extend(extra)

        # Determine which parts of the bib range are covered and uncovered
        covered_parts: list[str] = []
        uncovered_numbers: set[int] = set(range(bib_min, bib_max + 1))

        for r_start, r_end in ranges:
            overlap_start = max(r_start, bib_min)
            overlap_end = min(r_end, bib_max)
            if overlap_start <= overlap_end:
                covered_parts.append(f"{overlap_start} - {overlap_end}")
                uncovered_numbers -= set(range(overlap_start, overlap_end + 1))

        fully_covered = len(uncovered_numbers) == 0

        # Build tooltip
        if fully_covered:
            tooltip = _("Covered by:") + "\n"
            for part in covered_parts:
                tooltip += f"  {part}\n"
        else:
            # Collapse uncovered numbers into ranges for display
            uncovered_ranges = self._numbers_to_ranges(sorted(uncovered_numbers))
            tooltip = _("Not covered:") + "\n"
            for r_start, r_end in uncovered_ranges:
                if r_start == r_end:
                    tooltip += f"  {r_start}\n"
                else:
                    tooltip += f"  {r_start} - {r_end}\n"
            if covered_parts:
                tooltip += _("Covered by:") + "\n"
                for part in covered_parts:
                    tooltip += f"  {part}\n"

        if fully_covered:
            self._bib_status_label.SetLabel(STATUS_COMPLETE + " " + _("Covered"))
            self._bib_status_label.SetForegroundColour(wx.Colour(0, 128, 0))
            self._bib_add_range_btn.Disable()
        else:
            self._bib_status_label.SetLabel(
                STATUS_INCOMPLETE + " " + _("Not fully covered")
            )
            self._bib_status_label.SetForegroundColour(wx.Colour(200, 120, 0))
            self._bib_add_range_btn.Enable()

        self._bib_status_label.SetToolTip(tooltip.strip())
        self._bib_status_label.Refresh()
        self._bib_status_label.GetParent().Layout()

    @staticmethod
    def _numbers_to_ranges(numbers: list[int]) -> list[tuple[int, int]]:
        """Collapse a sorted list of numbers into consecutive ranges."""
        if not numbers:
            return []
        ranges: list[tuple[int, int]] = []
        start = numbers[0]
        end = numbers[0]
        for n in numbers[1:]:
            if n == end + 1:
                end = n
            else:
                ranges.append((start, end))
                start = n
                end = n
        ranges.append((start, end))
        return ranges

    def _on_add_bib_range(self, event) -> None:
        """Add extra ranges that cover only the bib numbers not yet covered."""
        if self._bib_range is None:
            return

        bib_min, bib_max = self._bib_range

        # Find uncovered numbers
        ranges = [(DEFAULT_RANGE_START, DEFAULT_RANGE_END)]
        extra = parse_extra_ranges(
            self._vm_section.get(CONFIG_OPTION_EXTRA_RANGES.name, "")
        )
        ranges.extend(extra)

        uncovered_numbers: set[int] = set(range(bib_min, bib_max + 1))
        for r_start, r_end in ranges:
            uncovered_numbers -= set(range(r_start, r_end + 1))

        if not uncovered_numbers:
            return

        # Collapse uncovered numbers into ranges
        uncovered_ranges = self._numbers_to_ranges(sorted(uncovered_numbers))

        # Add each uncovered range as a new extra range
        current = self._vm_section.get(CONFIG_OPTION_EXTRA_RANGES.name, "")
        new_parts = [f"{s}-{e}" for s, e in uncovered_ranges]
        if current:
            current = current.rstrip(",") + "," + ",".join(new_parts)
        else:
            current = ",".join(new_parts)
        # Re-parse and sort all extra ranges
        all_extra = parse_extra_ranges(current)
        all_extra.sort()
        self._vm_section[CONFIG_OPTION_EXTRA_RANGES.name] = ", ".join(
            f"{s}-{e}" for s, e in all_extra
        )
        Config().write()
        self._rebuild_range_rows()
        self.Layout()
        wx.CallLater(200, self._refresh_installed_list)

    def _on_add_range(self, event):
        current = self._vm_section.get(CONFIG_OPTION_EXTRA_RANGES.name, "")
        new_part = DEFAULT_EXTRA_RANGE
        if current:
            current = current.rstrip(",") + f",{new_part}"
        else:
            current = new_part
        self._vm_section[CONFIG_OPTION_EXTRA_RANGES.name] = current
        Config().write()
        self._rebuild_range_rows()
        self.Layout()
        wx.CallLater(200, self._refresh_installed_list)

    def _on_range_value_changed(self, event):
        self._validate_all_range_rows()
        event.Skip()
        self._save_range_values()
        self._update_bib_range_status()
        wx.CallLater(200, self._refresh_installed_list)

    def _on_range_enter(self, event):
        self._validate_all_range_rows()
        self._save_range_values()
        self._update_bib_range_status()
        wx.CallLater(200, self._refresh_installed_list)

    def _on_range_text(self, event):
        ctrl = event.GetEventObject()
        bg = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW)
        ctrl.SetBackgroundColour(bg)
        ctrl.SetToolTip(TOOLTIP_DEFAULT)
        ctrl.Refresh()

    def _validate_all_range_rows(self) -> tuple[bool, bool]:
        bg_ok = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW)
        bg_bad = COLOR_RANGE_ERROR

        parsed_indices: set[int] = set()
        parsed: list[tuple[int, int, int]] = []
        all_valid = True
        for i, (start_txt, end_txt) in enumerate(
            zip(self._range_start_ctrls, self._range_end_ctrls, strict=False)
        ):
            try:
                sv = start_txt.GetValue().strip()
                ev = end_txt.GetValue().strip()
                s = int(sv)
                e = int(ev)
                if s < 0 or s > e:
                    raise ValueError(
                        _("start")
                        + f" ({s}) "
                        + _("must be >= 0 and less than or equal to end")
                        + f" ({e})"
                    )
                parsed.append((s, e, i))
                parsed_indices.add(i)
            except ValueError as exc:
                all_valid = False
                msg = str(exc)
                for ctrl in (start_txt, end_txt):
                    ctrl.SetBackgroundColour(bg_bad)
                    ctrl.SetToolTip(msg)
                    ctrl.Refresh()

        has_conflicts = False
        if all_valid:
            all_ranges = sorted([(0, 999, -1)] + parsed, key=lambda x: x[0])
            conflicts: dict[int, list[str]] = {}
            for i in range(len(all_ranges)):
                s, e, idx = all_ranges[i]
                for j in range(i + 1, len(all_ranges)):
                    ns, ne, nidx = all_ranges[j]
                    if e >= ns:
                        label = (
                            f"{s}-{e}" if idx == -1 else _("extra range") + f" {s}-{e}"
                        )
                        nlabel = (
                            f"{ns}-{ne}"
                            if nidx == -1
                            else _("extra range") + f" {ns}-{ne}"
                        )
                        conflicts.setdefault(idx, []).append(
                            _("overlaps with") + f" {nlabel}"
                        )
                        conflicts.setdefault(nidx, []).append(
                            _("overlaps with") + f" {label}"
                        )

            has_conflicts = bool(conflicts)
            for (s, e, idx), (start_txt, end_txt) in zip(
                parsed,
                zip(self._range_start_ctrls, self._range_end_ctrls, strict=False),
            ):
                msg_list = conflicts.get(idx)
                if msg_list:
                    msg = "; ".join(msg_list)
                    start_txt.SetBackgroundColour(bg_bad)
                    start_txt.SetToolTip(msg)
                    start_txt.Refresh()
                    end_txt.SetBackgroundColour(bg_bad)
                    end_txt.SetToolTip(msg)
                    end_txt.Refresh()
                else:
                    start_txt.SetBackgroundColour(bg_ok)
                    start_txt.SetToolTip(TOOLTIP_DEFAULT)
                    start_txt.Refresh()
                    end_txt.SetBackgroundColour(bg_ok)
                    end_txt.SetToolTip(TOOLTIP_DEFAULT)
                    end_txt.Refresh()

        return all_valid, has_conflicts

    def _save_range_values(self):
        parts = []
        for start_txt, end_txt in zip(
            self._range_start_ctrls, self._range_end_ctrls, strict=False
        ):
            try:
                s = int(start_txt.GetValue())
                e = int(end_txt.GetValue())
                if 0 <= s <= e:
                    parts.append(f"{s}-{e}")
            except ValueError:
                pass
        self._vm_section[CONFIG_OPTION_EXTRA_RANGES.name] = ", ".join(parts)
        Config().write()

    def _on_remove_range(self, index, event):
        extra = parse_extra_ranges(
            self._vm_section.get(CONFIG_OPTION_EXTRA_RANGES.name, "")
        )
        if 0 <= index < len(extra):
            extra.pop(index)
            parts = [f"{s}-{e}" for s, e in extra]
            self._vm_section[CONFIG_OPTION_EXTRA_RANGES.name] = ", ".join(parts)
            Config().write()
        self._rebuild_range_rows()
        self.Layout()
        wx.CallLater(200, self._refresh_installed_list)

    def _build_filter_bar(self):
        sizer = wx.BoxSizer(wx.HORIZONTAL)

        lang_label = wx.StaticText(self, label=_("Language:"))
        sizer.Add(
            lang_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=UI_SMALL_BORDER
        )
        self.lang_combo = wx.ComboBox(
            self, choices=[_(FILTER_ALL)], value=_(FILTER_ALL), style=0
        )
        self.lang_combo.SetMinSize(wx.Size(140, -1))
        sizer.Add(self.lang_combo, flag=wx.RIGHT, border=12)
        self.lang_combo.Bind(wx.EVT_COMBOBOX, self._on_filter)
        self.lang_combo.Bind(wx.EVT_TEXT, self._on_lang_text)
        self.lang_combo.Bind(wx.EVT_KILL_FOCUS, self._on_lang_kill_focus)
        self.lang_combo.Bind(wx.EVT_KEY_DOWN, self._on_lang_key_down)

        gender_label = wx.StaticText(self, label=_("Gender:"))
        sizer.Add(
            gender_label,
            flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            border=UI_SMALL_BORDER,
        )
        self.gender_combo = wx.ComboBox(
            self,
            choices=[_(label) for _key, label in GENDER_CHOICES],
            value=_(GENDER_CHOICES[0][1]),
            style=wx.CB_READONLY,
        )
        sizer.Add(self.gender_combo, flag=wx.RIGHT, border=12)
        self.gender_combo.Bind(wx.EVT_COMBOBOX, self._on_filter)

        sizer.AddStretchSpacer()

        combo_h = self.lang_combo.GetBestSize().height
        icon_size = max(MIN_ICON_SIZE, combo_h - ICON_SIZE_PADDING)
        if _REFRESH_ICON.is_file():
            _img = wx.Image(str(_REFRESH_ICON), wx.BITMAP_TYPE_PNG)
            _img.Rescale(icon_size, icon_size, wx.IMAGE_QUALITY_HIGH)
            refresh_bmp = wx.Bitmap(_img)
        else:
            refresh_bmp = wx.ArtProvider.GetBitmap(
                wx.ART_REDO, wx.ART_BUTTON, wx.Size(icon_size, icon_size)
            )
        refresh_btn = wx.BitmapButton(self, bitmap=refresh_bmp)
        refresh_btn.SetMinSize(wx.Size(-1, combo_h))
        refresh_btn.SetToolTip(_(TOOLTIP_REFRESH_EDGE_TTS))
        refresh_btn.Bind(wx.EVT_BUTTON, self._on_refresh)
        sizer.Add(refresh_btn)

        return sizer

    def _build_discovered_section(self):
        box = wx.StaticBoxSizer(wx.VERTICAL, self, _("Discovered Voices"))
        self.discovered_list = _DiscoveredVoiceList(
            box.GetStaticBox(),
            self,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_VIRTUAL,
            size=(-1, 150),
        )
        self.discovered_list.AppendColumn("", width=PLAY_COL_WIDTH)
        self.discovered_list.SetColumnImage(0, self.discovered_list._header_icon_idx)
        self.discovered_list.AppendColumn(
            _(_COL_HEADER_SHORT_NAME), width=SHORTNAME_COL_WIDTH
        )
        self.discovered_list.AppendColumn(_(_COL_HEADER_LANGUAGE), width=LANG_COL_WIDTH)
        self.discovered_list.AppendColumn(_(_COL_HEADER_GENDER), width=GENDER_COL_WIDTH)
        self.discovered_list.Bind(
            wx.EVT_LIST_ITEM_ACTIVATED, self._on_discovered_activated
        )
        self.discovered_list.Bind(wx.EVT_LEFT_DOWN, self._on_discovered_left_down)
        self.discovered_list.Bind(wx.EVT_MOTION, self._on_discovered_motion)
        self.discovered_list.Bind(
            wx.EVT_LIST_ITEM_SELECTED, self._on_discovered_sel_changed
        )
        self.discovered_list.Bind(
            wx.EVT_LIST_ITEM_DESELECTED, self._on_discovered_sel_changed
        )
        box.Add(self.discovered_list, proportion=1, flag=wx.EXPAND)

        self.discovered_empty_label = wx.StaticText(
            box.GetStaticBox(), label=_("No voices match the current filters.")
        )
        self.discovered_empty_label.Hide()
        box.Add(
            self.discovered_empty_label,
            proportion=1,
            flag=wx.ALIGN_CENTER | wx.ALL,
            border=20,
        )

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.install_btn = wx.Button(box.GetStaticBox(), label=_("Install Selected"))
        self.install_btn.Disable()
        self.install_btn.Bind(wx.EVT_BUTTON, self._on_install_selected)
        btn_sizer.Add(self.install_btn)
        box.Add(btn_sizer, flag=wx.TOP, border=UI_SMALL_BORDER)

        return box

    def _build_installed_section(self):
        box = wx.StaticBoxSizer(wx.VERTICAL, self, _("Installed Voices"))
        self.installed_list = wx.ListCtrl(
            box.GetStaticBox(),
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL,
            size=wx.Size(-1, 120),
        )
        self.installed_list.AppendColumn("", width=PLAY_COL_WIDTH)
        self.installed_list.AppendColumn(
            _(_COL_HEADER_SHORT_NAME), width=SHORTNAME_COL_WIDTH
        )
        self.installed_list.AppendColumn(_(_COL_HEADER_LANGUAGE), width=LANG_COL_WIDTH)
        self.installed_list.AppendColumn(_(_COL_HEADER_GENDER), width=GENDER_COL_WIDTH)
        self.installed_list.AppendColumn(
            _(_COL_HEADER_STATUS), width=STATUS_COL_WIDTH, format=wx.LIST_FORMAT_CENTER
        )
        self.installed_list.AppendColumn(
            _(_COL_HEADER_DEFAULT), width=STAR_COL_WIDTH, format=wx.LIST_FORMAT_CENTER
        )
        self.installed_list.AppendColumn(
            _(_COL_HEADER_FALLBACK), width=STAR_COL_WIDTH, format=wx.LIST_FORMAT_CENTER
        )
        self._init_installed_images()
        self.installed_list.Bind(
            wx.EVT_LIST_ITEM_ACTIVATED, self._on_installed_activated
        )
        self.installed_list.Bind(wx.EVT_LEFT_DOWN, self._on_installed_left_down)
        self.installed_list.Bind(wx.EVT_MOTION, self._on_installed_motion)
        self.installed_list.Bind(
            wx.EVT_LIST_ITEM_SELECTED, self._on_installed_sel_changed
        )
        self.installed_list.Bind(
            wx.EVT_LIST_ITEM_DESELECTED, self._on_installed_sel_changed
        )
        box.Add(self.installed_list, proportion=1, flag=wx.EXPAND)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.repair_btn = wx.Button(box.GetStaticBox(), label=_("Repair"))
        self.repair_btn.Disable()
        self.repair_btn.Bind(wx.EVT_BUTTON, self._on_repair_installed)
        btn_sizer.Add(self.repair_btn, flag=wx.RIGHT, border=UI_SMALL_BORDER)
        self.remove_btn = wx.Button(box.GetStaticBox(), label=_("Remove"))
        self.remove_btn.Disable()
        self.remove_btn.Bind(wx.EVT_BUTTON, self._on_remove_installed)
        btn_sizer.Add(self.remove_btn)
        box.Add(btn_sizer, flag=wx.TOP, border=UI_SMALL_BORDER)

        return box

    def _init_installed_images(self):
        size = PLAY_ICON_SIZE
        bg = wx.SystemSettings.GetColour(wx.SYS_COLOUR_LISTBOX)

        def _make_play_bmp(color):
            bmp = wx.Bitmap(size, size)
            dc = wx.MemoryDC()
            dc.SelectObject(bmp)
            dc.SetBackground(wx.Brush(bg))
            dc.Clear()
            dc.SetBrush(wx.Brush(color))
            dc.SetPen(wx.Pen(color))
            m = size // 5
            dc.DrawPolygon(
                [wx.Point(m, m), wx.Point(m, size - m), wx.Point(size - m, size // 2)]
            )
            dc.SelectObject(wx.NullBitmap)
            return bmp

        image_list = wx.ImageList(size, size)
        self._inst_green_play_idx = image_list.Add(_make_play_bmp(COLOR_PLAY_GREEN))
        self._inst_gray_play_idx = image_list.Add(_make_play_bmp(COLOR_PLAY_GRAY))
        header_icon_idx = -1
        if _AUDIO_CARD_ICON.is_file():
            audio_img = wx.Image(str(_AUDIO_CARD_ICON))
            audio_img.Rescale(size, size, wx.IMAGE_QUALITY_HIGH)
            header_icon_idx = image_list.Add(wx.Bitmap(audio_img))
        self.installed_list.AssignImageList(image_list, wx.IMAGE_LIST_SMALL)
        if header_icon_idx != -1:
            self.installed_list.SetColumnImage(COL_INST_PLAY, header_icon_idx)

    def _build_progress_section(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.progress_gauge = wx.Gauge(self, range=100, size=wx.Size(-1, 20))
        sizer.Add(self.progress_gauge, flag=wx.EXPAND)
        self.progress_label = wx.StaticText(self, label="")
        sizer.Add(self.progress_label, flag=wx.TOP, border=2)
        return sizer

    def _build_close_button(self):
        close_btn = wx.Button(self, label=_("Close"))
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        return close_btn

    # -- Data loading ----------------------------------------------

    def _load_data(self):
        self._refresh_installed_list()
        self._update_progress(0, _("Loading voices from edge-tts..."))
        wx.CallAfter(self._start_voice_load)

    def _populate_language_filter(self):
        lang_names = set()
        for voice in self.discovered_voices:
            name = _locale_to_language_name(voice.get(_VOICE_KEY_LOCALE, ""))
            if name:
                lang_names.add(name)
        self._lang_combo_updating = True
        self.lang_combo.Clear()
        self.lang_combo.Append(_(FILTER_ALL))
        for name in sorted(lang_names):
            self.lang_combo.Append(name)
        self._lang_combo_updating = False
        self.lang_combo.SetSelection(0)
        self.lang_combo.SetMinSize(self.lang_combo.GetBestSize())

    def _start_voice_load(self):
        thread = threading.Thread(target=self._fetch_discovered_thread, daemon=True)
        thread.start()

    def _fetch_discovered_thread(self):
        try:
            voices = list_voices()
        except Exception:  # noqa: BLE001 - broad catch intentional; libraries raise diverse exceptions
            wx.CallAfter(self._on_voice_load_error)
            return
        wx.CallAfter(self._on_voices_loaded, voices)

    def _on_voices_loaded(self, voices):
        self.discovered_voices = voices
        self._populate_language_filter()
        self._refresh_discovered_list()
        self._refresh_installed_list()
        self._update_progress(0, "")

    def _on_voice_load_error(self):
        logger.exception("Failed to fetch voices from edge-tts")
        wx.MessageBox(
            _("Could not fetch voices from edge-tts. Check your internet connection."),
            _("Error"),
            wx.OK | wx.ICON_ERROR,
        )
        self._update_progress(0, "")

    def _refresh_voices(self):
        self._update_progress(0, _("Loading voices from edge-tts..."))
        self._start_voice_load()

    def _on_refresh(self, event):
        self._refresh_voices()

    def _on_filter(self, event):
        self._refresh_discovered_list()

    def _on_lang_text(self, event):
        if self._lang_combo_updating:
            return
        text = self.lang_combo.GetValue()
        if not text:
            self._lang_combo_updating = True
            self.lang_combo.SetValue(_(FILTER_ALL))
            self.lang_combo.SetSelection(0)
            self._lang_combo_updating = False
            self._on_filter(None)
            event.Skip()
            return
        self._on_filter(None)
        event.Skip()

    def _on_lang_kill_focus(self, event):
        self._resolve_lang_text()
        event.Skip()

    def _on_lang_key_down(self, event):
        if event.GetKeyCode() == wx.WXK_RETURN:
            self._resolve_lang_text()
        event.Skip()

    def _resolve_lang_text(self):
        text = self.lang_combo.GetValue()
        if not text or text.lower() == "all":
            return
        text_lower = text.lower()
        for i in range(self.lang_combo.GetCount()):
            item = self.lang_combo.GetString(i)
            if item.lower().startswith(text_lower) and item.lower() != text_lower:
                self._lang_combo_updating = True
                self.lang_combo.SetValue(item)
                self._lang_combo_updating = False
                self._on_filter(None)
                break

    # -- Helpers ---------------------------------------------------

    @staticmethod
    def _get_selected_shortname(listctrl, col: int = 0) -> str | None:
        idx = listctrl.GetFirstSelected()
        if idx == -1:
            return None
        return listctrl.GetItemText(idx, col)

    # -- Discovered voices -----------------------------------------

    def _refresh_discovered_list(self):
        lang_filter = self.lang_combo.GetValue().lower()
        is_lang_all = (
            self.lang_combo.GetSelection() == 0 or lang_filter == _(FILTER_ALL).lower()
        )
        gender_idx = self.gender_combo.GetSelection()
        gender_filter = (
            GENDER_CHOICES[gender_idx][0].lower()
            if gender_idx != wx.NOT_FOUND
            else _GENDER_ALL.lower()
        )

        self.filtered_voices = []
        for v in self.discovered_voices:
            gender_val = v.get(_VOICE_KEY_GENDER, "").lower()
            locale = v.get(_VOICE_KEY_LOCALE, "").lower()

            if gender_filter != _GENDER_ALL.lower() and gender_val != gender_filter:
                continue

            if not is_lang_all:
                match = next(
                    (
                        lang
                        for lang in pycountry.languages
                        if hasattr(lang, "name")
                        and lang.name.lower().startswith(lang_filter)
                    ),
                    None,
                )
                if match and hasattr(match, "alpha_2"):
                    if not locale.startswith(match.alpha_2.lower()):
                        continue
                else:
                    continue

            self.filtered_voices.append(v)

        self.discovered_list.SetItemCount(len(self.filtered_voices))
        self.discovered_list.Refresh()
        if self.filtered_voices:
            self.discovered_list.Show()
            self.discovered_empty_label.Hide()
        else:
            self.discovered_list.Hide()
            self.discovered_empty_label.Show()
        self.Layout()
        self._update_install_btn_state()

    def _on_get_discovered_text(self, row, col):
        if row >= len(self.filtered_voices):
            return ""
        v = self.filtered_voices[row]
        if col == COL_DISC_PLAY:
            return ""
        elif col == COL_DISC_SHORTNAME:
            return v.get(_VOICE_KEY_SHORT_NAME, "")
        elif col == COL_DISC_LANGUAGE:
            return _locale_to_language_name(v.get(_VOICE_KEY_LOCALE, ""))
        elif col == COL_DISC_GENDER:
            return _(v.get(_VOICE_KEY_GENDER, ""))
        return ""

    def _on_discovered_activated(self, event):
        self._install_selected_voice()

    def _on_install_selected(self, event):
        self._install_selected_voice()

    def _install_selected_voice(self):
        shortname = self._get_selected_shortname(
            self.discovered_list, col=COL_DISC_SHORTNAME
        )
        if not shortname:
            return
        voice_data = next(
            (
                v
                for v in self.discovered_voices
                if v.get(_VOICE_KEY_SHORT_NAME) == shortname
            ),
            None,
        )
        if not voice_data:
            return
        self._enqueue_install(voice_data)

    def _on_discovered_left_down(self, event):
        pos = event.GetPosition()
        row, _flags = self.discovered_list.HitTest(pos)
        if row == -1:
            event.Skip()
            return
        col = -1
        x = 0
        for c in range(self.discovered_list.GetColumnCount()):
            col_w = self.discovered_list.GetColumnWidth(c)
            if x <= pos.x < x + col_w:
                col = c
                break
            x += col_w
        if col == COL_DISC_PLAY:
            self._play_sample(row)
        else:
            event.Skip()

    def _on_discovered_sel_changed(self, event):
        self._update_install_btn_state()

    def _update_install_btn_state(self):
        if self.discovered_list.GetSelectedItemCount() == 0:
            self.install_btn.Disable()
            return
        row = self.discovered_list.GetFirstSelected()
        if row < 0 or row >= len(self.filtered_voices):
            self.install_btn.Disable()
            return
        shortname = self.filtered_voices[row].get(_VOICE_KEY_SHORT_NAME, "")
        self.install_btn.Enable(not (SOUNDS_DIR / shortname).is_dir())

    def _on_installed_sel_changed(self, event):
        self._update_repair_btn_state()
        self._update_remove_btn_state()

    def _update_repair_btn_state(self):
        if self.installed_list.GetSelectedItemCount() == 0:
            self.repair_btn.Disable()
            return
        row = self.installed_list.GetFirstSelected()
        if row < 0 or row >= len(self.installed_voices):
            self.repair_btn.Disable()
            return
        shortname = self.installed_voices[row].shortname
        if self.queue_active and shortname == self._current_job_shortname:
            self.repair_btn.Disable()
            return
        self.repair_btn.Enable(not self.installed_voices[row].complete)

    def _update_remove_btn_state(self):
        if self.installed_list.GetSelectedItemCount() == 0:
            self.remove_btn.Disable()
            return
        row = self.installed_list.GetFirstSelected()
        shortname = self.installed_list.GetItemText(row, COL_INST_SHORTNAME)
        self.remove_btn.Enable(
            not _is_default_voice(shortname) and not _is_fallback_voice(shortname)
        )

    def _on_discovered_motion(self, event):
        pos = event.GetPosition()
        row, _flags = self.discovered_list.HitTest(pos)
        if row == -1:
            if self._showing_play_tooltip:
                self.discovered_list.SetToolTip(TOOLTIP_DEFAULT)
                self._showing_play_tooltip = False
            event.Skip()
            return
        x = 0
        in_play_col = False
        for col in range(self.discovered_list.GetColumnCount()):
            col_w = self.discovered_list.GetColumnWidth(col)
            if x <= pos.x < x + col_w:
                in_play_col = col == COL_DISC_PLAY
                break
            x += col_w
        if in_play_col != self._showing_play_tooltip:
            self.discovered_list.SetToolTip(
                _(TOOLTIP_PLAY_SAMPLE) if in_play_col else TOOLTIP_DEFAULT
            )
            self._showing_play_tooltip = in_play_col
        event.Skip()

    def _play_sample(self, row: int) -> None:
        if self._play_in_progress:
            return
        if row >= len(self.filtered_voices):
            return
        voice = self.filtered_voices[row]
        shortname = voice.get(_VOICE_KEY_SHORT_NAME, "")
        if not shortname:
            return
        self._play_in_progress = True
        self.discovered_list.Refresh()
        self._set_installed_play_images(gray=True)
        threading.Thread(
            target=self._do_play_sample, args=(shortname,), daemon=True
        ).start()

    def _do_play_sample(self, shortname: str) -> None:
        import tempfile

        cache_dir = Path(tempfile.gettempdir()) / "_prewarning_sample_cache" / shortname
        cache_dir.mkdir(parents=True, exist_ok=True)
        files: list[Path] = []
        for n in SAMPLE_NUMBERS:
            cached = cache_dir / f"{n}{AUDIO_EXTENSION}"
            if not cached.is_file():
                generate(shortname, str(n), cached)
            files.append(cached)
        cached_test = cache_dir / TESTING_FILENAME
        if not cached_test.is_file():
            _do_play_sample_async(shortname, cached_test)
        files.append(cached_test)

        try:
            for f in files:
                Sound.play_file(f)
        finally:
            wx.CallAfter(self._set_play_in_progress_false)

    def _set_play_in_progress_false(self) -> None:
        self._play_in_progress = False
        self.discovered_list.Refresh()
        self._set_installed_play_images(gray=False)

    # -- Installed voices ------------------------------------------

    def _refresh_installed_list(self):
        self.installed_voices = _list_installed_voices(self.discovered_voices)
        self.installed_list.DeleteAllItems()
        self._update_repair_btn_state()
        self.remove_btn.Disable()
        for iv in self.installed_voices:
            idx = self.installed_list.GetItemCount()
            self.installed_list.InsertItem(idx, "")
            self.installed_list.SetItemColumnImage(
                idx, COL_INST_PLAY, self._inst_green_play_idx
            )
            self.installed_list.SetItem(idx, COL_INST_SHORTNAME, iv.shortname)
            self.installed_list.SetItem(idx, COL_INST_LANGUAGE, iv.lang)
            self.installed_list.SetItem(idx, COL_INST_GENDER, _(iv.gender))
            self.installed_list.SetItem(
                idx,
                COL_INST_STATUS,
                STATUS_COMPLETE if iv.complete else STATUS_INCOMPLETE,
            )
            if not iv.complete:
                self.installed_list.SetItemBackgroundColour(idx, COLOR_INCOMPLETE_ROW)
            self.installed_list.SetItem(
                idx,
                COL_INST_DEFAULT,
                STAR_FILLED if _is_default_voice(iv.shortname) else STAR_EMPTY,
            )
            self.installed_list.SetItem(
                idx,
                COL_INST_FALLBACK,
                STAR_FILLED if _is_fallback_voice(iv.shortname) else STAR_EMPTY,
            )
        self._installed_tooltip_key = NO_TOOLTIP_KEY

    def _refresh_star_columns(self):
        for row in range(self.installed_list.GetItemCount()):
            shortname = self.installed_list.GetItemText(row, COL_INST_SHORTNAME)
            self.installed_list.SetItem(
                row,
                COL_INST_DEFAULT,
                STAR_FILLED if _is_default_voice(shortname) else STAR_EMPTY,
            )
            self.installed_list.SetItem(
                row,
                COL_INST_FALLBACK,
                STAR_FILLED if _is_fallback_voice(shortname) else STAR_EMPTY,
            )
        self._installed_tooltip_key = NO_TOOLTIP_KEY

    def _on_installed_activated(self, event):
        idx = event.GetIndex()
        if idx < 0 or idx >= len(self.installed_voices):
            return
        iv = self.installed_voices[idx]
        self._play_installed_sample(iv.shortname)

    def _get_installed_tooltip(self, row: int, col: int) -> str:
        if col == COL_INST_PLAY:
            return _(TOOLTIP_PLAY_SAMPLE)
        if col == COL_INST_STATUS:
            shortname = self.installed_list.GetItemText(row, COL_INST_SHORTNAME)
            extra = parse_extra_ranges(
                self._vm_section.get(CONFIG_OPTION_EXTRA_RANGES.name, "")
            )
            return _voice_status_detail(SOUNDS_DIR / shortname, extra)
        if col == COL_INST_DEFAULT:
            shortname = self.installed_list.GetItemText(row, COL_INST_SHORTNAME)
            return (
                _(TOOLTIP_IS_DEFAULT)
                if _is_default_voice(shortname)
                else _(TOOLTIP_SET_DEFAULT)
            )
        if col == COL_INST_FALLBACK:
            shortname = self.installed_list.GetItemText(row, COL_INST_SHORTNAME)
            return (
                _(TOOLTIP_IS_FALLBACK)
                if _is_fallback_voice(shortname)
                else _(TOOLTIP_SET_FALLBACK)
            )
        return TOOLTIP_DEFAULT

    def _on_installed_left_down(self, event):
        pos = event.GetPosition()
        idx, flags = self.installed_list.HitTest(pos)
        if idx == -1 or flags == wx.LIST_HITTEST_NOWHERE:
            event.Skip()
            return
        col = -1
        x = 0
        for c in range(self.installed_list.GetColumnCount()):
            col_w = self.installed_list.GetColumnWidth(c)
            if x <= pos.x < x + col_w:
                col = c
                break
            x += col_w
        if col is None:
            event.Skip()
            return
        if col in (COL_INST_DEFAULT, COL_INST_FALLBACK):
            iv = self.installed_voices[idx]
            if col == COL_INST_DEFAULT:
                _toggle_default_voice(iv.shortname)
            else:
                _toggle_fallback_voice(iv.shortname)
            self._refresh_star_columns()
            self.installed_list.SetToolTip(self._get_installed_tooltip(idx, col))
            self._update_remove_btn_state()
        elif col == COL_INST_PLAY:
            if idx < len(self.installed_voices):
                self._play_installed_sample(self.installed_voices[idx].shortname)
        else:
            event.Skip()

    def _on_installed_motion(self, event):
        pos = event.GetPosition()
        row, _flags = self.installed_list.HitTest(pos)
        if row == -1:
            if self._installed_tooltip_key != NO_TOOLTIP_KEY:
                self.installed_list.SetToolTip(TOOLTIP_DEFAULT)
                self._installed_tooltip_key = NO_TOOLTIP_KEY
            event.Skip()
            return
        x = 0
        col = -1
        for c in range(self.installed_list.GetColumnCount()):
            col_w = self.installed_list.GetColumnWidth(c)
            if x <= pos.x < x + col_w:
                col = c
                break
            x += col_w
        key = (row, col)
        if key != self._installed_tooltip_key:
            if col == COL_INST_PLAY:
                self.installed_list.SetToolTip(_(TOOLTIP_PLAY_SAMPLE))
            elif col == COL_INST_STATUS:
                shortname = self.installed_list.GetItemText(row, COL_INST_SHORTNAME)
                extra = parse_extra_ranges(
                    self._vm_section.get(CONFIG_OPTION_EXTRA_RANGES.name, "")
                )
                detail = _voice_status_detail(SOUNDS_DIR / shortname, extra)
                self.installed_list.SetToolTip(detail)
            elif col in (COL_INST_DEFAULT, COL_INST_FALLBACK):
                self.installed_list.SetToolTip(self._get_installed_tooltip(row, col))
            else:
                self.installed_list.SetToolTip(TOOLTIP_DEFAULT)
            self._installed_tooltip_key = key
        event.Skip()

    def _play_installed_sample(self, shortname: str) -> None:
        if self._play_in_progress:
            return
        self._play_in_progress = True
        self.discovered_list.Refresh()
        self._set_installed_play_images(gray=True)
        threading.Thread(
            target=self._do_play_installed_sample, args=(shortname,), daemon=True
        ).start()

    def _set_installed_play_images(self, gray: bool) -> None:
        idx = self._inst_gray_play_idx if gray else self._inst_green_play_idx
        for row in range(self.installed_list.GetItemCount()):
            self.installed_list.SetItemColumnImage(row, COL_INST_PLAY, idx)

    def _do_play_installed_sample(self, shortname: str) -> None:
        for n in SAMPLE_NUMBERS:
            f = SOUNDS_DIR / shortname / f"{n}{AUDIO_EXTENSION}"
            if f.is_file():
                Sound().play_sound(str(f.relative_to(SOUNDS_DIR)))
        testing = SOUNDS_DIR / shortname / TESTING_FILENAME
        if testing.is_file():
            Sound().play_sound(str(testing.relative_to(SOUNDS_DIR)))
        wx.CallAfter(self._set_installed_play_in_progress_false)

    def _set_installed_play_in_progress_false(self) -> None:
        self._play_in_progress = False
        self.discovered_list.Refresh()
        self._set_installed_play_images(gray=False)

    def _on_repair_installed(self, event):
        shortname = self._get_selected_shortname(
            self.installed_list, col=COL_INST_SHORTNAME
        )
        if shortname:
            self._enqueue_repair(shortname)

    def _on_remove_installed(self, event):
        shortname = self._get_selected_shortname(
            self.installed_list, col=COL_INST_SHORTNAME
        )
        if not shortname:
            return
        if _is_default_voice(shortname) or _is_fallback_voice(shortname):
            wx.MessageBox(
                _(
                    "Cannot remove the current default or fallback voice. "
                    "Set a different voice as default/fallback first."
                ),
                _("Remove Disabled"),
                wx.OK | wx.ICON_WARNING,
            )
            return
        if self.queue_active and shortname == self._current_job_shortname:
            result = wx.MessageBox(
                _("An install or repair is currently in progress.")
                + "\n\n"
                + _("Removing voice '{shortname}' will cancel the operation.").format(
                    shortname=shortname
                )
                + "\n\n"
                + _("Continue?"),
                _("Cancel Operation"),
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
            )
            if result != wx.YES:
                return
            _cancel_event.set()
        elif self.queue_active:
            self._removed_shortnames.add(shortname)
        dlg = wx.MessageDialog(
            self,
            _("Remove voice '{shortname}'?").format(shortname=shortname)
            + "\n\n"
            + _("All files under sounds/{shortname}/ will be deleted.").format(
                shortname=shortname
            ),
            _("Confirm Remove"),
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
        )
        if dlg.ShowModal() == wx.ID_YES:
            voice_dir = SOUNDS_DIR / shortname
            if voice_dir.is_dir():
                _remove_voice_dir(voice_dir)
            self._refresh_installed_list()
        dlg.Destroy()

    # -- Install queue ---------------------------------------------

    def _enqueue_install(self, voice_data: Voice):
        shortname = voice_data.get(_VOICE_KEY_SHORT_NAME, "")
        _save_metadata_entry(voice_data)
        self._refresh_installed_list()
        extra = parse_extra_ranges(
            self._vm_section.get(CONFIG_OPTION_EXTRA_RANGES.name, "")
        )
        ranges = [(DEFAULT_RANGE_START, DEFAULT_RANGE_END)]
        ranges.extend(extra)
        self.install_queue.put(_InstallJob(shortname, ranges, voice_data))
        self._start_queue()

    def _enqueue_repair(self, shortname: str):
        extra = parse_extra_ranges(
            self._vm_section.get(CONFIG_OPTION_EXTRA_RANGES.name, "")
        )
        ranges = [(DEFAULT_RANGE_START, DEFAULT_RANGE_END)]
        ranges.extend(extra)
        voice_data = next(
            (
                v
                for v in self.discovered_voices
                if v.get(_VOICE_KEY_SHORT_NAME) == shortname
            ),
            None,
        )
        if voice_data is not None:
            self.install_queue.put(
                _InstallJob(shortname, ranges, voice_data, repair=True)
            )
            self._start_queue()

    def _start_queue(self):
        if not self.queue_active:
            self.queue_active = True
            thread = threading.Thread(target=self._process_queue, daemon=True)
            thread.start()

    def _process_queue(self):
        try:
            while not self.install_queue.empty():
                job = self.install_queue.get()
                if job.shortname in self._removed_shortnames:
                    self._removed_shortnames.discard(job.shortname)
                    continue
                self._current_job_shortname = job.shortname
                action = _("Repairing") if job.repair else _("Installing")

                try:
                    _process_job(job, self._update_progress, action)
                except _InstallCancelled:
                    _drain_queue(self.install_queue)
                    break

                wx.CallAfter(
                    self._update_progress, 0, _("Finished") + f" {job.shortname}"
                )
                wx.CallAfter(self._refresh_installed_list)
                wx.CallAfter(self._refresh_discovered_list)
        finally:
            self.queue_active = False
            self._current_job_shortname = None
            _cancel_event.clear()
            wx.CallAfter(self._update_progress, 0, "")

    def _update_progress(self, pct: int, label: str):
        try:
            self.progress_gauge.SetValue(pct)
            self.progress_label.SetLabel(label)
        except RuntimeError:
            pass

    # -- Close -----------------------------------------------------

    def _on_close(self, event):
        all_valid, has_conflicts = self._validate_all_range_rows()
        incomplete = [iv for iv in self.installed_voices if not iv.complete]

        msgs: list[str] = []
        if self.queue_active:
            msgs.append(
                _(
                    "An install or repair is currently in progress. "
                    "Closing will cancel the operation."
                )
            )
        if not all_valid:
            msgs.append(
                _(
                    "One or more extra ranges have invalid values. "
                    "These ranges will be discarded when closing."
                )
            )
        elif has_conflicts:
            msgs.append(
                _(
                    "One or more extra ranges overlap with another range. "
                    "These ranges will still be saved, but may generate "
                    "files that already exist."
                )
            )
        if incomplete:
            names = ", ".join(iv.shortname for iv in incomplete)
            msgs.append(
                _(
                    "The following installed voices are incomplete: {names}. "
                    "They will not have all required sound files available. "
                    "Some numbers may fall back to the default ding sound "
                    "when announced. Use Repair to generate the missing files."
                ).format(names=names)
            )
        if self._bib_range is not None and not self._is_bib_range_covered():
            bib_min, bib_max = self._bib_range
            msgs.append(
                _(
                    "The start list bib number range ({min} - {max}) is not fully "
                    "covered by the configured number ranges. Some bib numbers "
                    "will not have voice files and will fall back to the default "
                    "ding sound when announced."
                ).format(min=bib_min, max=bib_max)
            )

        if msgs:
            content = (
                _("There are issues that may affect voice playback.")
                + "\n\n"
                + "\n\n".join(f"• {m}" for m in msgs)
                + "\n\n"
                + _("Close anyway?")
            )
            result = wx.MessageBox(
                content,
                _("Confirm Close"),
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
            )
            if result != wx.YES:
                return
            if self.queue_active:
                _cancel_event.set()

        self.Destroy()
