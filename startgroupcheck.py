# -*- coding: utf-8 -*-
import logging
import re
from datetime import datetime
from typing import List, Dict, Any
# from xml.etree import ElementTree
# from zipfile import ZipFile

import pymysql.cursors

logger = logging.getLogger(__name__)

# Connect to the database
connection = pymysql.connect(host='192.168.2.111',
                             user='live',
                             password='live',
                             database='20210711havsoldag2',
                             cursorclass=pymysql.cursors.DictCursor)

event_id = 1
event_race_id = 1


def from_db(external_id: int) -> List[Dict[str, Any]]:
    results = []
    with connection.cursor() as cursor:
        # entries.competitorId is actually personId
        sql = 'SELECT' \
              '  `personids`.`externalId`,' \
              '   `results`.`bibNumber` AS `resultBibNumber`,' \
              '   `results`.`allocatedStartTime`,' \
              '   `results`.`startTime`,' \
              '   `results`.`electronicPunchingCardId`,' \
              '   `entries`.`sportIdentCCardNumber`,' \
              '   `entries`.`emitCCardNumber`,' \
              '   `entries`.`bibNumber` AS `entryBibNumber`,' \
              '   `persons`.`familyName`,' \
              '   `persons`.`firstName`,' \
              '   `organisations`.`name` AS `club`,' \
              '   `eventclasses`.`name` AS `class`' \
              ' FROM' \
              '  `results`,' \
              '  `entries`,' \
              '  `competitors`,' \
              '  `persons`,' \
              '  `personids`,' \
              '  `personidtypes`,' \
              '  `organisations`,' \
              '  `raceclasses`,' \
              '  `eventclasses`' \
              ' WHERE `results`.`entryId`=`entries`.`entryId`' \
              '   AND `entries`.`competitorId`=`competitors`.`personId`' \
              '   AND `competitors`.`personId`=`persons`.`personId`' \
              '   AND `persons`.`personId`=`personids`.`personId`' \
              '   AND `personids`.`externalId`=%s' \
              '   AND `personids`.`personIdsTypeId`=`personidtypes`.`personIdsTypeId`' \
              '   AND `personidtypes`.`name`=\'Eventor\'' \
              '   AND `competitors`.`organisationId`=`organisations`.`organisationId`' \
              '   AND `results`.`raceClassId`=`raceclasses`.`raceClassId`' \
              '   AND `raceclasses`.`eventClassId`=`eventclasses`.`eventClassId`' \
              ';'
        cursor.execute(sql, (external_id,))
        results.extend(cursor.fetchall())
        print('results: {}'.format(results))
    return results


"""def get_competitor_details(entry_id: str) -> List[Dict[str, Any]]:
    result = None
    with connection.cursor() as cursor:
        # entries.competitorId is actually personId
        sql = 'SELECT' \
              '  `Results`.`allocatedStartTime`,' \
              '  `Results`.`startTime`,' \
              '  `ElectronicPunchingCards`.`cardNumber`,' \
              '  `ElectronicPunchingCards`.`electronicPunchingCardType`,' \
              '  `Persons`.`familyName`,' \
              '  `Persons`.`firstName`,' \
              '  `Organisations`.`name` AS `club`,' \
              '  `EventClasses`.`name` AS `class`' \
              ' FROM' \
              '  `Results`' \
              '  INNER JOIN `Entries` ON `Results`.`entryId`=`Entries`.`entryId`' \
              '  INNER JOIN `Persons` ON `Persons`.`personId`=`Entries`.`competitorId`' \
              '  LEFT JOIN `Organisations` ON `Organisations`.`organisationId`=`Persons`.`defaultOrganisationId`' \
              '  LEFT JOIN `ElectronicPunchingCards`' \
              '    ON `ElectronicPunchingCards`.`cardId`=`Results`.`electronicPunchingCardId`' \
              '  LEFT JOIN `RaceClasses` ON `Results`.`raceClassId`=`RaceClasses`.`raceClassId`' \
              '  LEFT JOIN `EventClasses` ON `RaceClasses`.`eventClassId`=`EventClasses`.`eventClassId`' \
              'WHERE `Results`.`entryId`=%s' \
              ';'
        cursor.execute(sql, (entry_id,))
        results = cursor.fetchall()
        # print('results: {}'.format(results))
        if len(results) > 1:
            raise ValueError('Too many results matched {}: {}'.format(len(results), results))
        elif len(results) == 1:
            result = results[0]
    return result"""


def get_combined_competitor_data():
    logger.debug('get_combined_competitor_data')
    combined_competitor_data = []
    with connection.cursor() as cursor:
        sql = 'SELECT' \
              '  `Results`.`resultId`,' \
              '  `Results`.`raceClassId` AS `rRaceClassId`,' \
              '  `Results`.`allocatedStartTime`,' \
              '  `Results`.`startTime`,' \
              '  `Entries`.`entryId`,' \
              '  `Entries`.`acceptedEventClassId`,' \
              '  `EntrysClasses`.`ordered`,' \
              '  `EntrysClasses`.`classId`,' \
              '  `ElectronicPunchingCards`.`cardNumber`,' \
              '  `ElectronicPunchingCards`.`electronicPunchingCardType`,' \
              '  `Persons`.`familyName`,' \
              '  `Persons`.`firstName`,' \
              '  `Organisations`.`name` AS `club`,' \
              '  `EventClasses`.`name` AS `class`,' \
              '  `Services`.`serviceId`,' \
              '  `Services`.`name` AS `serviceName`,' \
              '  `Services`.`comment` AS `serviceComment`' \
              ' FROM' \
              '  `Results`' \
              '  INNER JOIN `Entries`' \
              '          ON `Results`.`entryId`=`Entries`.`entryId`' \
              '  INNER JOIN `Persons`' \
              '          ON `Persons`.`personId`=`Entries`.`competitorId`' \
              '  LEFT JOIN `EntrysClasses`' \
              '         ON `Entries`.`entryId`=`EntrysClasses`.`entryId`' \
              '  LEFT JOIN `Organisations`' \
              '         ON `Organisations`.`organisationId`=`Persons`.`defaultOrganisationId`' \
              '  LEFT JOIN `ElectronicPunchingCards`' \
              '         ON `ElectronicPunchingCards`.`cardId`=`Results`.`electronicPunchingCardId`' \
              '  LEFT JOIN `RaceClasses`' \
              '         ON `Results`.`raceClassId`=`RaceClasses`.`raceClassId`' \
              '  LEFT JOIN `EventClasses`' \
              '         ON `RaceClasses`.`eventClassId`=`EventClasses`.`eventClassId`' \
              '  LEFT JOIN `ServiceRequests`' \
              '         ON `Persons`.`personId`=`ServiceRequests`.`personId`' \
              '  LEFT JOIN `Services`' \
              '         ON `ServiceRequests`.`serviceId`=`Services`.`serviceId`' \
              'WHERE `Entries`.`eventId`=%s' \
              '  AND `RaceClasses`.`eventRaceId`=%s' \
              '  AND `Services`.`comment` LIKE \'Startgrupp %%\'' \
              ';'
        cursor.execute(sql, (event_id, event_race_id))
        combined_competitor_data.extend(cursor.fetchall())
        logger.debug('Combined competitor data %d: %s', len(combined_competitor_data), combined_competitor_data)
    return combined_competitor_data


"""def _get_data(element, selector, ns):
    data = element.find(selector, ns)
    if data is not None:
        return data.text
    else:
        return None


def _read_start_groups(start_groups_file: str):
    if start_groups_file.lower().endswith('.zip'):
        archive = ZipFile(start_groups_file, 'r')
        raw_data = archive.read('servicerequests.xml')
    else:
        f = open(start_groups_file, 'r', encoding='windows-1252')
        raw_data = f.read()
    data = ElementTree.fromstring(raw_data)

    ns = {'ns': 'http://www.orienteering.org/datastandard/3.0'}

    event_id = _get_data(data, 'ns:Event/ns:Id', ns)
    event_name = _get_data(data, 'ns:Event/ns:Name', ns)
    event_date = _get_data(data, 'ns:Event/ns:StartTime/ns:Date', ns)
    organiser_id = _get_data(data, 'ns:Event/ns:Organiser/ns:Id', ns)
    organiser_name = _get_data(data, 'ns:Event/ns:Organiser/ns:Name', ns)
    
    if event_date is not None:
        self.competition_date = event_date

    print('Event: ' + str(event_name) + ' (' + str(event_id) + ') ' + str(event_date))
    print('Organiser: ' + str(organiser_name) + ' (' + str(organiser_id) + ')')

    self.team_names.clear()
    self.teams.clear()
    self.runners.clear()

    xml_teams = startlist.findall('ns:ClassStart/ns:TeamStart', ns)
    for xml_team in xml_teams:
        team_name = self._get_data(xml_team, 'ns:Name', ns)
        team_bib_number = self._get_data(xml_team, 'ns:BibNumber', ns)
        self.team_names[team_bib_number] = team_name

        team = dict()
        team_members = xml_team.findall('ns:TeamMemberStart', ns)
        for team_member in team_members:
            team_member_id = self._get_data(team_member, 'ns:Person/ns:Id', ns)
            team_member_name_family = self._get_data(team_member, 'ns:Person/ns:Name/ns:Family', ns)
            team_member_name_given = self._get_data(team_member, 'ns:Person/ns:Name/ns:Given', ns)
            team_member_leg = self._get_data(team_member, 'ns:Start/ns:Leg', ns)
            team_member_leg_order = self._get_data(team_member, 'ns:Start/ns:LegOrder', ns)
            team_member_bib_number = self._get_data(team_member, 'ns:Start/ns:BibNumber', ns)
            team_member_control_card = self._get_data(team_member, 'ns:Start/ns:ControlCard', ns)
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

        team = dict(natsorted(team.items()))
        self.teams[team_bib_number] = team
    # for leg in team.items():
    # 	for subleg in leg:
    #

    self.team_names = dict(natsorted(self.team_names.items()))
    self.teams = dict(natsorted(self.teams.items()))"""


start_group_name_pattern = re.compile(r'(?P<shour>\d+):(?P<sminute>\d+)-(?P<ehour>\d+):(?P<eminute>\d+)',
                                      re.IGNORECASE | re.UNICODE)


def is_in_start_group(start_time: datetime, start_group_name: str) -> bool:

    start_group_name_match = start_group_name_pattern.match(start_group_name)
    if not start_group_name_match:
        raise ValueError('The start group does not have the correct name: %s'.format(start_group_name))

    start_group_first_start_time_hour = int(start_group_name_match.group('shour'))
    start_group_first_start_time_minute = int(start_group_name_match.group('sminute'))

    start_group_first_start_time = start_time.replace(hour=start_group_first_start_time_hour,
                                                      minute=start_group_first_start_time_minute)

    start_group_last_start_time_hour = int(start_group_name_match.group('ehour'))
    start_group_last_start_time_minute = int(start_group_name_match.group('eminute'))

    start_group_last_start_time = start_time.replace(hour=start_group_last_start_time_hour,
                                                     minute=start_group_last_start_time_minute)

    return start_group_first_start_time <= start_time <= start_group_last_start_time


def print_error(message: str, combined_competitor: Dict[str, Any]):
    first_name = combined_competitor['firstName']
    family_name = combined_competitor['familyName']
    club = combined_competitor['club']
    run_class = combined_competitor['class']
    card_number = combined_competitor['cardNumber']
    allocated_start_time = str(combined_competitor['allocatedStartTime'])
    service_comment = combined_competitor['serviceComment']
    service_name = combined_competitor['serviceName']
    print('{message}: {firstName} {familyName},'
          ' {club}, {runClass}, {cardNumber}, {startTime}, {serviceComment}: {serviceName}'
          .format(message=message,
                  firstName=first_name,
                  familyName=family_name,
                  club=club,
                  runClass=run_class,
                  cardNumber=card_number,
                  startTime=allocated_start_time,
                  serviceComment=service_comment,
                  serviceName=service_name))


my_combined_competitor_data = get_combined_competitor_data()
print('Combined competitor data {}: {}'.format(len(my_combined_competitor_data), my_combined_competitor_data))

for my_combined_competitor in my_combined_competitor_data:
    #print('Combined competitor: {}'.format(my_combined_competitor))

    my_start_group_name = my_combined_competitor['serviceName']

    my_allocated_start_time = my_combined_competitor['allocatedStartTime']

    if not my_allocated_start_time:
        print_error('The competitor does NOT have a start time', my_combined_competitor)
        """my_competitor_details = get_competitor_details(my_combined_competitor['entryId'])
        print('The competitor does NOT have a start time: {comp[firstName]} {comp[familyName]}, {comp[club]},'
              ' {comp[class]}, {comp[cardNumber]}, None,'
              ' {combined[serviceComment]}: {combined[serviceName]}'
              .format(comp=my_competitor_details, combined=my_combined_competitor))"""
        continue

    if not is_in_start_group(my_allocated_start_time, my_start_group_name):
        print_error('The competitor is NOT in the correct start group', my_combined_competitor)
        """my_competitor_details = get_competitor_details(my_combined_competitor['entryId'])
        print('The competitor is NOT in the correct start group: {comp[firstName]} {comp[familyName]}, {comp[club]},'
              ' {comp[class]}, {comp[cardNumber]}, {comp[allocatedStartTime]},'
              ' {combined[serviceComment]}: {combined[serviceName]}'
              .format(comp=my_competitor_details, combined=my_combined_competitor))"""
        continue



#from_db(20193)
#from_db(2390)
from_db(4462408)

connection.close()
