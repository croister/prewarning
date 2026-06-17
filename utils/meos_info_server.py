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

_MODULE_LOGGER_NAME = "MeosInfoServer"

_MOP_NS = "http://www.melin.nu/mop"

MEOS_INFO_SERVER_RUNTIME_STATE = RuntimeStateGroup("meos_info_server.dat")


def _find(elem: ET.Element, tag: str) -> ET.Element | None:
    """Find child element, trying with MOP namespace first, then without."""
    result = elem.find(f"{{{_MOP_NS}}}{tag}")
    if result is None:
        result = elem.find(tag)
    return result


def _strip_ns(tag: str) -> str:
    return tag.partition("}")[2] if "}" in tag else tag


def _fetch_xml(url: str) -> ET.Element:
    req = Request(url)
    response = urlopen(req, timeout=10)
    data = response.read()
    return ET.fromstring(data)


def _verify_url(url: str) -> VerificationResult:
    try:
        root = _fetch_xml(f"{url.rstrip('/')}/meos?get=competition")
        if _strip_ns(root.tag) in ("MOPComplete", "MOPDiff"):
            competition = root.find(f"{{{_MOP_NS}}}competition")
            if competition is None:
                competition = root.find("competition")
            name = competition.text if competition is not None else "?"
            return VerificationResult(message=f"Connected. Competition: {name}")
        return VerificationResult(
            message="Unexpected response from MeOS.", status=False
        )
    except Exception as e:
        logging.getLogger(_MODULE_LOGGER_NAME).debug("_verify_url: %s", e)
        return VerificationResult(message=str(e), status=False)


def _select_controls(url: str) -> SelectionResult | bool:
    try:
        result = SelectionResult(
            caption="Control Codes",
            message="Select control codes for pre-warning:",
            selection_type=SelectionType.MULTIPLE,
        )
        base = url.rstrip("/")

        # Build control id → name map
        ctrl_root = _fetch_xml(f"{base}/meos?get=control")
        control_map: Dict[int, str] = {}
        for elem in ctrl_root:
            if _strip_ns(elem.tag) == "control":
                ctrl_id = int(elem.get("id", 0))
                control_map[ctrl_id] = elem.text or str(ctrl_id)

        # Collect radio control IDs from classes
        cls_root = _fetch_xml(f"{base}/meos?get=class")
        radio_ids: Set[int] = set()
        for elem in cls_root:
            if _strip_ns(elem.tag) == "cls":
                radio_attr = elem.get("radio", "")
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
        display_name="URL",
        value_type=str,
        description="Base URL of the MeOS Information Server, e.g. http://localhost:2009.",
        default_value="http://localhost:2009",
        mandatory=True,
        validator=is_http_or_https_url,
    )

    CONFIG_OPTION_FETCH_INTERVAL = ConfigOptionDefinition(
        name="FetchIntervalSeconds",
        display_name="Fetch Interval",
        value_type=int,
        description="Seconds between polls of the MeOS Information Server.",
        default_value=10,
        valid_values=list(range(1, 121)),
    )

    CONFIG_OPTION_USE_UDP = ConfigOptionDefinition(
        name="UseUDP",
        display_name="Use UDP",
        value_type=bool,
        description=(
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
        display_name="UDP Port",
        value_type=int,
        description=(
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
        display_name="Next Difference",
        value_type=str,
        description="MOP diff token, persisted across restarts.",
        default_value="zero",
    )

    MEOS_INFO_SERVER_CONFIG_SECTION = ConfigSectionDefinition(
        name=CONFIG_SECTION_MEOS,
        display_name="MeOS Information Server",
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
        self._fetch_interval: int = 10
        self._use_udp: bool = True
        self._udp_port: int = 21338
        self._next_difference: str = "zero"

        # Caches
        self._zero_time: datetime | None = None
        self._control_map: Dict[int, str] = {}
        self._radio_control_ids: Set[int] = set()
        self._team_bib: Dict[int, str] = {}
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
            self.CONFIG_OPTION_FETCH_INTERVAL.get_value(section) or 10
        )
        self._use_udp = self.CONFIG_OPTION_USE_UDP.get_value(section)
        if self._use_udp is None:
            self._use_udp = True
        self._udp_port = self.CONFIG_OPTION_UDP_PORT.get_value(section) or 21338

    def update(self) -> None:
        self._parse_config()

    def config_updated(self, section_names: List[str]) -> None:
        self.update()

    # ── Lifecycle ────────────────────────────────────────────────────────────

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
            self._poll_thread.join()
        if self._udp_thread and self._udp_thread.is_alive():
            self._udp_thread.join()
        self._poll_thread = None
        self._udp_thread = None

    def is_running(self) -> bool:
        return self._ref_count > 0

    def reset(self) -> None:
        self._next_difference = "zero"
        self._seen_radio.clear()
        self._save_state()
        self._poll_event.set()

    # ── Cache priming ─────────────────────────────────────────────────────────

    def _prime_caches(self) -> None:
        if not self._url:
            return
        base = self._url.rstrip("/")
        try:
            self._fetch_competition(base)
        except Exception as e:
            self.logger.warning("Failed to prime competition cache: %s", e)
        try:
            self._fetch_controls(base)
        except Exception as e:
            self.logger.warning("Failed to prime control cache: %s", e)
        try:
            self._fetch_class_radio(base)
        except Exception as e:
            self.logger.warning("Failed to prime class cache: %s", e)
        try:
            self._fetch_teams(base)
        except Exception as e:
            self.logger.warning("Failed to prime team cache: %s", e)

    def _fetch_competition(self, base: str) -> None:
        root = _fetch_xml(f"{base}/meos?get=competition")
        for elem in root:
            if _strip_ns(elem.tag) == "competition":
                date_str = elem.get("date", "")
                zero_str = elem.get("zerotime", "00:00:00")
                try:
                    self._zero_time = datetime.strptime(
                        f"{date_str} {zero_str}", "%Y-%m-%d %H:%M:%S"
                    )
                except ValueError:
                    pass

    def _fetch_controls(self, base: str) -> None:
        root = _fetch_xml(f"{base}/meos?get=control")
        self._control_map.clear()
        for elem in root:
            if _strip_ns(elem.tag) == "control":
                ctrl_id = int(elem.get("id", 0))
                self._control_map[ctrl_id] = elem.text or str(ctrl_id)

    def _fetch_class_radio(self, base: str) -> None:
        root = _fetch_xml(f"{base}/meos?get=class")
        self._radio_control_ids.clear()
        for elem in root:
            if _strip_ns(elem.tag) == "cls":
                radio_attr = elem.get("radio", "")
                for leg in radio_attr.split(";"):
                    for rid in leg.split(","):
                        rid = rid.strip()
                        if rid:
                            self._radio_control_ids.add(int(rid))

    def _fetch_teams(self, base: str) -> None:
        root = _fetch_xml(f"{base}/meos?get=team")
        for elem in root:
            if _strip_ns(elem.tag) == "tm":
                team_id = int(elem.get("id", 0))
                base_elem = _find(elem, "base")
                r_elem = _find(elem, "r")
                if base_elem is not None:
                    bib = base_elem.get("bib")
                    if bib:
                        self._team_bib[team_id] = bib
                if r_elem is not None and r_elem.text:
                    for leg_idx, cmp_id_str in enumerate(
                        r_elem.text.split(";"), start=1
                    ):
                        cmp_id_str = cmp_id_str.strip()
                        if cmp_id_str and cmp_id_str != "0":
                            cmp_id = int(cmp_id_str)
                            info = self._cmp_info.setdefault(cmp_id, {})
                            info["team_id"] = team_id
                            info["leg"] = leg_idx

    # ── Polling loop ──────────────────────────────────────────────────────────

    def _poll_loop(self) -> None:
        self.logger.debug("Poll loop started")
        self._next_difference = "zero"
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
            # Stale/invalid diff token — reset to zero and retry
            self.logger.warning(
                "Invalid diff response for token '%s', resetting to 'zero'",
                self._next_difference,
            )
            self._next_difference = "zero"
            self._save_state()
            root = _fetch_xml(f"{base}/meos?difference=zero")
        root_tag = _strip_ns(root.tag)

        next_diff = root.get("nextdifference")
        if not next_diff:
            return

        is_complete = root_tag == "MOPComplete"
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
            if tag == "tm":
                self._process_team_elem(elem)
            elif tag == "cmp":
                self._process_cmp_elem(elem, suppress=suppress)

        if next_diff != self._next_difference:
            self._next_difference = next_diff
            self._save_state()
        self.logger.debug("Diff fetched: type=%s, next=%s", root_tag, next_diff)

    def _process_team_elem(self, elem: ET.Element) -> None:
        team_id = int(elem.get("id", 0))
        base_elem = _find(elem, "base")
        r_elem = _find(elem, "r")
        if base_elem is not None:
            bib = base_elem.get("bib")
            if bib:
                self._team_bib[team_id] = bib
                self.logger.debug("Team %d bib updated: %s", team_id, bib)
        if r_elem is not None and r_elem.text:
            for leg_idx, cmp_id_str in enumerate(r_elem.text.split(";"), start=1):
                cmp_id_str = cmp_id_str.strip()
                if cmp_id_str and cmp_id_str != "0":
                    cmp_id = int(cmp_id_str)
                    info = self._cmp_info.setdefault(cmp_id, {})
                    info["team_id"] = team_id
                    info["leg"] = leg_idx

    def _process_cmp_elem(self, elem: ET.Element, suppress: bool = False) -> None:
        cmp_id = int(elem.get("id", 0))
        card = elem.get("card")
        if card and card != "0":
            info = self._cmp_info.setdefault(cmp_id, {})
            if info.get("card") != card:
                info["card"] = card
                self.logger.debug("Competitor %d card updated: %s", cmp_id, card)

        radio_elem = _find(elem, "radio")
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
            card_number = cmp_data.get("card", "")
            team_id = cmp_data.get("team_id")
            leg = cmp_data.get("leg")

            passed_time = None
            if self._zero_time and running_time > 0:
                passed_time = (
                    self._zero_time + timedelta(seconds=running_time / 10)
                ).replace(microsecond=0)

            punch: Dict = {
                "id": f"{cmp_id}_{radio_id}",
                "controlCode": str(radio_id),
                "cardNumber": card_number,
                "passedTime": passed_time,
            }
            if team_id is not None and team_id in self._team_bib:
                punch["bibNumber"] = self._team_bib[team_id]
            if leg is not None:
                punch["relayLeg"] = leg

            if not suppress:
                self._notify_listeners(punch)

    # ── UDP listener ──────────────────────────────────────────────────────────

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
                "UDP bind failed (port %d): %s — using interval polling only",
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

    # ── Listeners ─────────────────────────────────────────────────────────────

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

    # ── Public API ────────────────────────────────────────────────────────────

    def get_selector_controls(self) -> "SelectionResult | bool":
        if not self._url:
            return False
        return _select_controls(self._url)

    def lookup_card(self, card_number: str) -> Dict | None:
        # Check cache first
        for cmp_id, info in self._cmp_info.items():
            if info.get("card") == card_number:
                team_id = info.get("team_id")
                leg = info.get("leg")
                if team_id is not None and leg is not None:
                    bib = self._team_bib.get(team_id)
                    if bib:
                        return {"bibNumber": bib, "relayLeg": leg}
        # Fall back to on-demand lookup
        return self._lookup_card_http(card_number, retry=True)

    def _lookup_card_http(self, card_number: str, retry: bool = True) -> Dict | None:
        if not self._url:
            return None
        try:
            base = self._url.rstrip("/")
            root = _fetch_xml(f"{base}/meos?lookup=competitor&card={card_number}")
            for elem in root:
                if _strip_ns(elem.tag) == "Competitor":
                    team_elem = _find(elem, "Team")
                    leg_elem = _find(elem, "Leg")
                    if team_elem is None or leg_elem is None:
                        return None
                    team_id = int(team_elem.get("id", 0))
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
                        return {"bibNumber": bib, "relayLeg": leg}
        except (HTTPError, URLError) as e:
            self.logger.error("lookup_card HTTP error: %s", e)
        except Exception as e:
            self.logger.error("lookup_card error: %s", e)
        return None

    # ── StateSaverMixin ───────────────────────────────────────────────────────

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
            self._next_difference = value if value else "zero"
            self._save_state()
            self._seen_radio.clear()
            self._poll_event.set()

    def _save_state(self) -> None:
        self._save_value(self.CONFIG_OPTION_NEXT_DIFFERENCE, self._next_difference)
