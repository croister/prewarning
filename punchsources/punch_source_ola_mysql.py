# -*- coding: utf-8 -*-

import logging
from threading import Thread
from time import sleep
from typing import List, Dict, Any

from pymysql import OperationalError

from utils.config import ConfigSectionDefinition, ConfigOptionDefinition, Config
from utils.config_definitions import ConfigSectionEnableType, ConfigVerifierDefinition, ConfigSectionOptionDefinition, \
    ConfigSelectorDefinition, SelectionData, SelectionType, SelectionResult, VerificationResult
from utils.ola_mysql import OlaMySql, connect, get_event_race_split_time_controls, are_valid_event_race_control_ids, \
    get_event_race_split_times, get_ola_db_version, is_relay_event
from validators.datetime_validators import is_timestamp
from validators.regex_validators import is_control_ids, is_punch_id
from ._base import _PunchSourceBase


LOGGER_NAME = 'PunchSourceOlaMySql'


def _select_control_ids(host: str, user: str, password: str, database: str, event_id: int, event_race_id: int):
    try:
        connection = connect(host, user, password, database)
        with connection:
            result = SelectionResult(caption='Control Ids',
                                     message='Select Control Ids:',
                                     selection_type=SelectionType.MULTIPLE)
            ola_db_version = get_ola_db_version(connection)
            is_relay = is_relay_event(connection, event_id=event_id)
            control_ids = get_event_race_split_time_controls(connection,
                                                             ola_db_version=ola_db_version,
                                                             is_relay=is_relay,
                                                             event_race_id=event_race_id)
            for control_id in control_ids:

                result.add_value(SelectionData(control_id['ID'],
                                               _split_time_control_description(control_id)))
            return result
    except Exception as e:
        logging.getLogger(LOGGER_NAME).debug('_select_control_ids: %s', e)
        return False


def _split_time_control_name(control_id: Dict[str, Any]) -> str:
    split_time_control_name = control_id['splitTimeControlName']
    if split_time_control_name is None or len(split_time_control_name) == 0:
        split_time_control_name = control_id['controlName']
    if split_time_control_name is None or len(split_time_control_name) == 0:
        split_time_control_name = ''

    return split_time_control_name


def _split_time_control_description(control_id: Dict[str, Any]) -> str:
    split_time_control_name = _split_time_control_name(control_id)

    class_names = control_id['classNames']
    if len(class_names) > 50:
        class_names = '{class_names:.46} ...'.format(class_names=class_names)

    description = '{id}: {name} ({e_codes}) used by {class_count} classes ({class_names})'.format(
        id=control_id['ID'],
        name=split_time_control_name,
        e_codes=control_id['punchingCodes'],
        class_count=control_id['classCount'],
        class_names=class_names)
    return description


def _verify_control_ids(host: str, user: str, password: str, database: str,
                        event_id: int, event_race_id: int, control_ids: str):
    try:
        if control_ids is None or len(control_ids) == 0:
            control_id_ints = []
        else:
            control_id_ints = [int(control_id) for control_id in control_ids.split()]

        connection = connect(host, user, password, database)
        with connection:
            ola_db_version = get_ola_db_version(connection)
            is_relay = is_relay_event(connection, event_id=event_id)
            return are_valid_event_race_control_ids(connection,
                                                    ola_db_version=ola_db_version,
                                                    is_relay=is_relay,
                                                    event_race_id=event_race_id,
                                                    control_ids=control_id_ints)
    except Exception as e:
        logging.getLogger(LOGGER_NAME).debug('_select_control_ids: %s', e)
        return False


def _verify_fetch(host: str, user: str, password: str, database: str,
                  event_id: int, event_race_id: int, control_ids: str,
                  last_modify_time: str or None, last_received_punch_id: str = None) -> VerificationResult:
    try:
        if control_ids is None or len(control_ids) == 0:
            control_id_ints = []
        else:
            control_id_ints = [int(control_id) for control_id in control_ids.split()]

        connection = connect(host, user, password, database)
        with connection:
            ola_db_version = get_ola_db_version(connection)
            event_split_times = get_event_race_split_times(connection,
                                                           ola_db_version=ola_db_version,
                                                           event_id=event_id,
                                                           event_race_id=event_race_id,
                                                           control_ids=control_id_ints,
                                                           last_modify_time=last_modify_time)

            if len(event_split_times) == 0:
                return VerificationResult(message='No Punches received')

            if last_received_punch_id is not None:
                split_time_ids = [split_time['id'] for split_time in event_split_times]
                if last_received_punch_id in split_time_ids:
                    return VerificationResult(message=f'{len(event_split_times)} Punches received and 1 ignored.')

            return VerificationResult(message=f'{len(event_split_times)} Punches received.')
    except Exception as e:
        logging.getLogger(LOGGER_NAME).debug('_verify_fetch: %s', e)
        return VerificationResult(message=str(e), status=False)


class PunchSourceOlaMySql(_PunchSourceBase):
    """
    A Punch Source that reads the Punches from the OLA MySQL Database.
    """

    name = __qualname__

    display_name = 'OLA MySQL Punch Source'

    description = 'Fetches electronic punches from the MySQL database used by the ' \
                  '<a href="https://www.svenskorientering.se/Arrangera/itochtavlings-administration/' \
                  'OLAtidtagnings-program/">OLA event organizing software</a>. ' \
                  'These punches have been fetched or received using one of the built-in methods in OLA. ' \
                  'OLA must be using MySQL as the database engine, the built-in database is not supported.'

    CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_CONTROL_IDS = ConfigOptionDefinition(
        name='ControlIDs',
        display_name='Control Ids',
        value_type=str,
        description='The Control IDs to use for Pre-Warning, separated by space.'
                    ' Use the Control Code (Kodsiffra) from OLA, NOT the punching units (Elektronisk stämplingskod).',
        mandatory=True,
        validator=is_control_ids,
    )

    CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_FETCH_INTERVAL_SECONDS = ConfigOptionDefinition(
        name='FetchIntervalSeconds',
        display_name='Fetch Interval',
        value_type=int,
        description='The number of seconds between calls to the OLA MySQL database.',
        default_value=10,
        valid_values=list(range(1, 121)),
    )

    CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_MODIFIED_TIME = ConfigOptionDefinition(
        name='LastModifiedTime',
        display_name='Last Modified Time',
        value_type=str,
        description='The Modified Time of the last retrieved Punch, used to only fetch Punches that are newer. '
                    'On the format of "YYYY-MM-DD hh:mm:ss.fff".',
        default_value='',
        validator=is_timestamp,
    )

    CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_RECEIVED_PUNCH_ID = ConfigOptionDefinition(
        name='LastReceivedPunchId',
        display_name='Last Received Punch Id',
        value_type=str,
        description='The Id of the last received Punch, used to not process it again. '
                    'On the format of `resultRaceIndividualNumber`_`passedCount`_`timingControl` '
                    'from the table `SplitTimes`, example "1_1_1".',
        default_value='',
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
        message='Unable to find any Control IDs.',
    )

    CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_CONTROL_IDS.set_selector(PUNCH_SOURCE_OLA_MYSQL_CONTROL_IDS_SELECTOR)

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
        message='The entered Control IDs do not exist in the selected event race.',
    )

    CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_CONTROL_IDS.set_verifier(PUNCH_SOURCE_OLA_MYSQL_CONTROL_IDS_VERIFIER)

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
        message='Check the configuration.',
    )

    CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_MODIFIED_TIME.set_verifier(
        PUNCH_SOURCE_OLA_MYSQL_LAST_MODIFIED_TIME_VERIFIER)

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
        message='Check the configuration.',
    )

    CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_RECEIVED_PUNCH_ID.set_verifier(
        PUNCH_SOURCE_OLA_MYSQL_LAST_RECEIVED_PUNCH_ID_VERIFIER)

    Config.register_config_section_definition(PUNCH_SOURCE_OLA_MYSQL_CONFIG_SECTION_DEFINITION)

    @classmethod
    def config_section_definition(cls) -> ConfigSectionDefinition:
        return cls.PUNCH_SOURCE_OLA_MYSQL_CONFIG_SECTION_DEFINITION

    def __repr__(self) -> str:
        return f'PunchSourceOlaMySQL(running={self._running},' \
               f' last_passed_time={self.last_modify_time},' \
               f' last_received_punch_id={self.last_received_punch_id},' \
               f' fetch_interval_seconds={self.fetch_interval_seconds},' \
               f' control_ids={self.control_ids})'

    def __str__(self) -> str:
        return repr(self)

    def __init__(self):
        super().__init__()

        if LOGGER_NAME != self.__class__.__name__:
            raise ValueError('LOGGER_NAME not correct: {} vs {}'.format(LOGGER_NAME, self.__class__.__name__))

        self.logger = logging.getLogger(self.__class__.__name__)

        self.ola_mysql = OlaMySql()

        self.last_modify_time = None
        self.last_received_punch_id = None
        self.fetch_interval_seconds = None
        self.control_ids = None

        self._running = False
        self._last_written_punch_ids = list()

        self.logger.debug(self)

        self.update()

        self.punch_fetcher = Thread(target=self._fetch_punches, daemon=True, name='PunchFetcherOlaMySqlThread')

    def __del__(self):
        self.stop()
        if self.punch_fetcher.is_alive():
            self.punch_fetcher.join()

    def start(self):
        self._running = True
        self.punch_fetcher.start()

    def stop(self):
        self._running = False

    def is_running(self) -> bool:
        return self._running

    def config_updated(self, section_names: List[str]):
        self.update()

    def update(self):
        self._parse_config()

    def _not_in_last_written(self, new_last_received_punch_id: int) -> bool:
        self.logger.debug('_not_in_last_written: %s %s', self._last_written_punch_ids, new_last_received_punch_id)
        return new_last_received_punch_id not in self._last_written_punch_ids

    def _parse_config(self):
        self.logger.debug('_parse_config')
        config_section = Config().get_section(self.name)

        new_last_received_punch_id = self.CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_RECEIVED_PUNCH_ID.get_value(
            config_section)
        self.logger.debug('_parse_config: old %s new %s', self.last_received_punch_id, new_last_received_punch_id)

        # Used to prevent unintentional decreases of last received punch id due to
        # late updates from the config file watcher.
        if self._not_in_last_written(new_last_received_punch_id):
            self.last_modify_time = self.CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_MODIFIED_TIME.get_value(
                config_section)
            self.last_received_punch_id = new_last_received_punch_id

        # If the new last received punch id matches the last we already have we are receiving the last update and
        # can clear the last written punch ids. This allows for us to receive intentional manual changes of the config.
        if self.last_received_punch_id == new_last_received_punch_id:
            self._last_written_punch_ids.clear()

        self.fetch_interval_seconds = self.CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_FETCH_INTERVAL_SECONDS\
            .get_value(config_section)
        self.control_ids = self.CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_CONTROL_IDS.get_value(config_section)
        if self.control_ids is not None:
            self.control_ids = self.control_ids.split()

    def _write_config(self):
        self.logger.debug('_write_config')
        config_section = Config().get_section(self.name)

        self.CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_MODIFIED_TIME.set_value(config_section, self.last_modify_time)
        self.CONFIG_OPTION_PUNCH_SOURCE_OLA_MYSQL_LAST_RECEIVED_PUNCH_ID.set_value(config_section,
                                                                                   self.last_received_punch_id)

        Config().write()

    def _fetch_punches(self):
        self.logger.debug('Started')
        while self._running:
            self._last_written_punch_ids.clear()
            try:
                split_times = self.ola_mysql.get_event_race_split_times(self.control_ids, self.last_modify_time)
                for split_time in split_times:
                    self.logger.debug(split_time)
                    if self.last_received_punch_id == split_time['id']:
                        self.logger.debug('Skipping: "%s" is the same as the last received Punch.', split_time['id'])
                        continue
                    self._notify_punch_listeners(split_time)
                    self.last_received_punch_id = split_time['id']
                    self._last_written_punch_ids.append(self.last_received_punch_id)
                    self.logger.debug('last_received_punch_id: %s', self.last_received_punch_id)
                    self.last_modify_time = split_time['modifyDate']
                    self.logger.debug('last_modify_time: %s', self.last_modify_time)
                    self._write_config()
            except OperationalError as oe:
                self.logger.error(oe)

            sleep(self.fetch_interval_seconds)
        self.logger.debug('Stopped')
