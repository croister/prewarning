# -*- coding: utf-8 -*-

from configparser import ConfigParser, SectionProxy
import logging
from pathlib import Path
from typing import List, Dict

from natsort import natsorted
from watchdog.events import LoggingEventHandler, FileSystemEvent
from watchdog.observers import Observer

from utils.config_consumer import ConfigConsumer
from utils.config_definitions import ConfigSectionDefinition, ConfigOptionDefinition, ConfigSectionOptionDefinition, \
    config_section_definitions_sort_key
from utils.singleton import Singleton


class Config(LoggingEventHandler, Singleton):
    """
    Handles the application's configuration.
    """

    DEFAULT_CONFIG_FILE_NAME = 'config.ini'

    DEFAULT_CONFIG_FILE_LOCATION = Path(__file__).resolve().parent.parent.absolute() / DEFAULT_CONFIG_FILE_NAME

    SECTION_COMMON = 'Common'

    CONFIG_SECTION_DEFINITIONS = dict()

    @classmethod
    def register_config_section_definition(cls, config_section_definition: ConfigSectionDefinition):
        if config_section_definition.name in cls.CONFIG_SECTION_DEFINITIONS:
            raise

        temp_config_section_name = '_{}'.format(config_section_definition.name)
        if temp_config_section_name in cls.CONFIG_SECTION_DEFINITIONS:
            config_section_definition.copy_from(cls.CONFIG_SECTION_DEFINITIONS[temp_config_section_name])
            del cls.CONFIG_SECTION_DEFINITIONS[temp_config_section_name]

        cls.CONFIG_SECTION_DEFINITIONS[config_section_definition.name] = config_section_definition

        for required in config_section_definition.requires:
            required.add_required_by(config_section_definition)

        for config_option_definition_name in config_section_definition.option_definitions:
            config_option_definition = config_section_definition.option_definitions[config_option_definition_name]
            for section_enabled_by in config_option_definition.enables:
                if type(section_enabled_by) == ConfigSectionDefinition:
                    section_enabled_by.set_enabled_by(ConfigSectionOptionDefinition(
                        section_name=config_section_definition.name,
                        option_definition=config_option_definition))

        cls.CONFIG_SECTION_DEFINITIONS = {value.name: value
                                          for value in natsorted(cls.CONFIG_SECTION_DEFINITIONS.values(),
                                                                 key=config_section_definitions_sort_key)}

        if cls.has_instance():
            cls.get_instance().config_section_definition_changed(config_section_definition.name)

    @classmethod
    def register_config_option_definition(cls,
                                          config_section_name: str,
                                          config_option_definition: ConfigOptionDefinition,
                                          notify_provider: bool = True):
        config_section_name = cls._create_temporary_config_section_definition_if_needed(config_section_name)

        cls.CONFIG_SECTION_DEFINITIONS[config_section_name].add_option_definition(config_option_definition)

        if cls.has_instance() and notify_provider:
            cls.get_instance().config_option_definition_added(config_section_name, config_option_definition.name)

    @classmethod
    def _create_temporary_config_section_definition_if_needed(cls, config_section_name: str) -> str:
        # Add it to a temporary config section definition if the config section definition is not already defined
        if config_section_name not in cls.CONFIG_SECTION_DEFINITIONS:
            config_section_name = '_{}'.format(config_section_name)
            if config_section_name not in cls.CONFIG_SECTION_DEFINITIONS:
                cls.CONFIG_SECTION_DEFINITIONS[config_section_name] = ConfigSectionDefinition(config_section_name,
                                                                                              config_section_name)
        return config_section_name

    CONFIG_SECTION_LISTENERS = dict()

    @classmethod
    def register_config_section_listener(cls, config_section_name: str, config_section_listener: ConfigConsumer):
        if config_section_name not in cls.CONFIG_SECTION_DEFINITIONS.keys():
            raise ValueError('The Config Section Definition "{}" is not registered.'
                             .format(config_section_name))

        if config_section_name not in cls.CONFIG_SECTION_LISTENERS:
            cls.CONFIG_SECTION_LISTENERS[config_section_name] = []
        if config_section_listener not in cls.CONFIG_SECTION_LISTENERS[config_section_name]:
            cls.CONFIG_SECTION_LISTENERS[config_section_name].append(config_section_listener)

    def __repr__(self) -> str:
        return f'Config(config_file_location={self.config_file_location})'

    def __str__(self) -> str:
        return repr(self)

    def __init__(self, config_file_location: str or Path or None = None):
        self.logger = logging.getLogger(self.__class__.__name__)

        super().__init__(self.logger)

        self.observer = None

        if config_file_location is None:
            self.config_file_location = self.DEFAULT_CONFIG_FILE_LOCATION
        else:
            if type(config_file_location) == Path:
                self.config_file_location = config_file_location
            else:
                self.config_file_location = Path(config_file_location)

        if not self.config_file_location.is_absolute():
            self.config_file_location = Path(__file__).resolve().parent.parent.absolute() / self.config_file_location

        if not self.config_file_location.is_file():
            self.logger.warning('The config file "%s" was not found, creating it.', self.config_file_location)

        self.config = ConfigParser()

        self.config_sections = dict()
        self.prev_config_sections = dict()

        self.observer = Observer()
        self.observer.name = 'ConfigFileObserverThread'
        self.observer.start()

        self.logger.debug('Config: %s', self)

    def __del__(self):
        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join()

    def on_modified(self, event: FileSystemEvent):
        super().on_modified(event)

        src_path = event.src_path
        if Path(src_path).resolve() == self.config_file_location:
            self.logger.debug('Configuration file modification detected, reloading.')
            self.read_config()
            validation_errors = self.validate()
            if len(validation_errors):
                raise ValueError('The configuration contains the following errors: {}.'
                                 .format(str(validation_errors)))

    def start(self):
        self.read_config()

    def get_section(self, name: str) -> SectionProxy:
        if name not in self.config:
            self.logger.error('The config section "%s" is not available.', name)
            raise ValueError('The config section "{}" is not available.'.format(name))
        return self.config[name]

    def config_option_definition_added(self, config_section_name: str, config_option_definition_name: str):
        config_section = self.config[config_section_name]
        section_definition = self.CONFIG_SECTION_DEFINITIONS[config_section_name]
        option_definition = section_definition[config_option_definition_name]
        value = config_section.get(option_definition.name, fallback=option_definition.default_value)
        self._validate_config_option(config_section_name, option_definition, value)

    def config_section_definition_changed(self, config_section_name: str):
        config_section = self.config[config_section_name]
        config_section_definition = self.CONFIG_SECTION_DEFINITIONS[config_section_name]
        self._validate_config_section(config_section, config_section_definition)

    def read_config(self):
        self.logger.debug('read_config')

        self.observer.unschedule_all()

        self.config.read(self.config_file_location)

        updated_sections = []

        for config_section_definition in self.CONFIG_SECTION_DEFINITIONS.values():
            config_section = self._read_config_section(config_section_definition)
            section_name = config_section_definition.name

            if section_name not in self.prev_config_sections \
                    or self.prev_config_sections[section_name] != config_section:
                self.config_sections[section_name] = config_section
                self.prev_config_sections[section_name] = dict(config_section)
                updated_sections.append(section_name)

        self._notify_updates(updated_sections)

        self.observer.schedule(event_handler=self, path=self.config_file_location.parent.as_posix())

    def _read_config_section(self, config_section_definition: ConfigSectionDefinition) -> SectionProxy:
        config_section_name = config_section_definition.name
        if not self.config.has_section(config_section_name):
            self.logger.warning('The configuration file is missing the "%s" section, creating with default values.',
                                config_section_name)
            self._create_initial_config_section(config_section_definition)

        for option_definition in config_section_definition.option_definitions.values():
            if option_definition.name not in self.config[config_section_name]:
                self.logger.warning('The configuration file is missing the "%s" option in the "%s" section,'
                                    ' creating with default value.',
                                    option_definition.name, config_section_name)
                self._create_initial_config_option(self.config[config_section_name], option_definition)

            value = option_definition.get_value(self.config[config_section_name])
            if value is None and option_definition.default_value is not None:
                self.logger.debug('The configuration file is missing a value for the "%s" option in the "%s" section,'
                                  ' using the default value.',
                                  option_definition.name, config_section_name)
                self._create_initial_config_option(self.config[config_section_name], option_definition)

        config_section = self.config[config_section_name]

        return config_section

    def _create_initial_config_section(self, config_section_definition: ConfigSectionDefinition):
        self.config[config_section_definition.name] = config_section_definition.get_initial_config_section()
        self.write()

    def _create_initial_config_option(self, config_section: SectionProxy,
                                      config_option_definition: ConfigOptionDefinition):
        config_section[config_option_definition.name] = config_option_definition.get_initial_option_value()
        self.write()

    def _notify_updates(self, updated_sections: List[str]):
        notifications = dict()
        for updated_section in updated_sections:
            if updated_section in self.CONFIG_SECTION_LISTENERS:
                listeners = self.CONFIG_SECTION_LISTENERS[updated_section]
                for listener in listeners:
                    if listener not in notifications:
                        notifications[listener] = []
                    notifications[listener].append(updated_section)

        for (listener, updated) in notifications.items():
            listener.config_updated(updated)

    def validate(self) -> Dict[ConfigSectionDefinition, Dict[ConfigOptionDefinition, List[str]]]:
        """Validate the configuration

        :return: The validation errors detected for this configuration
        :rtype: Dict[ConfigSectionDefinition, Dict[ConfigOptionDefinition, List[str]]]
        """
        validation_errors = dict()
        for config_section_definition in self.CONFIG_SECTION_DEFINITIONS.values():
            section_name = config_section_definition.name
            config_section = self.config_sections[section_name]

            section_validation_errors = self._validate_config_section(config_section,
                                                                      config_section_definition)
            if len(section_validation_errors):
                validation_errors[config_section_definition] = section_validation_errors

        return validation_errors

    def _validate_config_section(self,
                                 config_section: SectionProxy,
                                 config_section_definition: ConfigSectionDefinition) -> Dict[ConfigOptionDefinition,
                                                                                             List[str]]:
        """Validate a configuration section

        :param SectionProxy config_section: The config section to validate
        :param ConfigSectionDefinition config_section_definition: The config section definition
        :return: The validation errors detected for this config section
        :rtype: Dict[ConfigOptionDefinition, List[str]]
        """
        validation_errors = dict()
        if self._is_config_section_enabled(config_section_definition):
            for option_definition in config_section_definition.option_definitions.values():
                if self._is_config_option_enabled(config_section_definition, option_definition):
                    value = option_definition.get_value(config_section)
                    option_validation_errors = option_definition.validate(value)
                    if len(option_validation_errors):
                        validation_errors[option_definition] = option_validation_errors
        return validation_errors

    def _is_config_section_enabled(self, config_section_definition: ConfigSectionDefinition) -> bool:
        """Determines if a config section is enabled

        :param ConfigSectionDefinition config_section_definition: The config section definition
        :return: True if it is enabled otherwise False
        :rtype: bool
        """
        return config_section_definition.is_enabled(self.config_sections)

    def _is_config_option_enabled(self,
                                  config_section_definition: ConfigSectionDefinition,
                                  config_option_definition: ConfigOptionDefinition) -> bool:
        """Determines if a config option is enabled

        :param ConfigSectionDefinition config_section_definition: The config section definition
        :param ConfigOptionDefinition config_option_definition: The config option definition
        :return: True if it is enabled otherwise False
        :rtype: bool
        """
        return config_option_definition.is_enabled(self.config_sections[config_section_definition.name])

    def write(self):
        """Write the configuration to file"""
        with open(self.config_file_location, 'w') as configfile:
            self.config.write(configfile)
