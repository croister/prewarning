import logging
from abc import ABC, abstractmethod

from utils.config_definitions import ConfigSectionDefinition


class ConfigConsumer(ABC):
    """
    Base class for configuration consumers.
    """

    @classmethod
    @abstractmethod
    def config_section_definition(cls) -> ConfigSectionDefinition:
        """Must return the main config section definition for the implementing class

        :return: The configuration section definition for the class
        :rtype: ConfigSectionDefinition
        """

    @classmethod
    def get_config_section_definitions(cls) -> list[ConfigSectionDefinition]:
        """Returns a list of configuration section definitions.
        The default implementation adds the classes own config section,
        can be overridden to add more config sections to get notifications when they are changed.

        :return: A list of configuration section definitions
        :rtype: List[ConfigSectionDefinition]
        """
        definitions = [cls.config_section_definition()]
        return definitions

    def __repr__(self) -> str:
        return "ConfigConsumer()"

    def __str__(self) -> str:
        return repr(self)

    @abstractmethod
    def __init__(self):
        super().__init__()

        self.logger = logging.getLogger(self.__class__.__name__)

        definitions = self.get_config_section_definitions()
        self.logger.debug("config_section_definitions: %s", definitions)
        if definitions is not None:
            for definition in definitions:
                from utils.config import Config

                Config.register_config_section_listener(definition.name, self)

    def config_updated(self, section_names: list[str]):
        pass
