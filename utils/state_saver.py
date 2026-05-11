# -*- coding: utf-8 -*-
from abc import abstractmethod, ABC
from configparser import ConfigParser, SectionProxy
import logging
from pathlib import Path
from typing import List, Any, Dict

from utils.config_definitions import RuntimeStateOptionDefinition, RuntimeStateGroup
from utils.constants import DATA_DIR


class _StateSaverGroup:
    """
    Provides functionality to preserve state for a RuntimeStateGroup that survives abrupt restarts by writing and reading it from a file.
    """

    def __repr__(self) -> str:
        return f'__StateSaverGroup(' \
               f'config_section_name={self.config_section_name},' \
               f'runtime_state_group={self.runtime_state_group})'

    def __str__(self) -> str:
        return repr(self)

    def __init__(self, config_section_name: str, runtime_state_group: RuntimeStateGroup, data_dir: Path = DATA_DIR):
        self.logger = logging.getLogger(self.__class__.__name__)

        self.config_section_name = config_section_name

        self.runtime_state_group = runtime_state_group

        self._state_file_location = data_dir / runtime_state_group.state_file_name

        self._data_read_state = dict()
        for option_definition_name in self.runtime_state_group.option_definitions.keys():
            self._data_read_state[option_definition_name] = False

        self._config = ConfigParser()

        self._config_section: SectionProxy | None = None

        self._read_state()

    def _cleanup(self):
        if self._state_file_location.is_file():
            self._state_file_location.unlink()

    def _read_state(self):
        self.logger.debug('_read_state')

        self._config.read(self._state_file_location)

        self._config_section = self.__read_config_section()

        self.__validate()

    def __read_config_section(self) -> SectionProxy:
        if not self._config.has_section(self.config_section_name):
            self.logger.debug('The state file is missing the "%s" section, creating with default values.',
                              self.config_section_name)
            self.__create_initial_config_section()
        else:
            for option_definition_name in self.runtime_state_group.option_definitions.keys():
                self._data_read_state[option_definition_name] = True

        for option_definition in self.runtime_state_group.option_definitions.values():
            if option_definition.name not in self._config[self.config_section_name]:
                self.logger.debug('The state file is missing the "%s" option in the "%s" section,'
                                  ' creating with default value.',
                                  option_definition.name, self.config_section_name)
                self.__create_initial_config_option(self._config[self.config_section_name], option_definition)
                self._data_read_state[option_definition.name] = False

            value = option_definition.get_value(self._config[self.config_section_name])
            if value is None and option_definition.default_value is not None:
                self.logger.debug('The state file is missing a value for the "%s" option in the "%s" section,'
                                  ' using the default value.',
                                  option_definition.name, self.config_section_name)
                self.__create_initial_config_option(self._config[self.config_section_name], option_definition)
                self._data_read_state[option_definition.name] = False

        config_section = self._config[self.config_section_name]

        return config_section

    def __create_initial_config_section(self):
        self.logger.info('Creating initial state file "%s" with default values.', self._state_file_location)
        initial_config_section = dict()
        for option_definition in self.runtime_state_group.option_definitions.values():
            initial_config_section[option_definition.name] = option_definition.get_initial_option_value()
        self._config[self.config_section_name] = initial_config_section
        self.__write()

    def __create_initial_config_option(self, config_section: SectionProxy,
                                       config_option_definition: RuntimeStateOptionDefinition):
        config_section[config_option_definition.name] = config_option_definition.get_initial_option_value()
        self.__write()

    def __validate(self):
        """Validate the state file
        """
        for option_definition in self.runtime_state_group.option_definitions.values():
            value = option_definition.get_value(self._config_section)
            option_validation_errors = option_definition.validate(value)
            if len(option_validation_errors):
                self.logger.error('The state file has has the following validation errors value for the "%s" option'
                                  ' in the "%s" section, using the default value.\nValidation errors:\n%s',
                                  option_definition.name, self.config_section_name, str(option_validation_errors))
                self.__create_initial_config_option(self._config[self.config_section_name], option_definition)

    def __write(self):
        """Write the state to file"""
        with open(self._state_file_location, 'w') as state_file:
            self._config.write(state_file)

    def _data_read(self, option_definition: RuntimeStateOptionDefinition) -> bool:
        """Returns true if valid data has been read from the state file for the ConfigOptionDefinition

        :param ConfigOptionDefinition option_definition: The ConfigOptionDefinition to check for
        :return: True if valid data has been read otherwise False
        :rtype: bool
        """
        return option_definition.name in self._data_read_state and self._data_read_state[option_definition.name]

    def _get_value(self, option_definition: RuntimeStateOptionDefinition) -> Any:
        assert self._config_section is not None
        return option_definition.get_value(self._config_section)

    def _save_value(self, option_definition: RuntimeStateOptionDefinition, value: Any):
        self.logger.debug('_save_value: %s=%s', str(option_definition), value)
        assert self._config_section is not None
        option_definition.set_value(self._config_section, value)
        self.__write()

    def _save_values(self, values: Dict[RuntimeStateOptionDefinition, Any]):
        self.logger.debug('_save_values: %s', str(values))
        assert self._config_section is not None
        for option_definition in values.keys():
            option_definition.set_value(self._config_section, values[option_definition])
        self.__write()


class StateSaverMixin(ABC):
    """
    Provides functionality to preserve state that survives abrupt restarts by writing and reading it from a file.
    """

    def __repr__(self) -> str:
        return f'StateSaverMixin(state_saver_groups={self.state_saver_groups})'

    def __str__(self) -> str:
        return repr(self)

    def __init__(self, config_section_name: str,
                 runtime_state_groups: List[RuntimeStateGroup],
                 data_dir: Path = DATA_DIR):
        self.logger = logging.getLogger(self.__class__.__name__)

        if not data_dir.is_dir():
            data_dir.mkdir()

        self.state_saver_groups = dict({runtime_state_group.state_file_name: _StateSaverGroup(config_section_name, runtime_state_group, data_dir)
                                        for runtime_state_group in runtime_state_groups})

    def _cleanup(self):
        for state_saver_group in self.state_saver_groups.values():
            state_saver_group._cleanup()

    def __state_saver_groups_key(self, option_definition: RuntimeStateOptionDefinition) -> str:
        return option_definition.runtime_state_group.state_file_name

    def _data_read(self, option_definition: RuntimeStateOptionDefinition) -> bool:
        """Returns true if valid data has been read from the state file for the ConfigOptionDefinition

        :param ConfigOptionDefinition option_definition: The ConfigOptionDefinition to check for
        :return: True if valid data has been read otherwise False
        :rtype: bool
        """
        return self.state_saver_groups[self.__state_saver_groups_key(option_definition)]._data_read(option_definition)

    def _get_value(self, option_definition: RuntimeStateOptionDefinition) -> Any:
        """Returns the value with the correct type for a ConfigOptionDefinition

        :param ConfigOptionDefinition option_definition: The ConfigOptionDefinition to get the value for
        :return: The value
        :rtype: Any
        """
        return self.state_saver_groups[self.__state_saver_groups_key(option_definition)]._get_value(option_definition)

    def _save_value(self, option_definition: RuntimeStateOptionDefinition, value: Any):
        """Saves the value for a ConfigOptionDefinition to the state file

        :param ConfigOptionDefinition option_definition: The ConfigOptionDefinition to write the value for
        :param Any value: The value to write
        """
        self.state_saver_groups[self.__state_saver_groups_key(option_definition)]._save_value(option_definition, value)

    def _save_values(self, values: Dict[RuntimeStateOptionDefinition, Any]):
        """Saves the values for the ConfigOptionDefinitions to the state file

        :param Dict[ConfigOptionDefinition, Any] values: The values to write
        """
        state_saver_groups: dict[str, dict[RuntimeStateOptionDefinition, Any]] = dict()
        for option_definition, value in values.items():
            state_saver_groups_key = self.__state_saver_groups_key(option_definition)
            if state_saver_groups_key not in state_saver_groups:
                state_saver_groups[state_saver_groups_key] = dict()
            state_saver_groups[state_saver_groups_key][option_definition] = value

        for state_saver_group_key, group_values in state_saver_groups.items():
            self.state_saver_groups[state_saver_group_key]._save_values(group_values)

    @abstractmethod
    def _save_state(self):
        """Implement to save the state.
        """
