# -*- coding: utf-8 -*-

import logging
from datetime import date, datetime
from threading import Event, Thread
from typing import List, Dict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from imurl import URL

from utils.state_saver import StateSaverMixin
from utils.config import ConfigSectionDefinition, ConfigOptionDefinition, Config
from utils.config_definitions import (
    ConfigSectionEnableType,
    ConfigVerifierDefinition,
    ConfigSectionOptionDefinition,
    VerificationResult,
    RuntimeStateGroup,
    RuntimeStateOptionDefinition,
)
from utils.constants import (
    FETCH_INTERVAL_VALID_VALUES,
    PUNCH_KEY_CARD_NUMBER,
    PUNCH_KEY_CONTROL_CODE,
    PUNCH_KEY_ID,
    PUNCH_KEY_PASSED_TIME,
)
from validators.datetime_validators import is_date, is_time
from validators.number_validators import is_not_negative_int
from validators.regex_validators import is_control_ids
from validators.url_validators import is_http_or_https_url
from ._base import _PunchSourceBase


_MODULE_LOGGER_NAME = "PunchSourceOlresultatSe"

PUNCH_SOURCE_OL_RESULTAT_SE_RUNTIME_STATE = RuntimeStateGroup("ps_olresultatse.dat")

DEFAULT_RESPONSE_ENCODING = "utf-8"


PUNCH_KEYS = (
    PUNCH_KEY_ID,
    PUNCH_KEY_CONTROL_CODE,
    PUNCH_KEY_CARD_NUMBER,
    PUNCH_KEY_PASSED_TIME,
)


def _normalize_passed_time(raw: str) -> datetime:
    try:
        return datetime.fromisoformat(raw)
    except ValueError, TypeError:
        pass
    return datetime.now()


def _fetch_punches(
    url_str: str,
    unit_id: str,
    last_id: int,
    from_date: str | None = None,
    from_time: str | None = None,
    control_codes: List[str] | None = None,
):
    if url_str is None or len(url_str) == 0:
        raise ValueError("URL must be configured.")
    if unit_id is None or len(unit_id) == 0:
        raise ValueError("Competition or Device Id must be configured.")

    url = URL(url_str)

    url = url.set_query("unitId", unit_id)
    url = url.set_query("lastId", str(last_id))
    if from_date is not None:
        url = url.set_query("date", from_date)
    if from_time is not None:
        url = url.set_query("time", from_time)

    logging.getLogger(_MODULE_LOGGER_NAME).debug('_fetch_punches url: "%s"', url)

    req = Request(url.url)
    try:
        response = urlopen(req)
        response_encoding = response.info().get_content_charset()
        if response_encoding is None:
            response_encoding = DEFAULT_RESPONSE_ENCODING
        data = response.read().decode(response_encoding)
        splitlines = data.splitlines()
        punches = list()
        if splitlines:
            logging.getLogger(_MODULE_LOGGER_NAME).debug(
                '_fetch_punches data: "%s"', data
            )
            for line in splitlines:
                punch_dict = dict(zip(PUNCH_KEYS, line.split(";")))
                punch_dict[PUNCH_KEY_PASSED_TIME] = _normalize_passed_time(
                    punch_dict[PUNCH_KEY_PASSED_TIME]
                )
                if (
                    control_codes is None
                    or punch_dict[PUNCH_KEY_CONTROL_CODE] in control_codes
                ):
                    punches.append(punch_dict)
        logging.getLogger(_MODULE_LOGGER_NAME).debug(
            '_fetch_punches punches: %d "%s"', len(punches), punches
        )
        return punches
    except HTTPError as e:
        logging.getLogger(_MODULE_LOGGER_NAME).error(
            "_fetch_punches: The server could not fulfill the request. Error code: %s",
            e.code,
        )
        raise
    except URLError as e:
        logging.getLogger(_MODULE_LOGGER_NAME).error(
            "_fetch_punches: We failed to reach a server. Reason: %s", e.reason
        )
        raise
    except Exception as e:
        logging.getLogger(_MODULE_LOGGER_NAME).error(
            "_fetch_punches: Unknown Exception. %s", e
        )
        raise


def _verify_last_id(url_str: str, unit_id: str, last_id: int):
    try:
        punches = _fetch_punches(url_str=url_str, unit_id=unit_id, last_id=last_id)

        if len(punches) == 0:
            return VerificationResult(message="No Punches received.")

        return VerificationResult(message=f"{len(punches)} Punches received.")
    except Exception as e:
        logging.getLogger(_MODULE_LOGGER_NAME).debug("_verify_last_id: %s", e)
        return VerificationResult(message=str(e), status=False)


def _verify_date_time(
    url_str: str, unit_id: str, last_id: int, from_date: str, from_time: str
):
    try:
        punches = _fetch_punches(
            url_str=url_str,
            unit_id=unit_id,
            last_id=last_id,
            from_date=from_date,
            from_time=from_time,
        )

        if len(punches) == 0:
            return VerificationResult(message="No Punches received.")

        return VerificationResult(message=f"{len(punches)} Punches received.")
    except Exception as e:
        logging.getLogger(_MODULE_LOGGER_NAME).debug("_verify_date_time: %s", e)
        return VerificationResult(message=str(e), status=False)


def _verify_control_codes(
    url_str: str,
    unit_id: str,
    last_id: int,
    from_date: str,
    from_time: str,
    control_codes: List[str],
) -> VerificationResult:
    try:
        if control_codes is None:
            return VerificationResult(
                message="Control Codes must be configured.", status=False
            )

        punches = _fetch_punches(
            url_str=url_str,
            unit_id=unit_id,
            last_id=last_id,
            from_date=from_date,
            from_time=from_time,
            control_codes=control_codes,
        )

        if len(punches) == 0:
            return VerificationResult(message="No Punches received.")

        return VerificationResult(message=f"{len(punches)} Punches received.")
    except Exception as e:
        logging.getLogger(_MODULE_LOGGER_NAME).debug("_verify_control_codes: %s", e)
        return VerificationResult(message=str(e), status=False)


class PunchSourceOlresultatSe(StateSaverMixin, _PunchSourceBase):
    """
    A Punch Source that reads the Punches from olresultat.se.
    """

    name = __qualname__

    display_name = "OLResultat.se Punch Source"

    description = (
        "Fetches electronic punches from the site "
        '<a href="https://roc.olresultat.se/">roc.olresultat.se</a>. '
        "These punches have been sent to the site using a Raspberry Pi running the ROC software or an "
        'Android device running the <a href="http://www.joja.se/">SI-Droid ROC</a> app.'
    )

    CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_URL = ConfigOptionDefinition(
        name="PunchSourceUrl",
        display_name="URL",
        value_type=str,
        description="The URL to the resource that provides the Punches.",
        default_value="http://roc.olresultat.se/getpunches.asp",
        validator=is_http_or_https_url,
    )

    CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_COMPETITION_ID = ConfigOptionDefinition(
        name="CompetitionId",
        display_name="Competition or Device Id",
        value_type=str,
        description="The Competition Id or Device Id to fetch Punches from.",
        mandatory=True,
    )

    CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_LAST_RECEIVED_PUNCH_ID = RuntimeStateOptionDefinition(
        runtime_state_group=PUNCH_SOURCE_OL_RESULTAT_SE_RUNTIME_STATE,
        name="LastReceivedPunchId",
        display_name="Last Received Punch Id",
        value_type=int,
        description="The Id of the last received Punch, used to only fetch Punches with a higher Id.",
        default_value=0,
        validator=is_not_negative_int,
    )

    CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_FROM_DATE = ConfigOptionDefinition(
        name="FromDate",
        display_name="From Date",
        value_type=str,
        description="The date to fetch Punches from, used to only fetch newer Punches. ISO 8601 format (YYYY-MM-DD)",
        default_value=date.today().isoformat(),
        validator=is_date,
    )

    CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_FROM_TIME = ConfigOptionDefinition(
        name="FromTime",
        display_name="From Time",
        value_type=str,
        description="The time to fetch Punches from, used to only fetch newer Punches. ISO 8601 format (hh:mm:ss)",
        default_value="00:00:00",
        # default_value=time.isoformat(timespec='seconds'),
        validator=is_time,
    )

    CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_FETCH_INTERVAL_SECONDS = (
        ConfigOptionDefinition(
            name="FetchIntervalSeconds",
            display_name="Fetch Interval",
            value_type=int,
            description="The number of seconds between calls to the Punch Source URL.",
            default_value=10,
            valid_values=FETCH_INTERVAL_VALID_VALUES,
        )
    )

    CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_CONTROL_CODES = ConfigOptionDefinition(
        name="ControlCodes",
        display_name="Control Codes",
        value_type=str,
        description="The Control Codes to use for Pre-Warning, separated by space.",
        mandatory=True,
        validator=is_control_ids,
    )

    PUNCH_SOURCE_OL_RESULTAT_SE_CONFIG_SECTION_DEFINITION = ConfigSectionDefinition(
        name=name,
        display_name=display_name,
        option_definitions=[
            CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_URL,
            CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_COMPETITION_ID,
            CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_LAST_RECEIVED_PUNCH_ID,
            CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_FROM_DATE,
            CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_FROM_TIME,
            CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_FETCH_INTERVAL_SECONDS,
            CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_CONTROL_CODES,
        ],
        enable_type=ConfigSectionEnableType.IF_ENABLED,
        sort_key_prefix=30,
    )

    PUNCH_SOURCE_OL_RESULTAT_SE_LAST_RECEIVED_PUNCH_ID_VERIFIER = ConfigVerifierDefinition(
        function=_verify_last_id,
        parameters=[
            ConfigSectionOptionDefinition(
                section_name=name,
                option_definition=CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_URL,
            ),
            ConfigSectionOptionDefinition(
                section_name=name,
                option_definition=CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_COMPETITION_ID,
            ),
            ConfigSectionOptionDefinition(
                section_name=name,
                option_definition=CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_LAST_RECEIVED_PUNCH_ID,
            ),
        ],
        message="The request failed, check the configuration options for this Punch Source.",
    )

    CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_LAST_RECEIVED_PUNCH_ID.set_verifier(
        PUNCH_SOURCE_OL_RESULTAT_SE_LAST_RECEIVED_PUNCH_ID_VERIFIER
    )

    PUNCH_SOURCE_OL_RESULTAT_SE_FROM_TIME_VERIFIER = ConfigVerifierDefinition(
        function=_verify_date_time,
        parameters=[
            ConfigSectionOptionDefinition(
                section_name=name,
                option_definition=CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_URL,
            ),
            ConfigSectionOptionDefinition(
                section_name=name,
                option_definition=CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_COMPETITION_ID,
            ),
            ConfigSectionOptionDefinition(
                section_name=name,
                option_definition=CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_LAST_RECEIVED_PUNCH_ID,
            ),
            ConfigSectionOptionDefinition(
                section_name=name,
                option_definition=CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_FROM_DATE,
            ),
            ConfigSectionOptionDefinition(
                section_name=name,
                option_definition=CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_FROM_TIME,
            ),
        ],
        message="The request failed, check the configuration options for this Punch Source.",
    )

    CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_FROM_TIME.set_verifier(
        PUNCH_SOURCE_OL_RESULTAT_SE_FROM_TIME_VERIFIER
    )

    PUNCH_SOURCE_OL_RESULTAT_SE_CONTROL_CODES_VERIFIER = ConfigVerifierDefinition(
        function=_verify_control_codes,
        parameters=[
            ConfigSectionOptionDefinition(
                section_name=name,
                option_definition=CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_URL,
            ),
            ConfigSectionOptionDefinition(
                section_name=name,
                option_definition=CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_COMPETITION_ID,
            ),
            ConfigSectionOptionDefinition(
                section_name=name,
                option_definition=CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_LAST_RECEIVED_PUNCH_ID,
            ),
            ConfigSectionOptionDefinition(
                section_name=name,
                option_definition=CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_FROM_DATE,
            ),
            ConfigSectionOptionDefinition(
                section_name=name,
                option_definition=CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_FROM_TIME,
            ),
            ConfigSectionOptionDefinition(
                section_name=name,
                option_definition=CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_CONTROL_CODES,
            ),
        ],
        message="The request failed, check the other configuration options for this Punch Source.",
    )

    CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_CONTROL_CODES.set_verifier(
        PUNCH_SOURCE_OL_RESULTAT_SE_CONTROL_CODES_VERIFIER
    )

    Config.register_config_section_definition(
        PUNCH_SOURCE_OL_RESULTAT_SE_CONFIG_SECTION_DEFINITION
    )

    @classmethod
    def config_section_definition(cls) -> ConfigSectionDefinition:
        return cls.PUNCH_SOURCE_OL_RESULTAT_SE_CONFIG_SECTION_DEFINITION

    def __repr__(self) -> str:
        return (
            f"PunchSourceOlResultatSe(running={self.is_running()},"
            f" url={self.url},"
            f" competition_id={self.competition_id},"
            f" last_received_punch_id={self.last_received_punch_id},"
            f" from_date={self.from_date},"
            f" from_time={self.from_time},"
            f" fetch_interval_seconds={self.fetch_interval_seconds},"
            f" control_codes={self.control_codes})"
        )

    def __str__(self) -> str:
        return repr(self)

    def __init__(self):
        _PunchSourceBase.__init__(self)
        StateSaverMixin.__init__(
            self, self.name, [PUNCH_SOURCE_OL_RESULTAT_SE_RUNTIME_STATE]
        )

        if _MODULE_LOGGER_NAME != self.__class__.__name__:
            raise ValueError(
                "_MODULE_LOGGER_NAME not correct: {} vs {}".format(
                    _MODULE_LOGGER_NAME, self.__class__.__name__
                )
            )

        self.logger = logging.getLogger(self.__class__.__name__)

        self.url = None
        self.competition_id = None
        self.last_received_punch_id = 0
        self.from_date = None
        self.from_time = None
        self.fetch_interval_seconds = None
        self.control_codes = list()

        self.response_encoding = "utf-8"
        self._stop_event = Event()
        self._stop_event.set()
        self.punch_fetcher = None

        self.logger.debug(self)

        self.update()

        if self._data_read(
            self.CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_LAST_RECEIVED_PUNCH_ID
        ):
            self.last_received_punch_id = self._get_value(
                self.CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_LAST_RECEIVED_PUNCH_ID
            )
            self.logger.info(
                "Read %s value from state file: %s",
                self.CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_LAST_RECEIVED_PUNCH_ID.name,
                self.last_received_punch_id,
            )

        self._notify_tracking_listeners()

    def __del__(self):
        self.stop()

    def start(self):
        self._stop_event.clear()
        self.punch_fetcher = Thread(
            target=self._fetch_punches,
            daemon=True,
            name="PunchFetcherOlresultatSeThread",
        )
        self.punch_fetcher.start()

    def stop(self):
        self._stop_event.set()
        if self.punch_fetcher is not None and self.punch_fetcher.is_alive():
            self.punch_fetcher.join()

    def is_running(self) -> bool:
        return not self._stop_event.is_set()

    def config_updated(self, section_names: List[str]):
        self.update()

    def update(self):
        self._parse_config()

    def _parse_config(self):
        config_section = Config().get_section(self.name)

        self.url = self.CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_URL.get_value(
            config_section
        )
        self.competition_id = (
            self.CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_COMPETITION_ID.get_value(
                config_section
            )
        )

        self.from_date = (
            self.CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_FROM_DATE.get_value(
                config_section
            )
        )
        self.from_time = (
            self.CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_FROM_TIME.get_value(
                config_section
            )
        )
        self.fetch_interval_seconds = self.CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_FETCH_INTERVAL_SECONDS.get_value(
            config_section
        )
        new_control_codes = (
            self.CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_CONTROL_CODES.get_value(
                config_section
            )
        )
        self.control_codes.clear()
        if new_control_codes is not None:
            self.control_codes.extend(new_control_codes.split())

    def _get_tracking_state(self) -> Dict[str, str]:
        return {
            self.CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_LAST_RECEIVED_PUNCH_ID.name: str(
                self.last_received_punch_id
            ),
        }

    def get_runtime_value(self, option_definition: ConfigOptionDefinition):
        if (
            option_definition
            is self.CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_LAST_RECEIVED_PUNCH_ID
        ):
            return self.last_received_punch_id
        return None

    def set_runtime_value(self, option_definition: ConfigOptionDefinition, value: str):
        if (
            option_definition
            is self.CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_LAST_RECEIVED_PUNCH_ID
        ):
            self.last_received_punch_id = int(value) if value else 0
        else:
            return
        self._save_state()

    def reset_tracking(self):
        self.last_received_punch_id = 0
        self._save_state()

    def _save_state(self):
        self.logger.debug("_save_state: %s", self.last_received_punch_id)

        self._save_value(
            self.CONFIG_OPTION_PUNCH_SOURCE_OL_RESULTAT_SE_LAST_RECEIVED_PUNCH_ID,
            self.last_received_punch_id,
        )

        self._notify_tracking_listeners()

    def _fetch_punches(self):
        self.logger.debug("Started")
        while not self._stop_event.is_set():
            url = URL(self.url)

            url = url.set_query("unitId", self.competition_id)
            url = url.set_query("lastId", str(self.last_received_punch_id))
            if self.from_date is not None:
                url = url.set_query("date", self.from_date)
            if self.from_time is not None:
                url = url.set_query("time", self.from_time)

            self.logger.debug('_fetch_punches url: "%s"', url)

            req = Request(url.url)
            try:
                response = urlopen(req)
                response_encoding = response.info().get_content_charset()
                if response_encoding is None:
                    response_encoding = self.response_encoding
                data = response.read().decode(response_encoding)
                splitlines = data.splitlines()
                if splitlines:
                    self.logger.debug(data)
                    for line in splitlines:
                        punch_dict = dict(zip(PUNCH_KEYS, line.split(";")))
                        punch_dict[PUNCH_KEY_PASSED_TIME] = _normalize_passed_time(
                            punch_dict[PUNCH_KEY_PASSED_TIME]
                        )
                        self.logger.debug(punch_dict)
                        if punch_dict[PUNCH_KEY_CONTROL_CODE] in self.control_codes:
                            self._notify_punch_listeners(punch_dict)
                        self.last_received_punch_id = int(punch_dict[PUNCH_KEY_ID])
                        self.logger.debug(self.last_received_punch_id)
                    self._save_state()
            except HTTPError as e:
                self.logger.error(
                    "The server could not fulfill the request. Error code: %s", e.code
                )
            except URLError as e:
                self.logger.error("We failed to reach a server. Reason: %s", e.reason)
            except Exception as e:
                self.logger.error("Unexpected error fetching punches: %s", e)

            self._stop_event.wait(timeout=self.fetch_interval_seconds)
        self.logger.debug("Stopped")
        Config().write()
