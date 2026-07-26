import logging
from threading import Event, Thread
from typing import Any

from pymysql import OperationalError

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
from utils.constants import FETCH_INTERVAL_VALID_VALUES, PUNCH_KEY_ID
from utils.i18n import N_
from utils.ola_mysql import (
    _KEY_CLASS_COUNT,
    _KEY_CLASS_NAMES,
    _KEY_CONTROL_ID,
    _KEY_CONTROL_NAME,
    _KEY_PUNCHING_CODES,
    _KEY_SPLIT_TIME_CONTROL_NAME,
    OlaMySql,
    are_valid_event_race_control_ids,
    connect,
    get_event_race_split_time_controls,
    get_event_race_split_times,
    get_ola_db_version,
    is_relay_event,
)
from utils.state_saver import StateSaverMixin
from validators.datetime_validators import is_timestamp
from validators.regex_validators import is_control_ids, is_punch_id

from ._base import _PunchSourceBase

_MODULE_LOGGER_NAME = "PunchSourceOlaMySql"

PUNCH_SOURCE_OLA_MYSQL_RUNTIME_STATE = RuntimeStateGroup("ps_ola_mysql.dat")

# OLA split time result dict key
_SPLIT_TIME_KEY_MODIFY_DATE = "modifyDate"


def _select_control_ids(
    host: str,
    user: str,
    password: str,
    database: str,
    event_id: int,
    event_race_id: int,
):
    try:
        connection = connect(host, user, password, database)
        with connection:
            result = SelectionResult(
                caption="Control Ids",
                message="Select Control Ids:",
                selection_type=SelectionType.MULTIPLE,
            )
            ola_db_version = get_ola_db_version(connection)
            is_relay = is_relay_event(connection, event_id=event_id)
            control_ids = get_event_race_split_time_controls(
                connection,
                ola_db_version=ola_db_version,
                is_relay=is_relay,
                event_race_id=event_race_id,
            )
            for control_id in control_ids:
                result.add_value(
                    SelectionData(
                        control_id[_KEY_CONTROL_ID],
                        _split_time_control_description(control_id),
                    )
                )
            return result
    except Exception as e:  # noqa: BLE001 - broad catch intentional; libraries raise diverse exceptions
        logging.getLogger(_MODULE_LOGGER_NAME).debug("_select_control_ids: %s", e)
        return False


def _split_time_control_name(control_id: dict[str, Any]) -> str:
    split_time_control_name = control_id[_KEY_SPLIT_TIME_CONTROL_NAME]
    if split_time_control_name is None or len(split_time_control_name) == 0:
        split_time_control_name = control_id[_KEY_CONTROL_NAME]
    if split_time_control_name is None or len(split_time_control_name) == 0:
        split_time_control_name = ""

    return split_time_control_name


def _split_time_control_description(control_id: dict[str, Any]) -> str:
    split_time_control_name = _split_time_control_name(control_id)

    class_names = control_id[_KEY_CLASS_NAMES]
    if class_names is None:
        class_names = ""
    if len(class_names) > 50:
        class_names = f"{class_names:.46} ..."

    description = f"{control_id[_KEY_CONTROL_ID]}: {split_time_control_name} ({control_id[_KEY_PUNCHING_CODES]}) used by {control_id[_KEY_CLASS_COUNT]} classes ({class_names})"
    return description


def _verify_control_ids(
    host: str,
    user: str,
    password: str,
    database: str,
    event_id: int,
    event_race_id: int,
    control_ids: str,
) -> bool:
    try:
        if control_ids is None or len(control_ids) == 0:
            control_id_ints = []
        else:
            control_id_ints = [int(control_id) for control_id in control_ids.split()]

        connection = connect(host, user, password, database)
        with connection:
            ola_db_version = get_ola_db_version(connection)
            is_relay = is_relay_event(connection, event_id=event_id)
            return are_valid_event_race_control_ids(
                connection,
                ola_db_version=ola_db_version,
                is_relay=is_relay,
                event_race_id=event_race_id,
                control_ids=control_id_ints,
            )
    except Exception as e:  # noqa: BLE001 - broad catch intentional; libraries raise diverse exceptions
        logging.getLogger(_MODULE_LOGGER_NAME).debug("_select_control_ids: %s", e)
        return False


def _verify_fetch(
    host: str,
    user: str,
    password: str,
    database: str,
    event_id: int,
    event_race_id: int,
    control_ids: str,
    last_modify_time: str | None,
    last_received_punch_id: str | None = None,
) -> VerificationResult:
    try:
        if control_ids is None or len(control_ids) == 0:
            control_id_ints = []
        else:
            control_id_ints = [int(control_id) for control_id in control_ids.split()]

        connection = connect(host, user, password, database)
        with connection:
            ola_db_version = get_ola_db_version(connection)
            event_split_times = get_event_race_split_times(
                connection,
                ola_db_version=ola_db_version,
                event_id=event_id,
                event_race_id=event_race_id,
                control_ids=control_id_ints,
                last_modify_time=last_modify_time,
            )

            if len(event_split_times) == 0:
                return VerificationResult(message="No Punches received")

            if last_received_punch_id is not None:
                split_time_ids = [
                    split_time[PUNCH_KEY_ID] for split_time in event_split_times
                ]
                if last_received_punch_id in split_time_ids:
                    return VerificationResult(
                        message=f"{len(event_split_times)} Punches received and 1 ignored."
                    )

            return VerificationResult(
                message=f"{len(event_split_times)} Punches received."
            )
    except Exception as e:  # noqa: BLE001 - broad catch intentional; libraries raise diverse exceptions
        logging.getLogger(_MODULE_LOGGER_NAME).debug("_verify_fetch: %s", e)
        return VerificationResult(message=str(e), status=False)


class PunchSourceOlaMySql(StateSaverMixin, _PunchSourceBase):
    """
    A Punch Source that reads the Punches from the OLA MySQL Database.
    """

    name = __qualname__

    display_name = N_("OLA MySQL Punch Source")

    description = N_(
        "Fetches electronic punches from the MySQL database used by the "
        '<a href="https://www.svenskorientering.se/Arrangera/itochtavlings-administration/'
        'OLAtidtagnings-program/">OLA event organizing software</a>. '
        "These punches have been fetched or received using one of the built-in methods in OLA. "
        "OLA must be using MySQL as the database engine, the built-in database is not supported."
    )

    CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_CONTROL_IDS = ConfigOptionDefinition(
        name="ControlIDs",
        display_name=N_("Control Ids"),
        value_type=str,
        description=N_(
            "The Control IDs to use for Pre-Warning, separated by space."
            " Use the Control Code (Kodsiffra) from OLA, NOT the punching units (Elektronisk stämplingskod)."
        ),
        mandatory=True,
        validator=is_control_ids,
    )

    CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_FETCH_INTERVAL_SECONDS = (
        ConfigOptionDefinition(
            name="FetchIntervalSeconds",
            display_name=N_("Fetch Interval"),
            value_type=int,
            description=N_(
                "The number of seconds between calls to the OLA MySQL database."
            ),
            default_value=10,
            valid_values=FETCH_INTERVAL_VALID_VALUES,
        )
    )

    CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_MODIFIED_TIME = RuntimeStateOptionDefinition(
        runtime_state_group=PUNCH_SOURCE_OLA_MYSQL_RUNTIME_STATE,
        name="LastModifiedTime",
        display_name=N_("Last Modified Time"),
        value_type=str,
        description=N_(
            "The Modified Time of the last retrieved Punch, used to only fetch Punches that are newer. "
            'On the format of "YYYY-MM-DD hh:mm:ss.fff".'
        ),
        default_value="",
        validator=is_timestamp,
    )

    CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_RECEIVED_PUNCH_ID = RuntimeStateOptionDefinition(
        runtime_state_group=PUNCH_SOURCE_OLA_MYSQL_RUNTIME_STATE,
        name="LastReceivedPunchId",
        display_name=N_("Last Received Punch Id"),
        value_type=str,
        description=N_(
            "The Id of the last received Punch, used to not process it again. "
            "On the format of `resultRaceIndividualNumber`_`passedCount`_`timingControl` "
            'from the table `SplitTimes`, example "1_1_1".'
        ),
        default_value="",
        validator=is_punch_id,
    )

    PUNCH_SOURCE_OLA_MYSQL_CONFIG_SECTION_DEFINITION = ConfigSectionDefinition(
        name=name,
        display_name=display_name,
        option_definitions=[
            CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_CONTROL_IDS,
            CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_FETCH_INTERVAL_SECONDS,
            CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_MODIFIED_TIME,
            CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_RECEIVED_PUNCH_ID,
        ],
        enable_type=ConfigSectionEnableType.IF_ENABLED,
        requires=[
            OlaMySql.config_section_definition(),
        ],
        sort_key_prefix=30,
        # runtime_state_group=PUNCH_SOURCE_OLA_MYSQL_RUNTIME_STATE,
    )

    PUNCH_SOURCE_OLA_MYSQL_CONTROL_IDS_SELECTOR = ConfigSelectorDefinition(
        function=_select_control_ids,
        parameters=[
            ConfigSectionOptionDefinition(
                section_name=OlaMySql.CONFIG_SECTION_OLA_MYSQL,
                option_definition=OlaMySql.CONFIG_OPTION_HOST,
            ),
            ConfigSectionOptionDefinition(
                section_name=OlaMySql.CONFIG_SECTION_OLA_MYSQL,
                option_definition=OlaMySql.CONFIG_OPTION_USER,
            ),
            ConfigSectionOptionDefinition(
                section_name=OlaMySql.CONFIG_SECTION_OLA_MYSQL,
                option_definition=OlaMySql.CONFIG_OPTION_PASSWORD,
            ),
            ConfigSectionOptionDefinition(
                section_name=OlaMySql.CONFIG_SECTION_OLA_MYSQL,
                option_definition=OlaMySql.CONFIG_OPTION_DATABASE,
            ),
            ConfigSectionOptionDefinition(
                section_name=OlaMySql.CONFIG_SECTION_OLA_MYSQL,
                option_definition=OlaMySql.CONFIG_OPTION_EVENT,
            ),
            ConfigSectionOptionDefinition(
                section_name=OlaMySql.CONFIG_SECTION_OLA_MYSQL,
                option_definition=OlaMySql.CONFIG_OPTION_EVENT_RACE,
            ),
        ],
        message="Unable to find any Control IDs.",
    )

    CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_CONTROL_IDS.set_selector(
        PUNCH_SOURCE_OLA_MYSQL_CONTROL_IDS_SELECTOR
    )

    PUNCH_SOURCE_OLA_MYSQL_CONTROL_IDS_VERIFIER = ConfigVerifierDefinition(
        function=_verify_control_ids,
        parameters=[
            ConfigSectionOptionDefinition(
                section_name=OlaMySql.CONFIG_SECTION_OLA_MYSQL,
                option_definition=OlaMySql.CONFIG_OPTION_HOST,
            ),
            ConfigSectionOptionDefinition(
                section_name=OlaMySql.CONFIG_SECTION_OLA_MYSQL,
                option_definition=OlaMySql.CONFIG_OPTION_USER,
            ),
            ConfigSectionOptionDefinition(
                section_name=OlaMySql.CONFIG_SECTION_OLA_MYSQL,
                option_definition=OlaMySql.CONFIG_OPTION_PASSWORD,
            ),
            ConfigSectionOptionDefinition(
                section_name=OlaMySql.CONFIG_SECTION_OLA_MYSQL,
                option_definition=OlaMySql.CONFIG_OPTION_DATABASE,
            ),
            ConfigSectionOptionDefinition(
                section_name=OlaMySql.CONFIG_SECTION_OLA_MYSQL,
                option_definition=OlaMySql.CONFIG_OPTION_EVENT,
            ),
            ConfigSectionOptionDefinition(
                section_name=OlaMySql.CONFIG_SECTION_OLA_MYSQL,
                option_definition=OlaMySql.CONFIG_OPTION_EVENT_RACE,
            ),
            ConfigSectionOptionDefinition(
                section_name=name,
                option_definition=CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_CONTROL_IDS,
            ),
        ],
        message="The entered Control IDs do not exist in the selected event race.",
    )

    CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_CONTROL_IDS.set_verifier(
        PUNCH_SOURCE_OLA_MYSQL_CONTROL_IDS_VERIFIER
    )

    PUNCH_SOURCE_OLA_MYSQL_LAST_MODIFIED_TIME_VERIFIER = ConfigVerifierDefinition(
        function=_verify_fetch,
        parameters=[
            ConfigSectionOptionDefinition(
                section_name=OlaMySql.CONFIG_SECTION_OLA_MYSQL,
                option_definition=OlaMySql.CONFIG_OPTION_HOST,
            ),
            ConfigSectionOptionDefinition(
                section_name=OlaMySql.CONFIG_SECTION_OLA_MYSQL,
                option_definition=OlaMySql.CONFIG_OPTION_USER,
            ),
            ConfigSectionOptionDefinition(
                section_name=OlaMySql.CONFIG_SECTION_OLA_MYSQL,
                option_definition=OlaMySql.CONFIG_OPTION_PASSWORD,
            ),
            ConfigSectionOptionDefinition(
                section_name=OlaMySql.CONFIG_SECTION_OLA_MYSQL,
                option_definition=OlaMySql.CONFIG_OPTION_DATABASE,
            ),
            ConfigSectionOptionDefinition(
                section_name=OlaMySql.CONFIG_SECTION_OLA_MYSQL,
                option_definition=OlaMySql.CONFIG_OPTION_EVENT,
            ),
            ConfigSectionOptionDefinition(
                section_name=OlaMySql.CONFIG_SECTION_OLA_MYSQL,
                option_definition=OlaMySql.CONFIG_OPTION_EVENT_RACE,
            ),
            ConfigSectionOptionDefinition(
                section_name=name,
                option_definition=CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_CONTROL_IDS,
            ),
            ConfigSectionOptionDefinition(
                section_name=name,
                option_definition=CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_MODIFIED_TIME,
            ),
        ],
        message="Check the configuration.",
    )

    CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_MODIFIED_TIME.set_verifier(
        PUNCH_SOURCE_OLA_MYSQL_LAST_MODIFIED_TIME_VERIFIER
    )

    PUNCH_SOURCE_OLA_MYSQL_LAST_RECEIVED_PUNCH_ID_VERIFIER = ConfigVerifierDefinition(
        function=_verify_fetch,
        parameters=[
            ConfigSectionOptionDefinition(
                section_name=OlaMySql.CONFIG_SECTION_OLA_MYSQL,
                option_definition=OlaMySql.CONFIG_OPTION_HOST,
            ),
            ConfigSectionOptionDefinition(
                section_name=OlaMySql.CONFIG_SECTION_OLA_MYSQL,
                option_definition=OlaMySql.CONFIG_OPTION_USER,
            ),
            ConfigSectionOptionDefinition(
                section_name=OlaMySql.CONFIG_SECTION_OLA_MYSQL,
                option_definition=OlaMySql.CONFIG_OPTION_PASSWORD,
            ),
            ConfigSectionOptionDefinition(
                section_name=OlaMySql.CONFIG_SECTION_OLA_MYSQL,
                option_definition=OlaMySql.CONFIG_OPTION_DATABASE,
            ),
            ConfigSectionOptionDefinition(
                section_name=OlaMySql.CONFIG_SECTION_OLA_MYSQL,
                option_definition=OlaMySql.CONFIG_OPTION_EVENT,
            ),
            ConfigSectionOptionDefinition(
                section_name=OlaMySql.CONFIG_SECTION_OLA_MYSQL,
                option_definition=OlaMySql.CONFIG_OPTION_EVENT_RACE,
            ),
            ConfigSectionOptionDefinition(
                section_name=name,
                option_definition=CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_CONTROL_IDS,
            ),
            ConfigSectionOptionDefinition(
                section_name=name,
                option_definition=CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_MODIFIED_TIME,
            ),
            ConfigSectionOptionDefinition(
                section_name=name,
                option_definition=CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_RECEIVED_PUNCH_ID,
            ),
        ],
        message="Check the configuration.",
    )

    CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_RECEIVED_PUNCH_ID.set_verifier(
        PUNCH_SOURCE_OLA_MYSQL_LAST_RECEIVED_PUNCH_ID_VERIFIER
    )

    Config.register_config_section_definition(
        PUNCH_SOURCE_OLA_MYSQL_CONFIG_SECTION_DEFINITION
    )

    @classmethod
    def config_section_definition(cls) -> ConfigSectionDefinition:
        return cls.PUNCH_SOURCE_OLA_MYSQL_CONFIG_SECTION_DEFINITION

    def __repr__(self) -> str:
        return (
            f"PunchSourceOlaMySQL(running={self.is_running()},"
            f" last_passed_time={self.last_modify_time},"
            f" last_received_punch_id={self.last_received_punch_id},"
            f" fetch_interval_seconds={self.fetch_interval_seconds},"
            f" control_ids={self.control_ids})"
        )

    def __str__(self) -> str:
        return repr(self)

    def __init__(self):
        _PunchSourceBase.__init__(self)
        StateSaverMixin.__init__(
            self, self.name, [PUNCH_SOURCE_OLA_MYSQL_RUNTIME_STATE]
        )

        if _MODULE_LOGGER_NAME != self.__class__.__name__:
            raise ValueError(
                f"_MODULE_LOGGER_NAME not correct: {_MODULE_LOGGER_NAME} vs {self.__class__.__name__}"
            )

        self.logger = logging.getLogger(self.__class__.__name__)

        self.ola_mysql = OlaMySql()

        self.last_modify_time = None
        self.last_received_punch_id = None
        self.fetch_interval_seconds = None
        self.control_ids = None

        self._stop_event = Event()
        self._stop_event.set()
        self.punch_fetcher = None

        self.logger.debug(self)

        self.update()

        if self._data_read(
            self.CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_MODIFIED_TIME
        ):
            self.last_modify_time = self._get_value(
                self.CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_MODIFIED_TIME
            )
            self.logger.info(
                "Read %s value from state file: %s",
                self.CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_MODIFIED_TIME.name,
                self.last_modify_time,
            )
        if self._data_read(
            self.CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_RECEIVED_PUNCH_ID
        ):
            self.last_received_punch_id = self._get_value(
                self.CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_RECEIVED_PUNCH_ID
            )
            self.logger.info(
                "Read %s value from state file: %s",
                self.CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_RECEIVED_PUNCH_ID.name,
                self.last_received_punch_id,
            )

        self._notify_tracking_listeners()

    def __del__(self):
        self.stop()

    def start(self):
        self._stop_event.clear()
        self.punch_fetcher = Thread(
            target=self._fetch_punches, daemon=True, name="PunchFetcherOlaMySqlThread"
        )
        self.punch_fetcher.start()

    def stop(self):
        self._stop_event.set()
        if self.punch_fetcher is not None and self.punch_fetcher.is_alive():
            self.punch_fetcher.join()

    def is_running(self) -> bool:
        return not self._stop_event.is_set()

    def config_updated(self, section_names: list[str]):
        self.update()

    def update(self):
        self._parse_config()

    def _parse_config(self):
        self.logger.debug("_parse_config")
        config_section = Config().get_section(self.name)

        self.fetch_interval_seconds = (
            self.CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_FETCH_INTERVAL_SECONDS.get_value(
                config_section
            )
        )
        self.control_ids = (
            self.CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_CONTROL_IDS.get_value(
                config_section
            )
        )
        if self.control_ids is not None:
            self.control_ids = [int(c) for c in self.control_ids.split()]

    def _get_tracking_state(self) -> dict[str, str]:
        return {
            self.CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_MODIFIED_TIME.name: str(
                self.last_modify_time or ""
            ),
            self.CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_RECEIVED_PUNCH_ID.name: str(
                self.last_received_punch_id or ""
            ),
        }

    def get_runtime_value(self, option_definition: ConfigOptionDefinition):
        if (
            option_definition
            is self.CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_MODIFIED_TIME
        ):
            return self.last_modify_time
        if (
            option_definition
            is self.CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_RECEIVED_PUNCH_ID
        ):
            return self.last_received_punch_id
        return None

    def set_runtime_value(self, option_definition: ConfigOptionDefinition, value: str):
        if (
            option_definition
            is self.CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_MODIFIED_TIME
        ):
            self.last_modify_time = value
        elif (
            option_definition
            is self.CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_RECEIVED_PUNCH_ID
        ):
            self.last_received_punch_id = value
        else:
            return
        self._save_state()

    def reset_tracking(self):
        self.last_modify_time = None
        self.last_received_punch_id = None
        self._save_state()

    def _save_state(self):
        self.logger.debug(
            "_save_state: %s %s", self.last_modify_time, self.last_received_punch_id
        )

        values = {
            self.CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_MODIFIED_TIME: self.last_modify_time,
            self.CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_RECEIVED_PUNCH_ID: self.last_received_punch_id,
        }

        self._save_values(values)

        self._notify_tracking_listeners()

    def _fetch_punches(self):
        self.logger.debug("Started")
        while not self._stop_event.is_set():
            try:
                assert self.control_ids is not None
                split_times = self.ola_mysql.get_event_race_split_times(
                    self.control_ids, self.last_modify_time
                )
                for split_time in split_times:
                    self.logger.debug(split_time)
                    if self.last_received_punch_id == split_time[PUNCH_KEY_ID]:
                        self.logger.debug(
                            'Skipping: "%s" is the same as the last received Punch.',
                            split_time[PUNCH_KEY_ID],
                        )
                        continue
                    self._notify_punch_listeners(split_time)
                    self.last_received_punch_id = split_time[PUNCH_KEY_ID]
                    self.logger.debug(
                        "last_received_punch_id: %s", self.last_received_punch_id
                    )
                    self.last_modify_time = split_time[_SPLIT_TIME_KEY_MODIFY_DATE]
                    self.logger.debug("last_modify_time: %s", self.last_modify_time)
                    self._save_state()
            except OperationalError as oe:
                self.logger.error(oe)
            except Exception as e:  # noqa: BLE001 - broad catch intentional; libraries raise diverse exceptions
                self.logger.error("Unexpected error fetching punches: %s", e)

            self._stop_event.wait(timeout=self.fetch_interval_seconds)
        self.logger.debug("Stopped")
        Config().write()
