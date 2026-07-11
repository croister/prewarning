# -*- coding: utf-8 -*-

import logging
import socket
import struct
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from threading import Event, Thread
from typing import Dict, List, Set
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

from utils.config import Config, ConfigOptionDefinition, ConfigSectionDefinition
from utils.config_definitions import (
    ConfigSectionEnableType,
    ConfigSectionOptionDefinition,
    ConfigSelectorDefinition,
    ConfigVerifierDefinition,
    RuntimeStateGroup,
    RuntimeStateOptionDefinition,
    SelectionData,
    SelectionResult,
    SelectionType,
    VerificationResult,
)
from utils.singleton import Singleton
from utils.state_saver import StateSaverMixin
from validators.url_validators import is_http_or_https_url
from utils.config import ConfigConsumer
from utils.i18n import N_
from utils.constants import (
    FETCH_INTERVAL_VALID_VALUES,
    PUNCH_KEY_BIB_NUMBER,
    PUNCH_KEY_CARD_NUMBER,
    PUNCH_KEY_CONTROL_CODE,
    PUNCH_KEY_COUNTRY,
    PUNCH_KEY_ID,
    PUNCH_KEY_IS_LAST_LEG,
    PUNCH_KEY_PASSED_TIME,
    PUNCH_KEY_RELAY_LEG,
)

_MODULE_LOGGER_NAME = "MeosInfoServer"

_MOP_NS = "http://www.melin.nu/mop"

_INITIAL_DIFF_TOKEN = "zero"

# MOP XML response root tags
_ROOT_TAG_COMPLETE = "MOPComplete"
_ROOT_TAG_DIFF = "MOPDiff"

# MOP XML element tags
_TAG_COMPETITION = "competition"
_TAG_CONTROL = "control"
_TAG_CLASS = "cls"
_TAG_TEAM = "tm"
_TAG_COMPETITOR = "cmp"
_TAG_ORG = "org"
_TAG_BASE = "base"
_TAG_RADIO = "radio"
_TAG_RUNNERS = "r"

# MOP XML attribute names
_ATTR_ID = "id"
_ATTR_BIB = "bib"
_ATTR_DATE = "date"
_ATTR_ZEROTIME = "zerotime"
_ATTR_NEXT_DIFFERENCE = "nextdifference"
_ATTR_NAT = "nat"
_ATTR_ORG = "org"

# MOP sentinel value for empty competitor slot
_MOP_EMPTY_SLOT = "0"

# MeOS lookup API element tags
_LOOKUP_TAG_COMPETITOR = "Competitor"
_LOOKUP_TAG_TEAM = "Team"
_LOOKUP_TAG_LEG = "Leg"

# Internal cache dict keys for competitor info
_CMP_KEY_CARD = "card"
_CMP_KEY_TEAM_ID = "team_id"
_CMP_KEY_LEG = "leg"
_CMP_KEY_START_TIME = "st"
_CMP_KEY_NAT = "nat"

MEOS_INFO_SERVER_RUNTIME_STATE = RuntimeStateGroup("meos_info_server.dat")


_HTTP_TIMEOUT_SECONDS = 10
_HTTP_SELECTOR_TIMEOUT_SECONDS = 3


def _find(elem: ET.Element, tag: str) -> ET.Element | None:
    """Find child element, trying with MOP namespace first, then without."""
    result = elem.find(f"{{{_MOP_NS}}}{tag}")
    if result is None:
        result = elem.find(tag)
    return result


def _strip_ns(tag: str) -> str:
    return tag.partition("}")[2] if "}" in tag else tag


def _fetch_xml(url: str, timeout: int = _HTTP_TIMEOUT_SECONDS) -> ET.Element:
    req = Request(url)
    response = urlopen(req, timeout=timeout)
    data = response.read()
    return ET.fromstring(data)


def _verify_url(url: str) -> VerificationResult:
    try:
        root = _fetch_xml(
            f"{url.rstrip('/')}/meos?get=competition",
            timeout=_HTTP_SELECTOR_TIMEOUT_SECONDS,
        )
        if _strip_ns(root.tag) in (_ROOT_TAG_COMPLETE, _ROOT_TAG_DIFF):
            competition = root.find(f"{{{_MOP_NS}}}{_TAG_COMPETITION}")
            if competition is None:
                competition = root.find(_TAG_COMPETITION)
            name = competition.text if competition is not None else "?"
            return VerificationResult(message=f"Connected. Competition: {name}")
        return VerificationResult(
            message="Unexpected response from MeOS.", status=False
        )
    except Exception as e:
        logging.getLogger(_MODULE_LOGGER_NAME).debug("_verify_url: %s", e)
        msg = str(e)
        if "timed out" in msg:
            msg = f"Connection timed out. Is MeOS running at {url}?"
        elif "Connection refused" in msg or "10061" in msg:
            msg = f"Connection refused. Is MeOS running at {url}?"
        elif "Name or service not known" in msg or "getaddrinfo failed" in msg:
            msg = f"Unknown host. Check the URL: {url}"
        return VerificationResult(message=msg, status=False)


def _select_controls(url: str) -> SelectionResult | bool:
    try:
        result = SelectionResult(
            caption="Control Codes",
            message="Select control codes for pre-warning:",
            selection_type=SelectionType.MULTIPLE,
        )
        base = url.rstrip("/")

        # Build control id -> name map
        ctrl_root = _fetch_xml(
            f"{base}/meos?get=control", timeout=_HTTP_SELECTOR_TIMEOUT_SECONDS
        )
        control_map: Dict[int, str] = {}
        for elem in ctrl_root:
            if _strip_ns(elem.tag) == _TAG_CONTROL:
                ctrl_id = int(elem.get(_ATTR_ID, 0))
                control_map[ctrl_id] = elem.text or str(ctrl_id)

        # Collect radio control IDs from classes
        cls_root = _fetch_xml(
            f"{base}/meos?get=class", timeout=_HTTP_SELECTOR_TIMEOUT_SECONDS
        )
        radio_ids: Set[int] = set()
        for elem in cls_root:
            if _strip_ns(elem.tag) == _TAG_CLASS:
                radio_attr = elem.get(_TAG_RADIO, "")
                for leg in radio_attr.split(";"):
                    for rid in leg.split(","):
                        rid = rid.strip()
                        if rid:
                            radio_ids.add(int(rid))

        # Fall back to all controls if no radio controls found
        ids_to_show = radio_ids if radio_ids else set(control_map.keys())

        for ctrl_id in sorted(ids_to_show):
            name = control_map.get(ctrl_id, str(ctrl_id))
            result.add_value(SelectionData(str(ctrl_id), f"{ctrl_id}: {name}"))

        return result
    except Exception as e:
        logging.getLogger(_MODULE_LOGGER_NAME).debug("_select_controls: %s", e)
        return False


class MeosPunchListener(ABC):
    """Internal listener interface between MeosInfoServer and MeOS-based punch sources.
    Distinct from PunchListener which is the external interface on _PunchSourceBase."""

    @abstractmethod
    def meos_punch_received(self, punch: Dict) -> None:
        pass


class _MeosInfoServerMeta(type(ConfigConsumer), type(Singleton)):  # type: ignore[misc]
    pass


class MeosInfoServer(
    StateSaverMixin, ConfigConsumer, Singleton, metaclass=_MeosInfoServerMeta
):
    """
    Shared engine for MeOS-based punch and start list sources.

    Polls the MeOS Information Server REST API (MOP protocol) and optionally
    listens for UDP broadcast packets (requires MeOS networked setup with
    'Send and receive fast advance information' enabled).
    """

    CONFIG_SECTION_MEOS = __qualname__

    CONFIG_OPTION_URL = ConfigOptionDefinition(
        name="URL",
        display_name=N_("URL"),
        value_type=str,
        description=N_(
            "Base URL of the MeOS Information Server, e.g. http://localhost:2009."
        ),
        default_value="http://localhost:2009",
        mandatory=True,
        validator=is_http_or_https_url,
    )

    CONFIG_OPTION_FETCH_INTERVAL = ConfigOptionDefinition(
        name="FetchIntervalSeconds",
        display_name=N_("Fetch Interval"),
        value_type=int,
        description=N_("Seconds between polls of the MeOS Information Server."),
        default_value=10,
        valid_values=FETCH_INTERVAL_VALID_VALUES,
    )

    CONFIG_OPTION_USE_UDP = ConfigOptionDefinition(
        name="UseUDP",
        display_name=N_("Use UDP"),
        value_type=bool,
        description=N_(
            "Enable UDP listener for real-time punch notifications. "
            "Requires MeOS to be running in a networked setup with "
            "'Send and receive fast advance information' enabled. "
            "When a UDP packet is received, a diff fetch is triggered immediately "
            "and the interval timer is reset. "
            "Interval polling always runs as a fallback regardless of this setting."
        ),
        default_value=True,
    )

    CONFIG_OPTION_UDP_PORT = ConfigOptionDefinition(
        name="UDPPort",
        display_name=N_("UDP Port"),
        value_type=int,
        description=N_(
            "UDP broadcast port for MeOS fast advance information. "
            "Must match the DirectPort setting in MeOS Local Settings (default 21338). "
            "When running multiple competitions on the same network, use a different "
            "DirectPort in each MeOS instance to avoid receiving packets from the wrong competition."
        ),
        default_value=21338,
    )

    CONFIG_OPTION_NEXT_DIFFERENCE = RuntimeStateOptionDefinition(
        runtime_state_group=MEOS_INFO_SERVER_RUNTIME_STATE,
        name="NextDifference",
        display_name=N_("Next Difference"),
        value_type=str,
        description=N_("MOP diff token, persisted across restarts."),
        default_value=_INITIAL_DIFF_TOKEN,
        read_only=True,
    )

    MEOS_INFO_SERVER_CONFIG_SECTION = ConfigSectionDefinition(
        name=CONFIG_SECTION_MEOS,
        display_name=N_("MeOS Information Server"),
        option_definitions=[
            CONFIG_OPTION_URL,
            CONFIG_OPTION_FETCH_INTERVAL,
            CONFIG_OPTION_USE_UDP,
            CONFIG_OPTION_UDP_PORT,
            CONFIG_OPTION_NEXT_DIFFERENCE,
        ],
        enable_type=ConfigSectionEnableType.IF_REQUIRED,
        sort_key_prefix=20,
    )

    URL_VERIFIER = ConfigVerifierDefinition(
        function=_verify_url,
        parameters=[
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_MEOS,
                option_definition=CONFIG_OPTION_URL,
            ),
        ],
        message="Unable to connect to the MeOS Information Server.",
    )

    CONFIG_OPTION_URL.set_verifier(URL_VERIFIER)

    CONTROLS_SELECTOR = ConfigSelectorDefinition(  # type: ignore[name-defined]
        function=_select_controls,
        parameters=[
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_MEOS,
                option_definition=CONFIG_OPTION_URL,
            ),
        ],
        message="Unable to fetch controls from the MeOS Information Server.",
    )

    Config.register_config_section_definition(MEOS_INFO_SERVER_CONFIG_SECTION)

    @classmethod
    def config_section_definition(cls) -> ConfigSectionDefinition:
        return cls.MEOS_INFO_SERVER_CONFIG_SECTION

    def __repr__(self) -> str:
        return f"MeosInfoServer(url={self._url})"

    def __str__(self) -> str:
        return repr(self)

    def __init__(self) -> None:
        ConfigConsumer.__init__(self)
        StateSaverMixin.__init__(
            self, self.CONFIG_SECTION_MEOS, [MEOS_INFO_SERVER_RUNTIME_STATE]
        )

        self.logger = logging.getLogger(_MODULE_LOGGER_NAME)

        self._url: str | None = None
        self._fetch_interval: int = self.CONFIG_OPTION_FETCH_INTERVAL.default_value
        self._use_udp: bool = True
        self._udp_port: int = self.CONFIG_OPTION_UDP_PORT.default_value
        self._next_difference: str = _INITIAL_DIFF_TOKEN

        # Caches
        self._zero_time: datetime | None = None
        self._competition_date: datetime | None = None
        self._control_map: Dict[int, str] = {}
        self._radio_control_ids: Set[int] = set()
        self._org_nat: Dict[int, str] = {}
        self._team_bib: Dict[int, str] = {}
        self._team_org: Dict[int, int] = {}
        self._team_leg_count: Dict[int, int] = {}
        self._cmp_info: Dict[int, Dict] = {}
        self._seen_radio: Dict[int, Set[int]] = {}

        self._listeners: List[MeosPunchListener] = []
        self._ref_count: int = 0

        self._poll_event = Event()
        self._stop_event = Event()
        self._suppress_notifications = True
        self._poll_thread: Thread | None = None
        self._udp_thread: Thread | None = None

        # Restore persisted next_difference
        if self._data_read(self.CONFIG_OPTION_NEXT_DIFFERENCE):
            self._next_difference = self._get_value(self.CONFIG_OPTION_NEXT_DIFFERENCE)

        self.update()

    def _parse_config(self) -> None:
        section = Config().get_section(self.CONFIG_SECTION_MEOS)
        self._url = self.CONFIG_OPTION_URL.get_value(section)
        self._fetch_interval = (
            self.CONFIG_OPTION_FETCH_INTERVAL.get_value(section)
            or self.CONFIG_OPTION_FETCH_INTERVAL.default_value
        )
        self._use_udp = self.CONFIG_OPTION_USE_UDP.get_value(section)
        if self._use_udp is None:
            self._use_udp = self.CONFIG_OPTION_USE_UDP.default_value
        self._udp_port = (
            self.CONFIG_OPTION_UDP_PORT.get_value(section)
            or self.CONFIG_OPTION_UDP_PORT.default_value
        )

    def update(self) -> None:
        self._parse_config()

    def config_updated(self, section_names: List[str]) -> None:
        self.update()

    # -- Lifecycle ------------------------------------------------------------

    def start(self) -> None:
        self._ref_count += 1
        if self._ref_count > 1:
            self.logger.debug("start() called, ref_count=%d", self._ref_count)
            return
        self.logger.info("Starting MeosInfoServer (url=%s)", self._url)
        self._stop_event.clear()
        self._poll_event.clear()
        self._poll_thread = Thread(
            target=self._poll_loop, daemon=True, name="MeosInfoServerPollThread"
        )
        self._poll_thread.start()
        if self._use_udp:
            self._udp_thread = Thread(
                target=self._udp_loop, daemon=True, name="MeosInfoServerUDPThread"
            )
            self._udp_thread.start()

    def stop(self) -> None:
        self._ref_count = max(0, self._ref_count - 1)
        if self._ref_count > 0:
            self.logger.debug("stop() called, ref_count=%d", self._ref_count)
            return
        self.logger.info("Stopping MeosInfoServer")
        self._stop_event.set()
        self._poll_event.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=1)
        if self._udp_thread and self._udp_thread.is_alive():
            self._udp_thread.join(timeout=1)
        self._poll_thread = None
        self._udp_thread = None

    def is_running(self) -> bool:
        return self._ref_count > 0

    def reset(self) -> None:
        self._next_difference = _INITIAL_DIFF_TOKEN
        self._seen_radio.clear()
        self._save_state()
        self._poll_event.set()

    # -- Cache priming ---------------------------------------------------------

    def _prime_caches(self) -> None:
        if not self._url:
            return
        base = self._url.rstrip("/")
        try:
            self._fetch_competition(base)
        except Exception as e:
            self.logger.warning("Failed to prime competition cache: %s", e)
        if self._stop_event.is_set():
            return
        try:
            self._fetch_controls(base)
        except Exception as e:
            self.logger.warning("Failed to prime control cache: %s", e)
        if self._stop_event.is_set():
            return
        try:
            self._fetch_class_radio(base)
        except Exception as e:
            self.logger.warning("Failed to prime class cache: %s", e)
        if self._stop_event.is_set():
            return
        try:
            self._fetch_orgs(base)
        except Exception as e:
            self.logger.warning("Failed to prime org cache: %s", e)
        if self._stop_event.is_set():
            return
        try:
            self._fetch_teams(base)
        except Exception as e:
            self.logger.warning("Failed to prime team cache: %s", e)

    def _fetch_competition(self, base: str) -> None:
        root = _fetch_xml(f"{base}/meos?get=competition")
        for elem in root:
            if _strip_ns(elem.tag) == _TAG_COMPETITION:
                date_str = elem.get(_ATTR_DATE, "")
                zero_str = elem.get(_ATTR_ZEROTIME, "00:00:00")
                try:
                    self._zero_time = datetime.strptime(
                        f"{date_str} {zero_str}", "%Y-%m-%d %H:%M:%S"
                    )
                    self._competition_date = datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    pass

    def _fetch_controls(self, base: str) -> None:
        root = _fetch_xml(f"{base}/meos?get=control")
        self._control_map.clear()
        for elem in root:
            if _strip_ns(elem.tag) == _TAG_CONTROL:
                ctrl_id = int(elem.get(_ATTR_ID, 0))
                self._control_map[ctrl_id] = elem.text or str(ctrl_id)

    def _fetch_class_radio(self, base: str) -> None:
        root = _fetch_xml(f"{base}/meos?get=class")
        self._radio_control_ids.clear()
        for elem in root:
            if _strip_ns(elem.tag) == _TAG_CLASS:
                radio_attr = elem.get(_TAG_RADIO, "")
                for leg in radio_attr.split(";"):
                    for rid in leg.split(","):
                        rid = rid.strip()
                        if rid:
                            self._radio_control_ids.add(int(rid))

    def _fetch_orgs(self, base: str) -> None:
        root = _fetch_xml(f"{base}/meos?get=organization")
        for elem in root:
            if _strip_ns(elem.tag) == _TAG_ORG:
                org_id = int(elem.get(_ATTR_ID, 0))
                nat = elem.get(_ATTR_NAT)
                if nat:
                    self._org_nat[org_id] = nat
        self.logger.debug("Loaded %d org nationalities", len(self._org_nat))

    def _fetch_teams(self, base: str) -> None:
        root = _fetch_xml(f"{base}/meos?get=team")
        for elem in root:
            if _strip_ns(elem.tag) == _TAG_TEAM:
                team_id = int(elem.get(_ATTR_ID, 0))
                base_elem = _find(elem, _TAG_BASE)
                r_elem = _find(elem, _TAG_RUNNERS)
                if base_elem is not None:
                    bib = base_elem.get(_ATTR_BIB)
                    if bib:
                        self._team_bib[team_id] = bib
                    org_id = base_elem.get(_ATTR_ORG)
                    if org_id:
                        self._team_org[team_id] = int(org_id)
                if r_elem is not None and r_elem.text:
                    legs = r_elem.text.split(";")
                    self._team_leg_count[team_id] = len(legs)
                    for leg_idx, leg_runners in enumerate(legs, start=1):
                        for cmp_id_str in leg_runners.split(","):
                            cmp_id_str = cmp_id_str.strip()
                            if cmp_id_str and cmp_id_str != _MOP_EMPTY_SLOT:
                                cmp_id = int(cmp_id_str)
                                info = self._cmp_info.setdefault(cmp_id, {})
                                info[_CMP_KEY_TEAM_ID] = team_id
                                info[_CMP_KEY_LEG] = leg_idx

    # -- Polling loop ----------------------------------------------------------

    def _poll_loop(self) -> None:
        self.logger.debug("Poll loop started")
        self._next_difference = _INITIAL_DIFF_TOKEN
        self._suppress_notifications = True
        self._prime_caches()
        while not self._stop_event.is_set():
            try:
                self._do_fetch()
            except Exception as e:
                self.logger.error("Error in poll loop: %s", e)
            self._poll_event.wait(timeout=self._fetch_interval)
            self._poll_event.clear()
        self.logger.debug("Poll loop stopped")

    def _do_fetch(self) -> None:
        if not self._url:
            return
        base = self._url.rstrip("/")
        try:
            root = _fetch_xml(f"{base}/meos?difference={self._next_difference}")
        except ET.ParseError:
            # Stale/invalid diff token - reset to zero and retry
            self.logger.warning(
                "Invalid diff response for token '%s', resetting to 'zero'",
                self._next_difference,
            )
            self._next_difference = _INITIAL_DIFF_TOKEN
            self._save_state()
            root = _fetch_xml(f"{base}/meos?difference={_INITIAL_DIFF_TOKEN}")
        root_tag = _strip_ns(root.tag)

        next_diff = root.get(_ATTR_NEXT_DIFFERENCE)
        if not next_diff:
            return

        is_complete = root_tag == _ROOT_TAG_COMPLETE
        if is_complete:
            self.logger.debug("Received MOPComplete, resetting caches")
            self._prime_caches()
            self._seen_radio.clear()
            suppress = self._suppress_notifications
            self._suppress_notifications = False
        else:
            suppress = False

        for elem in root:
            tag = _strip_ns(elem.tag)
            if tag == _TAG_TEAM:
                self._process_team_elem(elem)
            elif tag == _TAG_COMPETITOR:
                self._process_cmp_elem(elem, suppress=suppress)
            elif tag == _TAG_ORG:
                self._process_org_elem(elem)

        if next_diff != self._next_difference:
            self._next_difference = next_diff
            self._save_state()
        self.logger.debug("Diff fetched: type=%s, next=%s", root_tag, next_diff)

    def _process_org_elem(self, elem: ET.Element) -> None:
        org_id = int(elem.get(_ATTR_ID, 0))
        nat = elem.get(_ATTR_NAT)
        if nat:
            self._org_nat[org_id] = nat

    def _process_team_elem(self, elem: ET.Element) -> None:
        team_id = int(elem.get(_ATTR_ID, 0))
        base_elem = _find(elem, _TAG_BASE)
        r_elem = _find(elem, _TAG_RUNNERS)
        if base_elem is not None:
            bib = base_elem.get(_ATTR_BIB)
            if bib:
                self._team_bib[team_id] = bib
                self.logger.debug("Team %d bib updated: %s", team_id, bib)
            org_id = base_elem.get(_ATTR_ORG)
            if org_id:
                self._team_org[team_id] = int(org_id)
        if r_elem is not None and r_elem.text:
            legs = r_elem.text.split(";")
            self._team_leg_count[team_id] = len(legs)
            for leg_idx, leg_runners in enumerate(legs, start=1):
                for cmp_id_str in leg_runners.split(","):
                    cmp_id_str = cmp_id_str.strip()
                    if cmp_id_str and cmp_id_str != _MOP_EMPTY_SLOT:
                        cmp_id = int(cmp_id_str)
                        info = self._cmp_info.setdefault(cmp_id, {})
                        info[_CMP_KEY_TEAM_ID] = team_id
                        info[_CMP_KEY_LEG] = leg_idx

    def _process_cmp_elem(self, elem: ET.Element, suppress: bool = False) -> None:
        cmp_id = int(elem.get(_ATTR_ID, 0))
        card = elem.get(_CMP_KEY_CARD)
        if card and card != _MOP_EMPTY_SLOT:
            info = self._cmp_info.setdefault(cmp_id, {})
            if info.get(_CMP_KEY_CARD) != card:
                info[_CMP_KEY_CARD] = card
                self.logger.debug("Competitor %d card updated: %s", cmp_id, card)

        base_elem = _find(elem, _TAG_BASE)
        if base_elem is not None:
            st = base_elem.get(_CMP_KEY_START_TIME)
            if st:
                info = self._cmp_info.setdefault(cmp_id, {})
                info[_CMP_KEY_START_TIME] = int(st)
            nat = base_elem.get(_ATTR_NAT)
            if nat:
                info = self._cmp_info.setdefault(cmp_id, {})
                info[_CMP_KEY_NAT] = nat

        radio_elem = _find(elem, _TAG_RADIO)
        if radio_elem is None or not radio_elem.text:
            return

        for entry in radio_elem.text.split(";"):
            entry = entry.strip()
            if not entry:
                continue
            parts = entry.split(",")
            if len(parts) != 2:
                continue
            try:
                radio_id = int(parts[0])
                running_time = int(parts[1])
            except ValueError:
                continue

            seen = self._seen_radio.setdefault(cmp_id, set())
            if radio_id in seen:
                continue
            seen.add(radio_id)

            cmp_data = self._cmp_info.get(cmp_id, {})
            card_number = cmp_data.get(_CMP_KEY_CARD, "")
            team_id = cmp_data.get(_CMP_KEY_TEAM_ID)
            leg = cmp_data.get(_CMP_KEY_LEG)

            passed_time = None
            if self._zero_time and running_time > 0:
                st = cmp_data.get(_CMP_KEY_START_TIME, 0)
                if st and self._competition_date:
                    passed_time = (
                        self._competition_date
                        + timedelta(seconds=(st + running_time) / 10)
                    ).replace(microsecond=0)
                else:
                    passed_time = (
                        self._zero_time + timedelta(seconds=running_time / 10)
                    ).replace(microsecond=0)

            punch: Dict = {
                PUNCH_KEY_ID: f"{cmp_id}_{radio_id}",
                PUNCH_KEY_CONTROL_CODE: str(radio_id),
                PUNCH_KEY_CARD_NUMBER: card_number,
                PUNCH_KEY_PASSED_TIME: passed_time,
            }
            if team_id is not None and team_id in self._team_bib:
                bib = self._team_bib[team_id]
                punch[PUNCH_KEY_BIB_NUMBER] = bib
                if leg is not None:
                    punch[PUNCH_KEY_RELAY_LEG] = leg
                    max_leg = self._team_leg_count.get(team_id)
                    is_last_leg = max_leg is not None and leg >= max_leg
                    punch[PUNCH_KEY_IS_LAST_LEG] = is_last_leg
                    punch[PUNCH_KEY_COUNTRY] = self._resolve_next_leg_country(
                        team_id, leg, is_last_leg
                    )

            if not suppress:
                self._notify_listeners(punch)

    # -- UDP listener ----------------------------------------------------------

    _UDP_STRUCT_SIZE = 20  # 5 x int32: cmpId, runnerId, iHashType, status, time

    def _udp_loop(self) -> None:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", self._udp_port))
            sock.settimeout(0.2)
            self.logger.info("UDP listener bound on port %d", self._udp_port)
        except OSError as e:
            self.logger.warning(
                "UDP bind failed (port %d): %s - using interval polling only",
                self._udp_port,
                e,
            )
            return

        while not self._stop_event.is_set():
            try:
                data, addr = sock.recvfrom(256)
                if len(data) >= self._UDP_STRUCT_SIZE:
                    cmp_id, runner_id, i_hash_type, status, time_val = (
                        struct.unpack_from("<5i", data)
                    )
                    self.logger.debug(
                        "UDP from %s: cmpId=%d runnerId=%d iHashType=%d status=%d time=%d",
                        addr,
                        cmp_id,
                        runner_id,
                        i_hash_type,
                        status,
                        time_val,
                    )
                    self._poll_event.set()
            except socket.timeout:
                pass
            except Exception as e:
                self.logger.debug("UDP recv error: %s", e)
        sock.close()

    # -- Listeners -------------------------------------------------------------

    def register_meos_punch_listener(self, listener: MeosPunchListener) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def unregister_meos_punch_listener(self, listener: MeosPunchListener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify_listeners(self, punch: Dict) -> None:
        self.logger.debug("New punch: %s", punch)
        for listener in self._listeners:
            listener.meos_punch_received(punch)

    # -- Public API ------------------------------------------------------------

    def get_selector_controls(self) -> "SelectionResult | bool":
        if not self._url:
            return False
        return _select_controls(self._url)

    def lookup_card(self, card_number: str) -> Dict | None:
        # Check cache first
        for cmp_id, info in self._cmp_info.items():
            if info.get(_CMP_KEY_CARD) == card_number:
                team_id = info.get(_CMP_KEY_TEAM_ID)
                leg = info.get(_CMP_KEY_LEG)
                if team_id is not None and leg is not None:
                    bib = self._team_bib.get(team_id)
                    if bib:
                        result = self._build_lookup_result(team_id, bib, leg)
                        self.logger.debug(
                            "lookup_card(%s): cache hit -> %s", card_number, result
                        )
                        return result
        # Fall back to on-demand lookup
        http_result = self._lookup_card_http(card_number, retry=True)
        self.logger.debug(
            "lookup_card(%s): http fallback -> %s", card_number, http_result
        )
        return http_result

    def _build_lookup_result(self, team_id: int, bib: str, leg: int) -> Dict:
        max_leg = self._team_leg_count.get(team_id)
        is_last_leg = max_leg is not None and leg >= max_leg
        country = self._resolve_next_leg_country(team_id, leg, is_last_leg)
        return {
            PUNCH_KEY_BIB_NUMBER: bib,
            PUNCH_KEY_RELAY_LEG: leg,
            PUNCH_KEY_IS_LAST_LEG: is_last_leg,
            PUNCH_KEY_COUNTRY: country,
        }

    def _resolve_next_leg_country(
        self, team_id: int, current_leg: int, is_last_leg: bool
    ) -> str | None:
        """Resolve country for the next-leg runner.

        Fallback chain: next-leg runner nat -> team org nat -> None.
        """
        if not is_last_leg:
            next_leg = current_leg + 1
            # Find a runner on the next leg for this team
            for info in self._cmp_info.values():
                if (
                    info.get(_CMP_KEY_TEAM_ID) == team_id
                    and info.get(_CMP_KEY_LEG) == next_leg
                ):
                    nat = info.get(_CMP_KEY_NAT)
                    if nat:
                        self.logger.debug(
                            "Country for team %d leg %d: runner nat=%s",
                            team_id,
                            next_leg,
                            nat,
                        )
                        return nat
                    break  # Found next-leg runner but no nat, fall through

        # Fall back to team's org nationality
        org_id = self._team_org.get(team_id)
        if org_id is not None:
            nat = self._org_nat.get(org_id)
            if nat:
                self.logger.debug(
                    "Country for team %d: org %d nat=%s", team_id, org_id, nat
                )
                return nat
        return None

    def _lookup_card_http(self, card_number: str, retry: bool = True) -> Dict | None:
        if not self._url:
            return None
        try:
            base = self._url.rstrip("/")
            root = _fetch_xml(f"{base}/meos?lookup=competitor&card={card_number}")
            for elem in root:
                if _strip_ns(elem.tag) == _LOOKUP_TAG_COMPETITOR:
                    team_elem = _find(elem, _LOOKUP_TAG_TEAM)
                    leg_elem = _find(elem, _LOOKUP_TAG_LEG)
                    if team_elem is None or leg_elem is None:
                        return None
                    team_id = int(team_elem.get(_ATTR_ID, 0))
                    leg = int(leg_elem.text or 0)
                    bib = self._team_bib.get(team_id)
                    if bib is None and retry:
                        # Refresh team bib cache once
                        try:
                            self._fetch_teams(base)
                        except Exception:
                            pass
                        bib = self._team_bib.get(team_id)
                    if bib:
                        return self._build_lookup_result(team_id, bib, leg)
        except (HTTPError, URLError) as e:
            self.logger.error("lookup_card HTTP error: %s", e)
        except Exception as e:
            self.logger.error("lookup_card error: %s", e)
        return None

    def get_bib_range(self) -> tuple[int, int] | None:
        """Returns the min and max bib numbers from the cached team data."""
        if not self._team_bib:
            return None
        bibs: list[int] = []
        for bib_str in self._team_bib.values():
            try:
                bibs.append(int(bib_str))
            except ValueError, TypeError:
                continue
        if not bibs:
            return None
        return (min(bibs), max(bibs))

    # -- StateSaverMixin -------------------------------------------------------

    def register_tracking_listener(self, callback):
        pass

    def unregister_tracking_listener(self, callback):
        pass

    def get_runtime_value(self, option_definition):
        if option_definition is self.CONFIG_OPTION_NEXT_DIFFERENCE:
            return self._next_difference
        return None

    def set_runtime_value(self, option_definition, value: str):
        if option_definition is self.CONFIG_OPTION_NEXT_DIFFERENCE:
            self._next_difference = value if value else _INITIAL_DIFF_TOKEN
            self._save_state()
            self._seen_radio.clear()
            self._poll_event.set()

    def _save_state(self) -> None:
        self._save_value(self.CONFIG_OPTION_NEXT_DIFFERENCE, self._next_difference)
