# -*- coding: utf-8 -*-

import logging
from enum import unique, Enum
from typing import List, Any, Dict

import pymysql
from pymysql.connections import Connection
from pymysql.cursors import DictCursor

from utils.config import Config
from utils.config_consumer import ConfigConsumer
from utils.config_definitions import ConfigOptionDefinition, ConfigSectionDefinition, ConfigSectionEnableType, \
    ConfigSectionOptionDefinition, ConfigSelectorDefinition, SelectionData, SelectionResult
from utils.config_verification import ConfigVerifierDefinition
from utils.singleton import Singleton
from validators.host_and_domain_name_validators import is_hostname_or_ip


LOGGER_NAME = 'OlaMySql'


def connect(host: str, user: str, password: str, database: str = None) -> Connection:
    logging.getLogger(LOGGER_NAME).debug('connect')

    connection = pymysql.connect(host=host,
                                 user=user,
                                 password=password,
                                 database=database,
                                 cursorclass=DictCursor)
    return connection


BUILT_IN_DATABASES = ['information_schema', 'mysql', 'performance_schema', 'sys']
DATABASE_KEY_NAME = 'Database'


def get_database_names(connection: Connection) -> List[str]:
    logging.getLogger(LOGGER_NAME).debug('get_database_names')

    database_names = []
    with connection.cursor(DictCursor) as cursor:
        sql = 'SHOW DATABASES' \
              ';'
        cursor.execute(sql)
        raw_databases = cursor.fetchall()
        logging.getLogger(LOGGER_NAME).debug('Raw databases data: %s', raw_databases)
        for item in raw_databases:
            if DATABASE_KEY_NAME in item:
                database_name = item[DATABASE_KEY_NAME]
                if database_name not in BUILT_IN_DATABASES:
                    database_names.append(database_name)
        logging.getLogger(LOGGER_NAME).debug('Parsed database names: %s', database_names)
    return database_names


def is_ola_database(connection: Connection) -> bool:
    logging.getLogger(LOGGER_NAME).debug('is_ola_database')

    is_ola_db = get_ola_db_version(connection) != 0
    logging.getLogger(LOGGER_NAME).debug('is_ola_database({}) == {}'.format(connection.db, is_ola_db))
    return is_ola_db


def get_ola_db_version(connection: Connection) -> int:
    logging.getLogger(LOGGER_NAME).debug('get_ola_db_version')

    versions = []
    with connection.cursor(DictCursor) as cursor:
        sql = 'SELECT' \
              '  `versionNumber`,' \
              '  `comment`,' \
              '  `moduleId`' \
              ' FROM `Version`' \
              ';'
        cursor.execute(sql)
        versions.extend(cursor.fetchall())
        logging.getLogger(LOGGER_NAME).debug('Versions data: %s', versions)

    version_number = 0
    for version in versions:
        version_number = max(version_number, version['versionNumber'])
    logging.getLogger(LOGGER_NAME).debug('Version number: %d', version_number)
    return version_number


@unique
class EventForm(Enum):
    INDIVIDUAL_SINGLE_DAY = 'IndSingleDay'
    INDIVIDUAL_MULTI_DAY = 'IndMultiDay'
    TEAM_SINGLE_DAY = 'TeamSingleDay'
    TEAM_MULTI_DAY = 'TeamMultiDay'
    RELAY_SINGLE_DAY = 'RelaySingleDay'
    RELAY_MULTI_DAY = 'RelayMultiDay'
    PATROL_SINGLE_DAY = 'PatrolSingleDay'
    PATROL_MULTI_DAY = 'PatrolMultiDay'

    def __str__(self) -> str:
        return str(self.value)

    def as_list(self) -> List['EventForm']:
        return [self]

    def as_str_list(self) -> List[str]:
        return [str(self)]

    def __eq__(self, other):
        if type(other) == str:
            return self.value == other
        return super(Enum).__eq__(other)


@unique
class EventFormType(Enum):

    INDIVIDUAL = [EventForm.INDIVIDUAL_SINGLE_DAY,
                  EventForm.INDIVIDUAL_MULTI_DAY]
    TEAM = [EventForm.TEAM_SINGLE_DAY,
            EventForm.TEAM_MULTI_DAY]
    RELAY = [EventForm.RELAY_SINGLE_DAY,
             EventForm.RELAY_MULTI_DAY]
    PATROL = [EventForm.PATROL_SINGLE_DAY,
              EventForm.PATROL_MULTI_DAY]
    ALL = [EventForm.INDIVIDUAL_SINGLE_DAY,
           EventForm.INDIVIDUAL_MULTI_DAY,
           EventForm.TEAM_SINGLE_DAY,
           EventForm.TEAM_MULTI_DAY,
           EventForm.RELAY_SINGLE_DAY,
           EventForm.RELAY_MULTI_DAY,
           EventForm.PATROL_SINGLE_DAY,
           EventForm.PATROL_MULTI_DAY]

    def __str__(self) -> str:
        return ', '.join(self.as_str_list())

    def as_list(self) -> List[EventForm]:
        return self.value

    def as_str_list(self) -> List[str]:
        return [str(v) for v in self.value]

    def __eq__(self, other):
        if type(other) == str or type(other) == EventForm:
            return other in self.value
        return super(Enum).__eq__(other)


def _generate_in_format_str(no_of_values: int):
    return ', '.join(['%s'] * no_of_values)


def get_events(connection: Connection, event_forms: EventForm or EventFormType = None) -> List[Dict[str, Any]]:
    logging.getLogger(LOGGER_NAME).debug('get_events')

    if event_forms is None:
        event_forms = EventFormType.ALL

    events = []
    with connection.cursor(DictCursor) as cursor:
        event_forms_format_str = _generate_in_format_str(len(event_forms.as_list()))
        sql = 'SELECT' \
              '  `eventId`,' \
              '  `name`,' \
              '  `eventNumber`,' \
              '  `district`,' \
              '  `startDate`,' \
              '  `finishDate`,' \
              '  `eventForm`,' \
              '  `punchingSportIdent`,' \
              '  `punchingEmit`' \
              ' FROM `Events`' \
              ' WHERE `eventForm` IN ({})' \
              ';'.format(event_forms_format_str)
        cursor.execute(sql, event_forms.as_str_list())
        events.extend(cursor.fetchall())
    logging.getLogger(LOGGER_NAME).debug('Events data: %s', events)
    return events


def get_event(connection: Connection, event_id: int) -> Dict[str, Any]:
    logging.getLogger(LOGGER_NAME).debug('get_event')

    with connection.cursor(DictCursor) as cursor:
        sql = 'SELECT' \
              '  `eventId`,' \
              '  `name`,' \
              '  `eventNumber`,' \
              '  `district`,' \
              '  `startDate`,' \
              '  `finishDate`,' \
              '  `eventForm`,' \
              '  `punchingSportIdent`,' \
              '  `punchingEmit`' \
              ' FROM `Events`' \
              ' WHERE `eventId` = %s' \
              ';'
        args = [event_id]
        cursor.execute(sql, args)
        event = cursor.fetchone()
    logging.getLogger(LOGGER_NAME).debug('Event data: %s', event)
    return event


def is_valid_event(connection: Connection, event_id: int, event_forms: EventForm or EventFormType = None) -> bool:
    logging.getLogger(LOGGER_NAME).debug('is_valid_event')

    if event_forms is None:
        event_forms = EventFormType.ALL

    event = get_event(connection, event_id=event_id)

    correct_event_type = False
    event_exists = event is not None
    if event_exists:
        event_form_str = event['eventForm']
        correct_event_type = event_forms == event_form_str

    valid_event = event_exists and correct_event_type
    logging.getLogger(LOGGER_NAME).debug('is_valid_event({}) == {}'.format(event_id, valid_event))
    return valid_event


def is_relay_event(connection: Connection, event_id: int) -> bool:
    logging.getLogger(LOGGER_NAME).debug('is_relay_event')

    relay_event = is_valid_event(connection, event_id=event_id, event_forms=EventFormType.RELAY)
    logging.getLogger(LOGGER_NAME).debug('is_relay_event({}) == {}'.format(event_id, relay_event))
    return relay_event


def get_event_races(connection: Connection, event_id: int) -> List[Dict[str, Any]]:
    logging.getLogger(LOGGER_NAME).debug('get_event_races')

    event_races = []
    with connection.cursor(DictCursor) as cursor:
        sql = 'SELECT *' \
              '  FROM `EventRaces`' \
              ' WHERE `eventId` = %s' \
              ';'
        cursor.execute(sql, (event_id, ))
        event_races.extend(cursor.fetchall())
        logging.getLogger(LOGGER_NAME).debug('Event races data: %s', event_races)
    return event_races


def is_valid_event_race(connection: Connection, event_id: int, event_race_id: int) -> bool:
    logging.getLogger(LOGGER_NAME).debug('is_valid_event_race')

    valid_event_race = event_race_id in [er['eventRaceId'] for er in get_event_races(connection, event_id)]
    logging.getLogger(LOGGER_NAME).debug('is_valid_event_race({}) == {}'.format(event_race_id, valid_event_race))
    return valid_event_race


def get_event_race_split_time_controls(connection: Connection,
                                       ola_db_version: int,
                                       is_relay: bool,
                                       event_race_id: int) -> List[Dict[str, Any]]:
    logging.getLogger(LOGGER_NAME).debug('get_event_split_time_controls')

    class_names_query = 'GROUP_CONCAT(' \
                        'DISTINCT `EventClasses`.`name` ' \
                        'SEPARATOR ", ")'
    if is_relay:
        class_names_query = 'GROUP_CONCAT(' \
                            'DISTINCT CONCAT(`EventClasses`.`name`, " - ", `RaceClasses`.`raceClassName`) ' \
                            'SEPARATOR ", ")'

    event_split_time_controls = []
    with connection.cursor(DictCursor) as cursor:
        if ola_db_version >= 565:  # OLA 6.3.9
            sql = 'SELECT DISTINCT' \
                  '       `RaceClassSplitTimeControls`.`name` AS `raceClassSplitTimeControlName`,' \
                  '       `Controls`.`name` AS `splitTimeControlName`,' \
                  '       `Controls`.`name` AS `controlName`,' \
                  '       `Controls`.`ID` AS `ID`,' \
                  '       GROUP_CONCAT(DISTINCT `PunchingUnits`.`punchingCode`' \
                  '          ORDER BY `PunchingUnits`.`punchingCode`' \
                  '          SEPARATOR ", ") AS `punchingCodes`,' \
                  '       `Controls`.`location` AS `controlLocation`,' \
                  '       `Controls`.`controlAreaName` AS `controlAreaName`,' \
                  '       COUNT(DISTINCT `RaceClasses`.`raceClassId`) AS `classCount`,' \
                  '       {class_names_query} AS `classNames`,' \
                  '       `RaceClassSplitTimeControls`.`noSplitTimes` AS `noSplitTimes`' \
                  ' FROM `Controls`' \
                  '  LEFT JOIN `CoursesWayPointControls`' \
                  '         ON `Controls`.`controlId` = `CoursesWayPointControls`.`controlId`' \
                  '  LEFT JOIN `RaceClassCourses`' \
                  '         ON `CoursesWayPointControls`.`courseId` = `RaceClassCourses`.`courseId`' \
                  '  LEFT JOIN `RaceClasses`' \
                  '         ON `RaceClassCourses`.`raceClassId` = `RaceClasses`.`raceClassId`' \
                  '  LEFT JOIN `EventClasses`' \
                  '         ON `RaceClasses`.`eventClassId` = `EventClasses`.`eventClassId`' \
                  '  LEFT JOIN `ControlsPunchingUnits`' \
                  '         ON `Controls`.`controlId` = `ControlsPunchingUnits`.`control`' \
                  '  LEFT JOIN `PunchingUnits`' \
                  '         ON `ControlsPunchingUnits`.`punchingUnit` = `PunchingUnits`.`punchingUnitId`' \
                  '  LEFT OUTER JOIN `RaceClassSplitTimeControls`' \
                  '         ON `Controls`.`controlId` = `RaceClassSplitTimeControls`.`splitTimeControlId`' \
                  ' WHERE `Controls`.`typeCode` = "WTC"' \
                  '   AND `Controls`.`eventRaceId` = %s' \
                  ' GROUP BY' \
                  '       `Controls`.`ID`' \
                  ' ORDER BY' \
                  '       `Controls`.`ID` ASC,' \
                  '       `EventClasses`.`name` ASC,' \
                  '       `RaceClasses`.`raceClassName` ASC' \
                  ';'.format(class_names_query=class_names_query)
        elif ola_db_version >= 564:  # OLA 6.3.0.0
            sql = 'SELECT DISTINCT' \
                  '       `RaceClassSplitTimeControls`.`name` AS `raceClassSplitTimeControlName`,' \
                  '       `Controls`.`name` AS `splitTimeControlName`,' \
                  '       `Controls`.`name` AS `controlName`,' \
                  '       `Controls`.`ID` AS `ID`,' \
                  '       GROUP_CONCAT(DISTINCT `PunchingUnits`.`punchingCode`' \
                  '          ORDER BY `PunchingUnits`.`punchingCode`' \
                  '          SEPARATOR ", ") AS `punchingCodes`,' \
                  '       `Controls`.`location` AS `controlLocation`,' \
                  '       `Controls`.`controlAreaName` AS `controlAreaName`,' \
                  '       COUNT(DISTINCT `RaceClasses`.`raceClassId`) AS `classCount`,' \
                  '       {class_names_query} AS `classNames`' \
                  ' FROM `Controls`' \
                  '  LEFT JOIN `CoursesWayPointControls`' \
                  '         ON `Controls`.`controlId` = `CoursesWayPointControls`.`controlId`' \
                  '  LEFT JOIN `RaceClassCourses`' \
                  '         ON `CoursesWayPointControls`.`courseId` = `RaceClassCourses`.`courseId`' \
                  '  LEFT JOIN `RaceClasses`' \
                  '         ON `RaceClassCourses`.`raceClassId` = `RaceClasses`.`raceClassId`' \
                  '  LEFT JOIN `EventClasses`' \
                  '         ON `RaceClasses`.`eventClassId` = `EventClasses`.`eventClassId`' \
                  '  LEFT JOIN `ControlsPunchingUnits`' \
                  '         ON `Controls`.`controlId` = `ControlsPunchingUnits`.`control`' \
                  '  LEFT JOIN `PunchingUnits`' \
                  '         ON `ControlsPunchingUnits`.`punchingUnit` = `PunchingUnits`.`punchingUnitId`' \
                  '  LEFT OUTER JOIN `RaceClassSplitTimeControls`' \
                  '         ON `Controls`.`controlId` = `RaceClassSplitTimeControls`.`splitTimeControlId`' \
                  ' WHERE `Controls`.`typeCode` = "WTC"' \
                  '   AND `Controls`.`eventRaceId` = %s' \
                  ' GROUP BY' \
                  '       `Controls`.`ID`' \
                  ' ORDER BY' \
                  '       `Controls`.`ID` ASC,' \
                  '       `EventClasses`.`name` ASC,' \
                  '       `RaceClasses`.`raceClassName` ASC' \
                  ';'.format(class_names_query=class_names_query)
        else:
            sql = 'SELECT DISTINCT' \
                  '       null AS `raceClassSplitTimeControlName`,' \
                  '       `SplitTimeControls`.`name` AS `splitTimeControlName`,' \
                  '       `Controls`.`name` AS `controlName`,' \
                  '       `Controls`.`ID` AS `ID`,' \
                  '       GROUP_CONCAT(DISTINCT `PunchingUnits`.`punchingCode`' \
                  '          ORDER BY `PunchingUnits`.`punchingCode`' \
                  '          SEPARATOR ", ") AS `punchingCodes`,' \
                  '       `Controls`.`location` AS `controlLocation`,' \
                  '       `Controls`.`controlAreaName` AS `controlAreaName`,' \
                  '       COUNT(DISTINCT `RaceClasses`.`raceClassId`) AS `classCount`,' \
                  '       {class_names_query} AS `classNames`' \
                  ' FROM `Controls`' \
                  '  LEFT JOIN `CoursesWayPointControls`' \
                  '         ON `Controls`.`controlId` = `CoursesWayPointControls`.`controlId`' \
                  '  LEFT JOIN `RaceClassCourses`' \
                  '         ON `CoursesWayPointControls`.`courseId` = `RaceClassCourses`.`courseId`' \
                  '  LEFT JOIN `RaceClasses`' \
                  '         ON `RaceClassCourses`.`raceClassId` = `RaceClasses`.`raceClassId`' \
                  '  LEFT JOIN `EventClasses`' \
                  '         ON `RaceClasses`.`eventClassId` = `EventClasses`.`eventClassId`' \
                  '  LEFT JOIN `ControlsPunchingUnits`' \
                  '         ON `Controls`.`controlId` = `ControlsPunchingUnits`.`control`' \
                  '  LEFT JOIN `PunchingUnits`' \
                  '         ON `ControlsPunchingUnits`.`punchingUnit` = `PunchingUnits`.`punchingUnitId`' \
                  '  LEFT JOIN `SplitTimeControls`' \
                  '         ON `Controls`.`controlId` = `SplitTimeControls`.`timingControl`' \
                  '  LEFT JOIN `RaceClassSplitTimeControls`' \
                  '         ON `SplitTimeControls`.`splitTimeControlId`' \
                  '          = `RaceClassSplitTimeControls`.`splitTimeControlId`' \
                  ' WHERE `Controls`.`typeCode` = "WTC"' \
                  '   AND `Controls`.`eventRaceId` = %s' \
                  ' GROUP BY' \
                  '       `Controls`.`ID`' \
                  ' ORDER BY' \
                  '       `Controls`.`ID` ASC,' \
                  '       `EventClasses`.`name` ASC,' \
                  '       `RaceClasses`.`raceClassName` ASC' \
                  ';'.format(class_names_query=class_names_query)
        args = [event_race_id]
        cursor.execute(sql, args)
        event_split_time_controls.extend(cursor.fetchall())
        logging.getLogger(LOGGER_NAME).debug('Event split time controls data: %s', event_split_time_controls)
    return event_split_time_controls


def are_valid_event_race_control_ids(connection: Connection,
                                     ola_db_version: int,
                                     is_relay: bool,
                                     event_race_id: int,
                                     control_ids: List[int]) -> bool:
    logging.getLogger(LOGGER_NAME).debug('is_valid_event_race_control_ids')

    if len(control_ids) > 0:
        event_race_control_ids = [er['ID'] for er in get_event_race_split_time_controls(connection,
                                                                                        ola_db_version=ola_db_version,
                                                                                        is_relay=is_relay,
                                                                                        event_race_id=event_race_id)]

        valid_event_race = all(control_id in event_race_control_ids for control_id in control_ids)
        logging.getLogger(LOGGER_NAME).debug('is_valid_event_race_control_ids(%s) == %s',
                                             event_race_id, valid_event_race)
    else:
        valid_event_race = False
    return valid_event_race


def _verify_connection_parameters(host: str, user: str, password: str):
    try:
        connect(host, user, password).close()
    except Exception as e:
        logging.getLogger(LOGGER_NAME).debug('_verify_connection_parameters: %s', e)
        return False
    return True


def _select_database(host: str, user: str, password: str) -> SelectionResult or False:
    try:
        connection = connect(host, user, password)
        with connection:
            result = SelectionResult(caption='Databases',
                                     message='Select a OLA Database:')
            databases = get_database_names(connection)
            for database in databases:
                result.add_value(SelectionData(database, database))
            return result
    except Exception as e:
        logging.getLogger(LOGGER_NAME).debug('_select_database: %s', e)
        return False


def _verify_database(host: str, user: str, password: str, database: str):
    try:
        connection = connect(host, user, password, database)
        with connection:
            return is_ola_database(connection)
    except Exception as e:
        logging.getLogger(LOGGER_NAME).debug('_verify_database: %s', e)
        return False


def _select_event(host: str, user: str, password: str, database: str,
                  event_forms: EventForm or EventFormType = None) -> SelectionResult or False:
    try:
        connection = connect(host, user, password, database)
        with connection:
            result = SelectionResult(caption='Events',
                                     message='Select an Event:')
            events = get_events(connection, event_forms)
            if not events:
                return False
            for event in events:
                result.add_value(SelectionData(event['eventId'],
                                               '{id}: {name} ({form}) {start}-{end}'.format(
                                                   id=event['eventId'],
                                                   name=event['name'],
                                                   form=event['eventForm'],
                                                   start=event['startDate'],
                                                   end=event['finishDate'],
                                               )))
            return result
    except Exception as e:
        logging.getLogger(LOGGER_NAME).debug('_select_event: %s', e)
        return False


def _verify_event(host: str, user: str, password: str, database: str, event_id: int,
                  event_forms: EventForm or EventFormType = None):
    if event_forms is None:
        event_forms = EventFormType.ALL

    try:
        connection = connect(host, user, password, database)
        with connection:
            return is_valid_event(connection, event_id, event_forms)
    except Exception as e:
        logging.getLogger(LOGGER_NAME).debug('_verify_event: %s', e)
        return False


def _select_event_race(host: str, user: str, password: str, database: str, event_id: int) -> SelectionResult or False:
    try:
        connection = connect(host, user, password, database)
        with connection:
            result = SelectionResult(caption='Event Races',
                                     message='Select an Event Race:')
            events_races = get_event_races(connection, event_id)
            for events_race in events_races:
                result.add_value(SelectionData(events_race['eventRaceId'],
                                               '{id}: {name} ({light}) {distance} distance {date}'.format(
                                                   id=events_race['eventRaceId'],
                                                   name=events_race['name'],
                                                   light=events_race['raceLightCondition'],
                                                   distance=events_race['raceDistance'],
                                                   date=events_race['raceDate'],
                                               )))
            return result
    except Exception as e:
        logging.getLogger(LOGGER_NAME).debug('_select_event_race: %s', e)
        return False


def _verify_event_race(host: str, user: str, password: str, database: str, event_id: int, event_race_id: int) -> bool:
    try:
        connection = connect(host, user, password, database)
        with connection:
            return is_valid_event_race(connection, event_id, event_race_id)
    except Exception as e:
        logging.getLogger(LOGGER_NAME).debug('_verify_event_race: %s', e)
        return False


def get_event_race_split_times(connection: Connection,
                               ola_db_version: int,
                               event_id: int,
                               event_race_id: int,
                               control_ids: List[int],
                               last_modify_time: str or None = None) -> List[Dict[str, Any]]:
    logging.getLogger(LOGGER_NAME).debug('get_event_race_split_times')

    if last_modify_time is None:
        last_modify_time = '0000-00-00 00:00:00.000'

    event_split_times = []
    with connection.cursor(DictCursor) as cursor:
        control_ids_format_str = _generate_in_format_str(len(control_ids))
        if ola_db_version >= 564:
            sql = 'SELECT' \
                  '  CONCAT(`SplitTimes`.`resultRaceIndividualNumber`,' \
                  '         "_",' \
                  '         `SplitTimes`.`passedCount`,' \
                  '         "_",' \
                  '         `SplitTimes`.`timingControl`) AS id,' \
                  '  `Controls`.`ID` AS controlCode,' \
                  '  `ElectronicPunchingCards`.`cardNumber` AS cardNumber,' \
                  '  `SplitTimes`.`passedTime`,' \
                  '  `SplitTimes`.`modifyDate`,' \
                  '  `Results`.`bibNumber`,' \
                  '  `RaceClasses`.`relayLeg`' \
                  ' FROM `SplitTimes`' \
                  '  LEFT JOIN `Results`' \
                  '         ON `SplitTimes`.`resultRaceIndividualNumber` = `Results`.`resultId`' \
                  '  LEFT JOIN `RaceClasses`' \
                  '         ON `Results`.`raceClassId` = `RaceClasses`.`raceClassId`' \
                  '  LEFT JOIN `ElectronicPunchingCards`' \
                  '         ON `Results`.`electronicPunchingCardId` = `ElectronicPunchingCards`.`cardId`' \
                  '  LEFT JOIN `Controls`' \
                  '         ON `SplitTimes`.`timingControl` = `Controls`.`controlId`' \
                  '  LEFT JOIN `EventRaces`' \
                  '         ON `RaceClasses`.`eventRaceId` = `EventRaces`.`eventRaceId`' \
                  ' WHERE `EventRaces`.`eventId` = %s' \
                  '   AND `EventRaces`.`eventRaceId` = %s' \
                  '   AND `Controls`.`ID` IN ({})' \
                  '   AND `SplitTimes`.`modifyDate` >= %s' \
                  ' ORDER BY' \
                  '  `SplitTimes`.`modifyDate` ASC' \
                  ';'.format(control_ids_format_str)
        else:
            sql = 'SELECT' \
                  '  CONCAT(`SplitTimes`.`resultRaceIndividualNumber`,' \
                  '         "_",' \
                  '         `SplitTimes`.`splitTimeControlId`,' \
                  '         "_",' \
                  '         `SplitTimes`.`passedCount`) AS id,' \
                  '  `Controls`.`ID` AS controlCode,' \
                  '  `ElectronicPunchingCards`.`cardNumber` AS cardNumber,' \
                  '  `SplitTimes`.`passedTime`,' \
                  '  `SplitTimes`.`modifyDate`,' \
                  '  `Results`.`bibNumber`,' \
                  '  `RaceClasses`.`relayLeg`' \
                  ' FROM `SplitTimes`' \
                  '  LEFT JOIN `Results`' \
                  '         ON `SplitTimes`.`resultRaceIndividualNumber` = `Results`.`resultId`' \
                  '  LEFT JOIN `RaceClasses`' \
                  '         ON `Results`.`raceClassId` = `RaceClasses`.`raceClassId`' \
                  '  LEFT JOIN `ElectronicPunchingCards`' \
                  '         ON `Results`.`electronicPunchingCardId` = `ElectronicPunchingCards`.`cardId`' \
                  '  LEFT JOIN `SplitTimeControls`' \
                  '         ON `SplitTimes`.`splitTimeControlId` = `SplitTimeControls`.`splitTimeControlId`' \
                  '  LEFT JOIN `Controls`' \
                  '         ON `SplitTimeControls`.`timingControl` = `Controls`.`controlId`' \
                  '  LEFT JOIN `EventRaces`' \
                  '         ON `SplitTimeControls`.`eventRaceId` = `EventRaces`.`eventRaceId`' \
                  ' WHERE `EventRaces`.`eventId` = %s' \
                  '   AND `EventRaces`.`eventRaceId` = %s' \
                  '   AND `Controls`.`ID` IN ({})' \
                  '   AND `SplitTimes`.`modifyDate` >= %s' \
                  ' ORDER BY' \
                  '  `SplitTimes`.`modifyDate` ASC' \
                  ';'.format(control_ids_format_str)
        args = [event_id, event_race_id]
        args.extend(control_ids)
        args.append(last_modify_time)
        cursor.execute(sql, args)
        event_split_times.extend(cursor.fetchall())
        logging.getLogger(LOGGER_NAME).debug('Event split times data: %s', event_split_times)
    return event_split_times


class _OlaMySqlMeta(type(ConfigConsumer), type(Singleton)):
    pass


class OlaMySql(ConfigConsumer, Singleton, metaclass=_OlaMySqlMeta):
    """
    Util for interacting with the OLA MySql Database.
    """

    CONFIG_SECTION_OLA_MYSQL = __qualname__

    CONFIG_OPTION_HOST = ConfigOptionDefinition(
        name='Host',
        display_name='Host',
        value_type=str,
        description='Host where the database server is located.',
        mandatory=True,
        validator=is_hostname_or_ip,
    )

    CONFIG_OPTION_USER = ConfigOptionDefinition(
        name='User',
        display_name='User',
        value_type=str,
        description='The username to log in as.',
        mandatory=True,
    )

    CONFIG_OPTION_PASSWORD = ConfigOptionDefinition(
        name='Password',
        display_name='Password',
        value_type=str,
        description='The password to use.',
    )

    CONFIG_OPTION_DATABASE = ConfigOptionDefinition(
        name='Database',
        display_name='Database',
        value_type=str,
        description='The database to use.',
        mandatory=True,
    )

    CONFIG_OPTION_EVENT = ConfigOptionDefinition(
        name='Event',
        display_name='Event Id',
        value_type=int,
        description='The Event in the Database to use.',
        mandatory=True,
    )

    CONFIG_OPTION_EVENT_RACE = ConfigOptionDefinition(
        name='EventRace',
        display_name='Event Race Id',
        value_type=int,
        description='The Event Race in the Database to use.',
        mandatory=True,
    )

    OLA_MYSQL_CONFIG_SECTION_DEFINITION = ConfigSectionDefinition(
        name=CONFIG_SECTION_OLA_MYSQL,
        display_name='OLA MySQL Database',
        option_definitions=[
            CONFIG_OPTION_HOST,
            CONFIG_OPTION_USER,
            CONFIG_OPTION_PASSWORD,
            CONFIG_OPTION_DATABASE,
            CONFIG_OPTION_EVENT,
            CONFIG_OPTION_EVENT_RACE,
        ],
        enable_type=ConfigSectionEnableType.IF_REQUIRED,
        sort_key_prefix=20,
    )

    MYSQL_CONNECTION_VERIFIER = ConfigVerifierDefinition(
        function=_verify_connection_parameters,
        parameters=[
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_OLA_MYSQL,
                option_definition=CONFIG_OPTION_HOST,
            ),
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_OLA_MYSQL,
                option_definition=CONFIG_OPTION_USER,
            ),
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_OLA_MYSQL,
                option_definition=CONFIG_OPTION_PASSWORD,
            ),
        ],
        message='Unable to connect to the MySQL Server.',
    )

    CONFIG_OPTION_PASSWORD.set_verifier(MYSQL_CONNECTION_VERIFIER)

    MYSQL_DATABASE_SELECTOR = ConfigSelectorDefinition(
        function=_select_database,
        parameters=[
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_OLA_MYSQL,
                option_definition=CONFIG_OPTION_HOST,
            ),
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_OLA_MYSQL,
                option_definition=CONFIG_OPTION_USER,
            ),
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_OLA_MYSQL,
                option_definition=CONFIG_OPTION_PASSWORD,
            ),
        ],
        message='Unable to find any databases.',
    )

    CONFIG_OPTION_DATABASE.set_selector(MYSQL_DATABASE_SELECTOR)

    MYSQL_DATABASE_VERIFIER = ConfigVerifierDefinition(
        function=_verify_database,
        parameters=[
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_OLA_MYSQL,
                option_definition=CONFIG_OPTION_HOST,
            ),
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_OLA_MYSQL,
                option_definition=CONFIG_OPTION_USER,
            ),
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_OLA_MYSQL,
                option_definition=CONFIG_OPTION_PASSWORD,
            ),
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_OLA_MYSQL,
                option_definition=CONFIG_OPTION_DATABASE,
            ),
        ],
        message='The database does not exist or is not a OLA database.',
    )

    CONFIG_OPTION_DATABASE.set_verifier(MYSQL_DATABASE_VERIFIER)

    MYSQL_EVENT_SELECTOR = ConfigSelectorDefinition(
        function=_select_event,
        parameters=[
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_OLA_MYSQL,
                option_definition=CONFIG_OPTION_HOST,
            ),
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_OLA_MYSQL,
                option_definition=CONFIG_OPTION_USER,
            ),
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_OLA_MYSQL,
                option_definition=CONFIG_OPTION_PASSWORD,
            ),
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_OLA_MYSQL,
                option_definition=CONFIG_OPTION_DATABASE,
            ),
            EventFormType.RELAY,
        ],
        message='Unable to find any Relay events.',
    )

    CONFIG_OPTION_EVENT.set_selector(MYSQL_EVENT_SELECTOR)

    MYSQL_EVENT_VERIFIER = ConfigVerifierDefinition(
        function=_verify_event,
        parameters=[
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_OLA_MYSQL,
                option_definition=CONFIG_OPTION_HOST,
            ),
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_OLA_MYSQL,
                option_definition=CONFIG_OPTION_USER,
            ),
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_OLA_MYSQL,
                option_definition=CONFIG_OPTION_PASSWORD,
            ),
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_OLA_MYSQL,
                option_definition=CONFIG_OPTION_DATABASE,
            ),
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_OLA_MYSQL,
                option_definition=CONFIG_OPTION_EVENT,
            ),
            EventFormType.RELAY
        ],
        message='The event does not exist in the selected database or is not a Relay event.',
    )

    CONFIG_OPTION_EVENT.set_verifier(MYSQL_EVENT_VERIFIER)

    MYSQL_EVENT_RACE_SELECTOR = ConfigSelectorDefinition(
        function=_select_event_race,
        parameters=[
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_OLA_MYSQL,
                option_definition=CONFIG_OPTION_HOST,
            ),
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_OLA_MYSQL,
                option_definition=CONFIG_OPTION_USER,
            ),
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_OLA_MYSQL,
                option_definition=CONFIG_OPTION_PASSWORD,
            ),
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_OLA_MYSQL,
                option_definition=CONFIG_OPTION_DATABASE,
            ),
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_OLA_MYSQL,
                option_definition=CONFIG_OPTION_EVENT,
            ),
        ],
        message='Unable to find any event races.',
    )

    CONFIG_OPTION_EVENT_RACE.set_selector(MYSQL_EVENT_RACE_SELECTOR)

    MYSQL_EVENT_RACE_VERIFIER = ConfigVerifierDefinition(
        function=_verify_event_race,
        parameters=[
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_OLA_MYSQL,
                option_definition=CONFIG_OPTION_HOST,
            ),
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_OLA_MYSQL,
                option_definition=CONFIG_OPTION_USER,
            ),
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_OLA_MYSQL,
                option_definition=CONFIG_OPTION_PASSWORD,
            ),
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_OLA_MYSQL,
                option_definition=CONFIG_OPTION_DATABASE,
            ),
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_OLA_MYSQL,
                option_definition=CONFIG_OPTION_EVENT,
            ),
            ConfigSectionOptionDefinition(
                section_name=CONFIG_SECTION_OLA_MYSQL,
                option_definition=CONFIG_OPTION_EVENT_RACE,
            ),
        ],
        message='The event race does not exist in the selected event.',
    )

    CONFIG_OPTION_EVENT_RACE.set_verifier(MYSQL_EVENT_RACE_VERIFIER)

    Config.register_config_section_definition(OLA_MYSQL_CONFIG_SECTION_DEFINITION)

    @classmethod
    def config_section_definition(cls) -> ConfigSectionDefinition:
        return cls.OLA_MYSQL_CONFIG_SECTION_DEFINITION

    def __repr__(self) -> str:
        return f'OlaMySQL(host={self.host},' \
               f' user={self.user},' \
               f' database={self.database},' \
               f' ola_db_version={self.ola_db_version},' \
               f' event={self.event},' \
               f' event_race={self.event_race})'

    def __str__(self) -> str:
        return repr(self)

    def __init__(self):
        super().__init__()

        if LOGGER_NAME != self.__class__.__name__:
            raise ValueError('LOGGER_NAME not correct: {} vs {}'.format(LOGGER_NAME, self.__class__.__name__))

        self.logger = logging.getLogger(self.__class__.__name__)

        self.host = None
        self.user = None
        self.password = None
        self.database = None
        self.event = None
        self.event_race = None

        self.ola_db_version = None
        self.is_relay = None

        self._parse_config()

        self.logger.debug(self)

    def config_updated(self, section_names: List[str]):
        self._parse_config()

    def _parse_config(self):
        config_section = Config().get_section(self.CONFIG_SECTION_OLA_MYSQL)

        self.host = self.CONFIG_OPTION_HOST.get_value(config_section)

        self.user = self.CONFIG_OPTION_USER.get_value(config_section)

        self.password = self.CONFIG_OPTION_PASSWORD.get_value(config_section)

        self.database = self.CONFIG_OPTION_DATABASE.get_value(config_section)

        self.event = self.CONFIG_OPTION_EVENT.get_value(config_section)

        self.event_race = self.CONFIG_OPTION_EVENT_RACE.get_value(config_section)

        self.ola_db_version = None
        self.is_relay = None

    def get_database_names(self) -> List[str]:
        self.logger.debug('get_database_names')

        connection = connect(self.host, self.user, self.password)
        with connection:
            database_names = get_database_names(connection)
        return database_names

    def _connect(self):
        self.logger.debug('_connect')

        if not self.database:
            self.logger.error('The value for "database" in the "%s" section is missing.',
                              self.CONFIG_SECTION_OLA_MYSQL)
            raise ValueError('The value for "database" in the "{}" section is missing.'
                             .format(self.CONFIG_SECTION_OLA_MYSQL))

        connection = connect(self.host, self.user, self.password, self.database)

        if self.ola_db_version is None:
            self.ola_db_version = get_ola_db_version(connection)
            if self.ola_db_version == 0:
                self.logger.error('The database "%s" is not a OLA database.', self.database)
                raise ValueError('The database "{}" is not a OLA database.'.format(self.database))

        if self.is_relay is None:
            if self.event is not None:
                self.is_relay = is_relay_event(connection, event_id=self.event)

        return connection

    def get_ola_db_version(self) -> int:
        self.logger.debug('get_ola_db_version')

        if self.ola_db_version is None:
            connection = self._connect()
            connection.close()
        return self.ola_db_version

    def get_events(self, event_forms: EventForm or EventFormType = None) -> List[Dict[str, Any]]:
        self.logger.debug('get_events')

        connection = self._connect()
        with connection:
            events = get_events(connection, event_forms)
        return events

    def get_event_races(self) -> List[Dict[str, Any]]:
        self.logger.debug('get_event_races')

        if self.event is None:
            raise ValueError('A Event needs to be selected first')

        connection = self._connect()
        with connection:
            event_races = get_event_races(connection, self.event)
        return event_races

    def get_event_classes(self) -> List[Dict[str, Any]]:
        self.logger.debug('get_event_classes')
        if self.event is None:
            raise ValueError('A Event needs to be selected first')
        event_classes = []
        connection = self._connect()
        with connection:
            with connection.cursor(DictCursor) as cursor:
                sql = 'SELECT' \
                      '  `EventClasses`.`eventClassId`,' \
                      '  `EventClasses`.`baseClassId`,' \
                      '  `EventClasses`.`name`,' \
                      '  `EventClasses`.`shortName` AS `class`,' \
                      '  `EventClasses`.`eventId`,' \
                      '  `EventClasses`.`classStatus`,' \
                      '  `EventClasses`.`collectedTo`,' \
                      '  `CollectedToEventClasses`.`shortName` AS `collectedToName`,' \
                      '  `EventClasses`.`dividedFrom`,' \
                      '  `EventClasses`.`finalFromClassId`,' \
                      '  `EventClasses`.`lowAge`,' \
                      '  `EventClasses`.`highAge`,' \
                      '  `EventClasses`.`sex`,' \
                      '  `EventClasses`.`numberInTeam`,' \
                      '  `EventClasses`.`teamEntry`,' \
                      '  `EventClasses`.`maxNumberInClass`,' \
                      '  `EventClasses`.`numberOfVacancies`,' \
                      '  `EventClasses`.`divideClassMethod`,' \
                      '  `EventClasses`.`actualForRanking`,' \
                      '  `EventClasses`.`noTimePresentation`,' \
                      '  `EventClasses`.`substituteClassId`,' \
                      '  `EventClasses`.`notQualifiedSubstitutionClassId`,' \
                      '  `EventClasses`.`classTypeId`,' \
                      '  `ClassTypes`.`name` AS `classTypeName`,' \
                      '  `EventClasses`.`normalizedClass`,' \
                      '  `EventClasses`.`numberOfPrizesTotal`,' \
                      '  `EventClasses`.`noTotalResult`,' \
                      '  `EventClasses`.`allowEventRaceEntry`,' \
                      '  `EventClasses`.`allowCardReusage`,' \
                      '  `EventClasses`.`sequence`,' \
                      '  `EventClasses`.`allowNoTimePresentationEntries`' \
                      ' FROM `EventClasses`' \
                      '  LEFT JOIN `EventClasses` AS `CollectedToEventClasses`' \
                      '         ON `CollectedToEventClasses`.`baseClassId` = `EventClasses`.`collectedTo`' \
                      '  LEFT JOIN `ClassTypes`' \
                      '         ON `EventClasses`.`classTypeId` = `ClassTypes`.`classTypeId`' \
                      ' WHERE `EventClasses`.`eventId` = %s' \
                      '   AND (`CollectedToEventClasses`.`eventId` = %s' \
                      '        OR `CollectedToEventClasses`.`eventId` IS NULL)' \
                      ' ORDER BY' \
                      '  `EventClasses`.`sequence`' \
                      ';'
                cursor.execute(sql, (self.event, self.event))
                event_classes.extend(cursor.fetchall())
                self.logger.debug('Event classes data: %s', event_classes)
        return event_classes

    def get_event_race_results(self,
                               event_class_ids: List[str],
                               runner_statuses: List[str] or None = None) -> List[Dict[str, Any]]:
        self.logger.debug('get_event_results')
        if self.event is None:
            raise ValueError('A Event needs to be selected first')
        if self.event_race is None:
            raise ValueError('A Event Race needs to be selected first')
        if runner_statuses is None:
            runner_statuses = ['passed']
        event_results = []
        connection = self._connect()
        with connection:
            with connection.cursor(DictCursor) as cursor:
                event_class_ids_format_str = _generate_in_format_str(len(event_class_ids))
                runner_statuses_format_str = _generate_in_format_str(len(runner_statuses))
                sql = 'SELECT' \
                      '  `Results`.`bibNumber`,' \
                      '  `Results`.`individualCourseId`,' \
                      '  `Results`.`rawDataFromElectronicPunchingCardsId`,' \
                      '  `Results`.`modifyDate`,' \
                      '  `Results`.`totalTime`,' \
                      '  `Results`.`position`,' \
                      '  `Persons`.`familyname` as `lastname`,' \
                      '  `Persons`.`firstname` as `firstname`,' \
                      '  `Organisations`.`shortname` as `clubname`,' \
                      '  `EventClasses`.`shortName`,' \
                      '  `Results`.`runnerStatus`,' \
                      '  `Results`.`entryid`,' \
                      '  `Results`.`allocatedStartTime`,' \
                      '  `Results`.`starttime`,' \
                      '  `Entries`.`allocationControl`,' \
                      '  `Entries`.`allocationEntryId`' \
                      ' FROM `Results`' \
                      '   INNER JOIN `Entries`' \
                      '           ON `Results`.`entryId` = `Entries`.`entryId`' \
                      '   INNER JOIN `Persons`' \
                      '           ON `Entries`.`competitorId` = `Persons`.`personId`' \
                      '   LEFT JOIN `Organisations`' \
                      '           ON `Persons`.`defaultOrganisationId` = `Organisations`.`organisationId`' \
                      '   INNER JOIN `RaceClasses`' \
                      '           ON `Results`.`raceClassID` = `RaceClasses`.`raceClassId`' \
                      '   INNER JOIN `EventClasses`' \
                      '           ON `RaceClasses`.`eventClassId` = `EventClasses`.`eventClassId`' \
                      '  WHERE `RaceClasses`.`eventRaceId` = %s' \
                      '    AND `EventClasses`.`eventId` = %s' \
                      '    AND `EventClasses`.`eventClassId` IN ({})' \
                      '    AND `RaceClasses`.`raceClassStatus` NOT IN (\'notUsed\')' \
                      '    AND `Results`.`runnerStatus` IN ({})' \
                      ';'.format(event_class_ids_format_str, runner_statuses_format_str)
                args = [self.event_race, self.event]
                args.extend(event_class_ids)
                args.extend(runner_statuses)
                cursor.execute(sql, args)
                event_results.extend(cursor.fetchall())
                self.logger.debug('Event results data: %s', event_results)
        return event_results

    def get_event_race_split_time_controls(self) -> List[Dict[str, Any]]:
        self.logger.debug('get_event_split_time_controls')
        if self.event is None:
            raise ValueError('A Event needs to be selected first')
        if self.event_race is None:
            raise ValueError('A Event Race needs to be selected first')

        connection = self._connect()
        with connection:
            split_time_controls = get_event_race_split_time_controls(connection,
                                                                     ola_db_version=self.ola_db_version,
                                                                     is_relay=self.is_relay,
                                                                     event_race_id=self.event_race)
        return split_time_controls

    def get_event_race_split_times(self,
                                   control_ids: List[int],
                                   last_modify_time: str or None = None) -> List[Dict[str, Any]]:
        self.logger.debug('get_event_race_split_times')
        if self.event is None:
            raise ValueError('A Event needs to be selected first')
        if self.event_race is None:
            raise ValueError('A Event Race needs to be selected first')

        if last_modify_time is None:
            last_modify_time = '0000-00-00 00:00:00.000'

        connection = self._connect()
        with connection:
            event_split_times = get_event_race_split_times(connection,
                                                           ola_db_version=self.ola_db_version,
                                                           event_id=self.event,
                                                           event_race_id=self.event_race,
                                                           control_ids=control_ids,
                                                           last_modify_time=last_modify_time)
        return event_split_times

    def get_event_race_pre_warning_data(self, card_number: str) -> Dict[str, Any] or None:
        self.logger.debug('get_event_pre_warning_data')
        if self.event is None:
            raise ValueError('A Event needs to be selected first')
        if self.event_race is None:
            raise ValueError('A Event Race needs to be selected first')
        connection = self._connect()
        with connection:
            with connection.cursor(DictCursor) as cursor:
                sql = 'SELECT' \
                      '  `Results`.`bibNumber`,' \
                      '  `RaceClasses`.`relayLeg`' \
                      ' FROM `Results`' \
                      '  LEFT JOIN `RaceClasses`' \
                      '         ON `Results`.`raceClassId` = `RaceClasses`.`raceClassId`' \
                      '  LEFT JOIN `EventRaces`' \
                      '         ON `RaceClasses`.`eventRaceId` = `EventRaces`.`eventRaceId`' \
                      '  LEFT JOIN `ElectronicPunchingCards`' \
                      '         ON `Results`.`electronicPunchingCardId` = `ElectronicPunchingCards`.`cardId`' \
                      ' WHERE `EventRaces`.`eventId` = %s' \
                      '   AND `EventRaces`.`eventRaceId` = %s' \
                      '   AND `ElectronicPunchingCards`.`cardNumber` = %s' \
                      ' ORDER BY' \
                      '  `Results`.`bibNumber`,' \
                      '  `RaceClasses`.`relayLeg`' \
                      ';'
                args = [self.event, self.event_race, card_number]
                cursor.execute(sql, args)
                event_pre_warning_data = cursor.fetchall()
                self.logger.debug('Event Pre-Warning data: %s', event_pre_warning_data)
                if len(event_pre_warning_data) == 0:
                    return None
                if len(event_pre_warning_data) == 1:
                    return event_pre_warning_data[0]
                else:
                    self.logger.debug('Too many matches, skipping!')
                    return None
