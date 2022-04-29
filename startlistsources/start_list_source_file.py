# -*- coding: utf-8 -*-

import logging
from pathlib import Path
from typing import List, Dict
from xml.etree import ElementTree
from zipfile import ZipFile

from natsort import natsorted
from watchdog.events import LoggingEventHandler
from watchdog.observers import Observer
import wx

from utils.config import ConfigSectionDefinition, ConfigOptionDefinition, Config
from utils.config_definitions import ConfigSectionEnableType, ConfigVerifierDefinition, ConfigSectionOptionDefinition, \
    ConfigSelectorDefinition, SelectionResult, SelectionData, VerificationResult
from utils.config_selection import select_file
from utils.sound import Sound, SoundFolder, verify_sound
from validators.path_validators import file_exists
from ._base import _StartListSourceBase


LOGGER_NAME = 'StartListSourceFile'

DEFAULT_START_LIST_FILE_FOLDER = Path(__file__).resolve().parent.parent.absolute()


def _select_start_list_file(parent: wx.Window, prev_file: str or Path = None) -> str or False:

    if prev_file is None:
        default_dir = DEFAULT_START_LIST_FILE_FOLDER.as_posix()
    elif issubclass(type(prev_file), Path):
        default_dir = prev_file.resolve().parent.absolute().as_posix()
    else:
        default_dir = Path(prev_file).resolve().parent.absolute().as_posix()

    selected = select_file(parent=parent,
                           message='Select a Start List File',
                           default_dir=default_dir,
                           wildcard='IOFv3 Start List files (*.xml,*.zip)|*.xml;*.zip')
    if selected is not None:
        result = SelectionResult()

        selected_path = Path(selected)
        try:
            selected_path = selected_path.relative_to(DEFAULT_START_LIST_FILE_FOLDER)
            selected_str = selected_path.as_posix()
        except ValueError:
            selected_str = selected

        result.add_value(SelectionData(selected_str, selected_str))

        return result
    else:
        return False


def _get_data(element, selector, ns):
    data = element.find(selector, ns)
    if data is not None:
        return data.text
    else:
        return None


def _read_start_list(start_list_file: str):
    if start_list_file.lower().endswith('.zip'):
        archive = ZipFile(start_list_file, 'r')
        data = archive.read('SOFTSTRT.XML')
    else:
        f = open(start_list_file, 'r', encoding='windows-1252')
        data = f.read()

    start_list = ElementTree.fromstring(data)

    if start_list.tag != '{http://www.orienteering.org/datastandard/3.0}StartList':
        raise ValueError('Start List File is not a valid IOFv3 Start List.')

    ns = {'ns': 'http://www.orienteering.org/datastandard/3.0'}

    event_id = _get_data(start_list, 'ns:Event/ns:Id', ns)
    event_name = _get_data(start_list, 'ns:Event/ns:Name', ns)
    event_date = _get_data(start_list, 'ns:Event/ns:StartTime/ns:Date', ns)
    organiser_id = _get_data(start_list, 'ns:Event/ns:Organiser/ns:Id', ns)
    organiser_name = _get_data(start_list, 'ns:Event/ns:Organiser/ns:Name', ns)

    logging.getLogger(LOGGER_NAME).debug('_read_start_list - Event: %s (%s) %s',
                                         str(event_name), str(event_id), str(event_date))
    logging.getLogger(LOGGER_NAME).debug('_read_start_list - Organiser: %s (%s)',
                                         str(organiser_name), str(organiser_id))

    team_names = dict()
    teams = dict()
    runners = dict()

    xml_teams = start_list.findall('ns:ClassStart/ns:TeamStart', ns)
    for xml_team in xml_teams:
        team_name = _get_data(xml_team, 'ns:Name', ns)
        team_bib_number = _get_data(xml_team, 'ns:BibNumber', ns)
        team_names[team_bib_number] = team_name

        team = dict()
        team_members = xml_team.findall('ns:TeamMemberStart', ns)
        for team_member in team_members:
            team_member_id = _get_data(team_member, 'ns:Person/ns:Id', ns)
            team_member_name_family = _get_data(team_member, 'ns:Person/ns:Name/ns:Family', ns)
            team_member_name_given = _get_data(team_member, 'ns:Person/ns:Name/ns:Given', ns)
            team_member_leg = _get_data(team_member, 'ns:Start/ns:Leg', ns)
            team_member_leg_order = _get_data(team_member, 'ns:Start/ns:LegOrder', ns)
            team_member_bib_number = _get_data(team_member, 'ns:Start/ns:BibNumber', ns)
            team_member_control_card = _get_data(team_member, 'ns:Start/ns:ControlCard', ns)
            if team_member_control_card is not None:
                runners[team_member_control_card] = {'id': team_member_id,
                                                     'family': team_member_name_family,
                                                     'given': team_member_name_given,
                                                     'leg': team_member_leg,
                                                     'leg_order': team_member_leg_order,
                                                     'team_bib_number': team_bib_number,
                                                     'bib_number': team_member_bib_number,
                                                     'control_card': team_member_control_card}
                if team_member_leg not in team:
                    team[team_member_leg] = dict()
                leg = team[team_member_leg]
                leg[team_member_leg_order] = runners[team_member_control_card]

        team = natsorted(team.items())
        teams[team_bib_number] = team
    # for leg in team.items():
    # 	for subleg in leg:
    #

    team_names = natsorted(team_names.items())
    teams = natsorted(teams.items())

    logging.getLogger(LOGGER_NAME).debug('_read_start_list - Teams: %s', str(team_names))
    logging.getLogger(LOGGER_NAME).debug('_read_start_list - Runners: %s', str(runners))

    return team_names, teams, runners


def _verify_start_list_file(start_list_file: Path):
    try:
        if start_list_file is None:
            raise ValueError('Start List File must be configured.')

        if not start_list_file.is_absolute():
            start_list_file = DEFAULT_START_LIST_FILE_FOLDER / start_list_file

        (team_names, teams, runners) = _read_start_list(start_list_file=start_list_file.as_posix())

        if len(team_names) == 0:
            return VerificationResult(message='No Teams in the Start List File.')

        return VerificationResult(message=f'{len(team_names)} Teams in the Start List File.')
    except Exception as e:
        logging.getLogger(LOGGER_NAME).debug('_verify_start_list_file: %s', e)
        return VerificationResult(message=str(e), status=False)


class StartListSourceFile(_StartListSourceBase, LoggingEventHandler):
    """
    A Start List Source that reads the start list from a file and monitors it for changes.
    """

    name = __qualname__

    display_name = 'File Start List Source'

    description = 'Reads a start list file following the ' \
                  '<a href="https://orienteering.sport/iof/it/data-standard-3-0/">IOF 3.0 Data Standard</a> ' \
                  'and uses it to look up the team bib number and relay leg. ' \
                  'Files generated by <a href="https://www.svenskorientering.se/Arrangera/itochtavlings-' \
                  'administration/OLAtidtagnings-program/">OLA</a> and ' \
                  '<a href="https://sportsoftware.de/orienteering/os">OS2010</a> have been tested.' \
                  'The file will be monitored and re-read if it changes.'

    CONFIG_OPTION_START_LIST_FILE = ConfigOptionDefinition(
        name='StartListFile',
        display_name='Start List File',
        value_type=Path,
        description='The path on the file system where the start list file is located.',
        mandatory=True,
        validator=file_exists,
    )

    CONFIG_OPTION_START_LIST_UPDATE_SOUND_FILE = ConfigOptionDefinition(
        name='StartListUpdateSoundFile',
        display_name='Start List Update Sound',
        value_type=Path,
        description='The path to the sound file to use when the start list is updated.',
        default_value=Path('half_ding.mp3'),
        valid_values_gen=SoundFolder().get_all_sounds,
    )

    START_LIST_SOURCE_FILE_CONFIG_SECTION_DEFINITION = ConfigSectionDefinition(
        name=name,
        display_name=display_name,
        option_definitions=[
            CONFIG_OPTION_START_LIST_FILE,
            CONFIG_OPTION_START_LIST_UPDATE_SOUND_FILE,
        ],
        enable_type=ConfigSectionEnableType.IF_ENABLED,
        sort_key_prefix=40,
    )

    START_LIST_FILE_START_LIST_FILE_SELECTOR = ConfigSelectorDefinition(
        function=_select_start_list_file,
        parameters=[
            ConfigSectionOptionDefinition(
                section_name=name,
                option_definition=CONFIG_OPTION_START_LIST_FILE,
            ),
        ],
        message='Unable to select any Start List File.',
    )

    CONFIG_OPTION_START_LIST_FILE.set_selector(START_LIST_FILE_START_LIST_FILE_SELECTOR)

    START_LIST_SOURCE_FILE_START_LIST_FILE_VERIFIER = ConfigVerifierDefinition(
        function=_verify_start_list_file,
        parameters=[
            ConfigSectionOptionDefinition(
                section_name=name,
                option_definition=CONFIG_OPTION_START_LIST_FILE,
            ),
        ],
        message='The Start List File was not valid.',
    )

    CONFIG_OPTION_START_LIST_FILE.set_verifier(START_LIST_SOURCE_FILE_START_LIST_FILE_VERIFIER)

    START_LIST_SOURCE_FILE_CONFIG_SECTION_START_LIST_UPDATE_SOUND_VERIFIER = ConfigVerifierDefinition(
        function=verify_sound,
        parameters=[
            ConfigSectionOptionDefinition(
                section_name=name,
                option_definition=CONFIG_OPTION_START_LIST_UPDATE_SOUND_FILE,
            ),
        ],
        message='The selected sound could not be played.',
    )

    CONFIG_OPTION_START_LIST_UPDATE_SOUND_FILE.set_verifier(
        START_LIST_SOURCE_FILE_CONFIG_SECTION_START_LIST_UPDATE_SOUND_VERIFIER)

    Config.register_config_section_definition(START_LIST_SOURCE_FILE_CONFIG_SECTION_DEFINITION)

    @classmethod
    def config_section_definition(cls) -> ConfigSectionDefinition:
        return cls.START_LIST_SOURCE_FILE_CONFIG_SECTION_DEFINITION

    def __repr__(self) -> str:
        return f'StartListSourceFile(running={self._running},' \
               f' start_list_file={self.start_list_file},' \
               f' start_list_update_sound_file={self.start_list_update_sound_file})'

    def __str__(self) -> str:
        return repr(self)

    def __init__(self):
        self.observer = None

        if LOGGER_NAME != self.__class__.__name__:
            raise ValueError('LOGGER_NAME not correct: {} vs {}'.format(LOGGER_NAME, self.__class__.__name__))

        self.logger = logging.getLogger(self.__class__.__name__)

        super().__init__()

        self.start_list_file = None
        self.start_list_update_sound_file = None

        self.team_names = dict()
        self.teams = dict()
        self.runners = dict()

        self._running = False

        self.logger.debug(self)

        self.observer = Observer()
        self.observer.name = 'StartListFileObserverThread'

    def __del__(self):
        self.stop()

    def start(self):
        self._running = True
        self.update()

    def stop(self):
        self._running = False
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join()

    def is_running(self) -> bool:
        return self._running

    def get_config_section_definitions(self) -> List[ConfigSectionDefinition]:
        """Returns a list of configuration section definitions.

        :return: A list of configuration section definitions
        :rtype: List[ConfigSectionDefinition]
        """
        definitions = super().get_config_section_definitions()
        definitions.append(self.START_LIST_SOURCE_FILE_CONFIG_SECTION_DEFINITION)
        return definitions

    def on_modified(self, event):
        super().on_modified(event)

        src_path = event.src_path
        if src_path.endswith('~'):
            src_path = src_path[0:-1]
        if Path(src_path).resolve() == self.start_list_file:
            self._read_start_list()

    def config_updated(self, section_names: List[str]):
        self.update()

    def update(self):
        self._parse_config()
        self._read_start_list()

    def _parse_config(self):
        config_section = Config().get_section(self.name)

        self.observer.unschedule_all()

        start_list_file = self.CONFIG_OPTION_START_LIST_FILE.get_value(config_section)

        if start_list_file.is_file():
            self.start_list_file = start_list_file
        else:
            self.start_list_file = DEFAULT_START_LIST_FILE_FOLDER / start_list_file

        if not self.start_list_file.is_file():
            self.logger.error('The Start List file "%s" could not be found.', str(start_list_file))
            raise ValueError('The Start List file "{}" could not be found.'.format(str(start_list_file)))

        self.start_list_update_sound_file = self.CONFIG_OPTION_START_LIST_UPDATE_SOUND_FILE.get_value(config_section)

        self.observer.schedule(event_handler=self, path=self.start_list_file.parent.as_posix())
        if self._running and not self.observer.is_alive():
            self.observer.start()

    def _read_start_list(self):
        if self.start_list_file.as_posix().lower().endswith('.zip'):
            with ZipFile(self.start_list_file, 'r') as archive:
                data = archive.read('SOFTSTRT.XML')
        else:
            with open(self.start_list_file.as_posix(), 'r', encoding='windows-1252') as f:
                data = f.read()

        start_list = ElementTree.fromstring(data)

        if start_list.tag != '{http://www.orienteering.org/datastandard/3.0}StartList':
            self.logger.error('The Start List File (%s) is not a valid IOFv3 Start List.',
                              self.start_list_file.as_posix())
            raise ValueError('The Start List File ({}) is not a valid IOFv3 Start List.'.format(
                self.start_list_file.as_posix()))

        ns = {'ns': 'http://www.orienteering.org/datastandard/3.0'}

        event_id = _get_data(start_list, 'ns:Event/ns:Id', ns)
        event_name = _get_data(start_list, 'ns:Event/ns:Name', ns)
        event_date = _get_data(start_list, 'ns:Event/ns:StartTime/ns:Date', ns)
        organiser_id = _get_data(start_list, 'ns:Event/ns:Organiser/ns:Id', ns)
        organiser_name = _get_data(start_list, 'ns:Event/ns:Organiser/ns:Name', ns)

        if event_date is not None:
            self.competition_date = event_date

        self.logger.debug('Event: %s (%s) %s', str(event_name), str(event_id), str(event_date))
        self.logger.debug('Organiser: %s (%s)', str(organiser_name), str(organiser_id))

        self.team_names.clear()
        self.teams.clear()
        self.runners.clear()

        xml_teams = start_list.findall('ns:ClassStart/ns:TeamStart', ns)
        for xml_team in xml_teams:
            team_name = _get_data(xml_team, 'ns:Name', ns)
            team_bib_number = _get_data(xml_team, 'ns:BibNumber', ns)
            self.team_names[team_bib_number] = team_name

            team = dict()
            team_members = xml_team.findall('ns:TeamMemberStart', ns)
            for team_member in team_members:
                team_member_id = _get_data(team_member, 'ns:Person/ns:Id', ns)
                team_member_name_family = _get_data(team_member, 'ns:Person/ns:Name/ns:Family', ns)
                team_member_name_given = _get_data(team_member, 'ns:Person/ns:Name/ns:Given', ns)
                team_member_leg = _get_data(team_member, 'ns:Start/ns:Leg', ns)
                team_member_leg_order = _get_data(team_member, 'ns:Start/ns:LegOrder', ns)
                team_member_bib_number = _get_data(team_member, 'ns:Start/ns:BibNumber', ns)
                team_member_control_card = _get_data(team_member, 'ns:Start/ns:ControlCard', ns)
                if team_member_control_card is not None:
                    self.runners[team_member_control_card] = {'id': team_member_id,
                                                              'family': team_member_name_family,
                                                              'given': team_member_name_given,
                                                              'leg': team_member_leg,
                                                              'leg_order': team_member_leg_order,
                                                              'team_bib_number': team_bib_number,
                                                              'bib_number': team_member_bib_number,
                                                              'control_card': team_member_control_card}
                    if team_member_leg not in team:
                        team[team_member_leg] = dict()
                    leg = team[team_member_leg]
                    leg[team_member_leg_order] = self.runners[team_member_control_card]

            team = natsorted(team.items())
            self.teams[team_bib_number] = team
        # for leg in team.items():
        # 	for subleg in leg:
        #

        self.team_names = natsorted(self.team_names.items())
        self.teams = natsorted(self.teams.items())
        # self.start_list_file_time = stat(self.add_path(self.start_list_file)).st_mtime
        self.logger.debug('Teams: %s', str(self.team_names))
        self.logger.debug('Runners: %s', str(self.runners))

        Sound.play(self.start_list_update_sound_file)

    def lookup_from_card_number(self, card_number: str) -> Dict[str, str] or None:
        """Returns Bib-Number and Relay Leg for the provided Card Number.

        :param str card_number: The Card Number to look up.
        :return: A dict with the Bib-Number (bibNumber) and Relay Leg (relayLeg).
        :rtype: Dict[str, Str] or None
        """
        runner = self.runners.get(card_number)
        if runner is not None:
            team_bib_number = runner['team_bib_number']
            leg = runner['leg']
            return {'bibNumber': team_bib_number, 'relayLeg': leg}
        else:
            self.logger.warning('Not found: %s', card_number)
            return None
