import logging

from utils.config import Config, ConfigSectionDefinition
from utils.config_definitions import ConfigSectionEnableType
from utils.i18n import N_
from utils.meos_info_server import MeosInfoServer

from ._base import _StartListSourceBase

_MODULE_LOGGER_NAME = "StartListSourceMeos"


class StartListSourceMeos(_StartListSourceBase):
    """
    A Start List Source that looks up bib number and relay leg from a running
    MeOS instance via its Information Server REST API.
    MeOS must have the Information Server enabled (Services \u2192 Information Server).
    """

    name = __qualname__

    display_name = N_("MeOS Information Server Start List Source")

    description = N_(
        "Looks up team bib number and relay leg from a running "
        '<a href="https://www.melin.nu/meos/">MeOS</a> instance via its '
        "Information Server REST API. "
        "MeOS must have the Information Server enabled (Services \u2192 Information Server). "
        "If the received punch data already contains the bib number and leg, "
        "no operation will be performed."
    )

    START_LIST_SOURCE_MEOS_CONFIG_SECTION = ConfigSectionDefinition(
        name=name,
        display_name=display_name,
        option_definitions=[],
        enable_type=ConfigSectionEnableType.IF_ENABLED,
        requires=[MeosInfoServer.config_section_definition()],
        sort_key_prefix=40,
    )

    Config.register_config_section_definition(START_LIST_SOURCE_MEOS_CONFIG_SECTION)

    @classmethod
    def config_section_definition(cls) -> ConfigSectionDefinition:
        return cls.START_LIST_SOURCE_MEOS_CONFIG_SECTION

    def __repr__(self) -> str:
        return f"StartListSourceMeos(running={self._running})"

    def __str__(self) -> str:
        return repr(self)

    def __init__(self) -> None:
        super().__init__()
        self.logger = logging.getLogger(_MODULE_LOGGER_NAME)
        self._running = False
        self.logger.debug(self)

    def __del__(self) -> None:
        self.stop()

    def start(self) -> None:
        self._running = True
        MeosInfoServer().start()

    def stop(self) -> None:
        if self._running:
            MeosInfoServer().stop()
            self._running = False

    def is_running(self) -> bool:
        return self._running

    def config_updated(self, section_names: list[str]) -> None:
        pass

    def lookup_from_card_number(self, card_number: str) -> dict[str, str] | None:
        if not self._running:
            self.logger.debug("NOT started, ignoring request!")
            return None
        return MeosInfoServer().lookup_card(card_number)

    def get_bib_range(self) -> tuple[int, int] | None:
        """Returns the range of bib numbers from MeOS."""
        if not self._running:
            return None
        return MeosInfoServer().get_bib_range()

    def get_team_count(self) -> int | None:
        """Returns the number of teams from MeOS."""
        if not self._running:
            return None
        return MeosInfoServer().get_team_count()

    def get_runner_count(self) -> int | None:
        """Returns the number of runners from MeOS."""
        if not self._running:
            return None
        return MeosInfoServer().get_runner_count()
