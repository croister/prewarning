# -*- coding: utf-8 -*-
from abc import abstractmethod
from configparser import ConfigParser, SectionProxy
import logging
from pathlib import Path
from typing import List, Any, Dict

from utils.config_definitions import ConfigOptionDefinition
from utils.constants import DATA_DIR


class StateSaverMixin:
    """
    Provides functionality to preserve state that survives abrupt restarts by writing and reading it from a file.
    """

    def __repr__(self) -> str:
        return f'StateSaverMixin(state_file_location={self.state_file_location},' \
               f'config_section_name={self.config_section_name},' \
               f'option_definitions={self.option_definitions})'

    def __str__(self) -> str:
        return repr(self)

    def __init__(self, state_file_name: str,
                 config_section_name: str,
                 option_definitions: List[ConfigOptionDefinition]):
        self.logger = logging.getLogger(self.__class__.__name__)

        if not DATA_DIR.is_dir():
            DATA_DIR.mkdir()

        self.state_file_location = DATA_DIR / state_file_name

        if not self.state_file_location.is_absolute():
            self.state_file_location = Path(__file__).resolve().parent.parent.absolute() / self.state_file_location

        if not self.state_file_location.is_file():
            self.logger.info('The state file "%s" was not found, creating it.', self.state_file_location)

        self.config_section_name = config_section_name

        self.option_definitions = dict({option_definition.name: option_definition
                                        for option_definition in option_definitions})

        self.data_read = dict()
        for option_definition_name in self.option_definitions.keys():
            self.data_read[option_definition_name] = False

        self.config = ConfigParser()

        self.config_section = None

        self.__read_state()

    def __del__(self):
        self._cleanup()

    def _cleanup(self):
        if self.state_file_location.is_file():
            self.state_file_location.unlink()

    def __read_state(self):
        self.logger.debug('_read_state')

        self.config.read(self.state_file_location)

        self.config_section = self.__read_config_section()

        self.__validate()

    def __read_config_section(self) -> SectionProxy:
        if not self.config.has_section(self.config_section_name):
            self.logger.debug('The state file is missing the "%s" section, creating with default values.',
                              self.config_section_name)
            self.__create_initial_config_section()
        else:
            for option_definition_name in self.option_definitions.keys():
                self.data_read[option_definition_name] = True

        for option_definition in self.option_definitions.values():
            if option_definition.name not in self.config[self.config_section_name]:
                self.logger.debug('The state file is missing the "%s" option in the "%s" section,'
                                  ' creating with default value.',
                                  option_definition.name, self.config_section_name)
                self.__create_initial_config_option(self.config[self.config_section_name], option_definition)
                self.data_read[option_definition.name] = False

            value = option_definition.get_value(self.config[self.config_section_name])
            if value is None and option_definition.default_value is not None:
                self.logger.debug('The state file is missing a value for the "%s" option in the "%s" section,'
                                  ' using the default value.',
                                  option_definition.name, self.config_section_name)
                self.__create_initial_config_option(self.config[self.config_section_name], option_definition)
                self.data_read[option_definition.name] = False

        config_section = self.config[self.config_section_name]

        return config_section

    def __create_initial_config_section(self):
        initial_config_section = dict()
        for option_definition in self.option_definitions.values():
            initial_config_section[option_definition.name] = option_definition.get_initial_option_value()
        self.config[self.config_section_name] = initial_config_section
        self.__write()

    def __create_initial_config_option(self, config_section: SectionProxy,
                                       config_option_definition: ConfigOptionDefinition):
        config_section[config_option_definition.name] = config_option_definition.get_initial_option_value()
        self.__write()

    def __validate(self):
        """Validate the state file
        """
        for option_definition in self.option_definitions.values():
            value = option_definition.get_value(self.config_section)
            option_validation_errors = option_definition.validate(value)
            if len(option_validation_errors):
                self.logger.error('The state file has has the following validation errors value for the "%s" option'
                                  ' in the "%s" section, using the default value.\nValidation errors:\n%s',
                                  option_definition.name, self.config_section_name, str(option_validation_errors))
                self.__create_initial_config_option(self.config[self.config_section_name], option_definition)

    def __write(self):
        """Write the state to file"""
        with open(self.state_file_location, 'w') as state_file:
            self.config.write(state_file)

    def _data_read(self, option_definition: ConfigOptionDefinition) -> bool:
        """Returns true if valid data has been read from the state file for the ConfigOptionDefinition

        :param ConfigOptionDefinition option_definition: The ConfigOptionDefinition to check for
        :return: True if valid data has been read otherwise False
        :rtype: bool
        """
        return option_definition.name in self.data_read and self.data_read[option_definition.name]

    def _get_value(self, option_definition: ConfigOptionDefinition) -> Any:
        """Returns the value with the correct type for a ConfigOptionDefinition

        :param ConfigOptionDefinition option_definition: The ConfigOptionDefinition to get the value for
        :return: The value
        :rtype: Any
        """
        return option_definition.get_value(self.config_section)

    def _save_value(self, option_definition: ConfigOptionDefinition, value: Any):
        """Saves the value for a ConfigOptionDefinition to the state file

        :param ConfigOptionDefinition option_definition: The ConfigOptionDefinition to write the value for
        :param Any value: The value to write
        """
        self.logger.debug('_save_value: %s=%s', str(option_definition), value)
        option_definition.set_value(self.config_section, value)
        self.__write()

    def _save_values(self, values: Dict[ConfigOptionDefinition, Any]):
        """Saves the values for the ConfigOptionDefinitions to the state file

        :param Dict[ConfigOptionDefinition, Any] values: The values to write
        """
        self.logger.debug('_save_values: %s', str(values))
        for option_definition in values.keys():
            option_definition.set_value(self.config_section, values[option_definition])
        self.__write()

    @abstractmethod
    def _save_state(self):
        """Implement to save the state.
        """
