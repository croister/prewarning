# -*- coding: utf-8 -*-

import logging
from typing import Dict, List

from utils.config import Config, ConfigOptionDefinition, ConfigSectionDefinition
from utils.config_definitions import (
    ConfigSectionEnableType,
    ConfigSectionOptionDefinition,
    ConfigSelectorDefinition,
)
from utils.constants import PUNCH_KEY_CONTROL_CODE
from utils.meos_info_server import MeosInfoServer, MeosPunchListener
from validators.regex_validators import is_control_ids
from ._base import _PunchSourceBase

_MODULE_LOGGER_NAME = "PunchSourceMeos"


class PunchSourceMeos(MeosPunchListener, _PunchSourceBase):
    """
    A Punch Source that reads punches from a running MeOS instance via its
    Information Server REST API (MOP protocol) and optional UDP broadcast.
    """

    name = __qualname__

    display_name = "MeOS Information Server Punch Source"

    description = (
        "Fetches electronic punches from a running "
        '<a href="https://www.melin.nu/meos/">MeOS</a> instance via its '
        "Information Server REST API. "
        "MeOS must have the Information Server enabled (Services \u2192 Information Server). "
        "For real-time notifications, enable 'Send and receive fast advance information' "
        "in MeOS (requires a networked setup)."
    )

    CONFIG_OPTION_CONTROL_CODES = ConfigOptionDefinition(
        name="ControlCodes",
        display_name="Control Codes",
        value_type=str,
        description=(
            "The control codes to use for pre-warning, separated by space. "
            "Use the selector to populate the list from MeOS. "
            "The selector shows controls that MeOS has identified as radio controls "
            "(controls with a name and OK status, or explicitly flagged as radio). "
            "If no such controls exist, all controls in the competition are shown as a fallback."
        ),
        mandatory=True,
        validator=is_control_ids,
    )

    MEOS_PUNCH_SOURCE_CONFIG_SECTION = ConfigSectionDefinition(
        name=name,
        display_name=display_name,
        option_definitions=[CONFIG_OPTION_CONTROL_CODES],
        enable_type=ConfigSectionEnableType.IF_ENABLED,
        requires=[MeosInfoServer.config_section_definition()],
        sort_key_prefix=30,
    )

    CONTROLS_SELECTOR = ConfigSelectorDefinition(
        function=lambda url: MeosInfoServer().get_selector_controls(),
        parameters=[
            ConfigSectionOptionDefinition(
                section_name=MeosInfoServer.CONFIG_SECTION_MEOS,
                option_definition=MeosInfoServer.CONFIG_OPTION_URL,
            ),
        ],
        message="Unable to fetch controls from the MeOS Information Server.",
    )

    CONFIG_OPTION_CONTROL_CODES.set_selector(CONTROLS_SELECTOR)

    Config.register_config_section_definition(MEOS_PUNCH_SOURCE_CONFIG_SECTION)

    @classmethod
    def config_section_definition(cls) -> ConfigSectionDefinition:
        return cls.MEOS_PUNCH_SOURCE_CONFIG_SECTION

    def __repr__(self) -> str:
        return f"PunchSourceMeos(running={self.is_running()}, control_codes={self._control_codes})"

    def __str__(self) -> str:
        return repr(self)

    def __init__(self) -> None:
        _PunchSourceBase.__init__(self)
        self.logger = logging.getLogger(_MODULE_LOGGER_NAME)
        self._control_codes: List[str] = []
        self._running = False
        self.update()
        self.logger.debug(self)

    def __del__(self) -> None:
        self.stop()

    def start(self) -> None:
        self._running = True
        MeosInfoServer().register_meos_punch_listener(self)
        MeosInfoServer().start()
        self.logger.debug("Started")

    def stop(self) -> None:
        if self._running:
            MeosInfoServer().unregister_meos_punch_listener(self)
            MeosInfoServer().stop()
            self._running = False
            self.logger.debug("Stopped")

    def is_running(self) -> bool:
        return self._running

    def config_updated(self, section_names: List[str]) -> None:
        self.update()

    def update(self) -> None:
        self._parse_config()

    def _parse_config(self) -> None:
        section = Config().get_section(self.name)
        codes = self.CONFIG_OPTION_CONTROL_CODES.get_value(section)
        self._control_codes = codes.split() if codes else []

    def reset_tracking(self) -> None:
        MeosInfoServer().reset()

    def meos_punch_received(self, punch: Dict) -> None:
        if not self._running:
            return
        if punch.get(PUNCH_KEY_CONTROL_CODE) not in self._control_codes:
            self.logger.debug(
                "Punch filtered out: controlCode=%s", punch.get(PUNCH_KEY_CONTROL_CODE)
            )
            return
        self.logger.debug("Punch accepted: %s", punch)
        self._notify_punch_listeners(punch)
