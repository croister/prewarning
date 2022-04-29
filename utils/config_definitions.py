# -*- coding: utf-8 -*-

import inspect
import logging
from configparser import SectionProxy
from enum import Enum, unique
from pathlib import Path
from typing import Any, Dict, List, Callable, Iterable, Tuple

import wx


class ConfigOptionDefinition:
    """
    Defines the metadata of a configuration option.
    """

    def __repr__(self) -> str:
        return f'ConfigOptionDefinition(name={self.name},' \
               f' value_type={self.value_type},' \
               f' description={self.description},' \
               f' mandatory={self.mandatory},' \
               f' default_value={self.default_value})'

    def __str__(self) -> str:
        return repr(self)

    def __init__(self,
                 name: str,
                 display_name: str,
                 value_type: type,
                 description: str,
                 mandatory: bool = False,
                 default_value: Any = None,
                 valid_values: List[Any] = None,
                 valid_values_gen: Callable = None,
                 enabled_by: 'ConfigOptionDefinition' = None,
                 enables: List['ConfigSectionDefinition' or 'ConfigOptionDefinition'] = None,
                 validator: Callable = None):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)

        if enables is None:
            enables = list()

        self.name = name
        self.display_name = display_name
        self.value_type = value_type
        self.description = description
        self.mandatory = mandatory
        self.default_value = default_value
        self.valid_values = valid_values
        self.valid_values_gen = valid_values_gen
        self.enabled_by = enabled_by
        self.enables = enables
        self.validator = validator
        self.verifier = None
        self.selector = None

        if enabled_by is not None:
            if enabled_by.value_type != bool:
                self.logger.error(
                    'Only bool option values are allows for "enabled_by" for the configuration option %s.', self.name)
                raise ValueError(
                    'Only bool option values are allows for "enabled_by" for the configuration option {}.'.format(
                        self.name))

            enabled_by.enables.append(self)

        self.logger.debug(self)

        self._validate_type()

        if self.valid_values is not None and self.valid_values_gen is not None:
            self.logger.error(
                'Both valid_values and valid_values_gen can not be set at the same time '
                'on the configuration option %s.', self.name)
            raise ValueError(
                'Both valid_values and valid_values_gen can not be set at the same time '
                'on the configuration option {}.'.format(self.name))

        if self.valid_values is not None:
            for value in self.valid_values:
                self._validate_value_type('valid_values', value)

        if self.valid_values_gen is not None:
            for value in self.valid_values_gen():
                self._validate_value_type('valid_values_gen', value)

        if self.default_value is not None:
            validation_errors = self.validate(self.default_value, True)
            if len(validation_errors):
                raise ValueError(
                    'The DEFAULT value ({}) for the configuration option {} has the following validation errors: {}.'
                    .format(self.default_value, self.name, str(validation_errors)))

    def set_verifier(self, verifier: 'ConfigVerifierDefinition'):
        """Defines which function to use to verify this config option

        :param ConfigVerifierDefinition verifier: The function to use to verify this config option
        """
        if self.verifier is not None:
            self.logger.error('Verifier is already defined for "%s".', self.name)
            raise ValueError('Verifier is already defined for "{}".'.format(self.name))

        self.verifier = verifier

    def set_selector(self, selector: 'ConfigSelectorDefinition'):
        """Defines which function to use to select a value for this config option

        :param ConfigSelectorDefinition selector: The function to use to select a value for this config option
        """
        if self.selector is not None:
            self.logger.error('Selector is already defined for "%s".', self.name)
            raise ValueError('Selector is already defined for "{}".'.format(self.name))

        self.selector = selector

    def _validate_type(self):
        """Validates the value type
        """
        if self.value_type == bool:
            if self.default_value is None:
                self.logger.error(
                    'A configuration option (%s) with the type bool must have a default value.', self.name)
                raise ValueError(
                    'A configuration option ({}) with the type bool must have a default value.'.format(self.name))
            if self.valid_values is not None or self.valid_values_gen is not None:
                self.logger.error(
                    'A configuration option (%s) with the type bool can not have valid values defined.',
                    self.name)
                raise ValueError(
                    'A configuration option ({}) with the type bool can not have valid values defined.'.format(
                        self.name))

    def get_valid_values(self) -> List[Any] or None:
        """Returns the list of valid values for this option

        :return: The list of valid values for this option
        :rtype: List[str] or None
        """
        valid_values = None
        if self.valid_values is not None:
            valid_values = self.valid_values
        elif self.valid_values_gen is not None:
            valid_values = self.valid_values_gen()
        return valid_values

    def validate(self, value: Any, is_default: bool = False) -> List[str]:
        """Validates the value

        :param str value: The value to be validated
        :param bool is_default: If set to True it will print 'default value' otherwise only 'value'
        :return: The validation errors detected for this value
        :rtype: List[str]
        """
        value_name = 'value'
        if is_default:
            value_name = 'DEFAULT value'

        validation_errors = list()
        try:
            converted_value = self._convert_value(value_name, value)

            if converted_value is None:
                if self.mandatory:
                    validation_errors.append('The value is mandatory.')
            else:

                validation_errors.extend(self._validate_value_type(value_name, converted_value))
                validation_errors.extend(self._validate_value(value_name, converted_value))
        except ValueError as e:
            validation_errors.append(e.args[0])

        return validation_errors

    def _convert_value(self, value_name: str, value: Any) -> Any:
        """Returns the value converted to the correct type

        :param str value_name: The name of the value
        :param Any value: The value to convert
        :return: The converted value
        :rtype: Any
        """
        if value is None:
            return None

        if type(value) == str and not value:
            return None

        try:
            if self.value_type is str:
                converted_value = str(value)
            elif self.value_type is int:
                converted_value = int(value)
            elif self.value_type is float:
                converted_value = float(value)
            elif self.value_type is bool:
                converted_value = bool(value)
            elif self.value_type is Path:
                converted_value = Path(str(value))
            else:
                self.logger.error(
                    'Unknown value type "%s" for the configuration option %s.', self.value_type.__name__, self.name)
                raise ValueError(
                    'Unknown value type "{}" for the configuration option {}.'.format(self.value_type.__name__,
                                                                                      self.name))
        except ValueError:
            self.logger.error(
                'The %s (%s) for the configuration option %s is expected to have the type "%s" but has the type "%s".',
                value_name, value, self.name, self.value_type.__name__, type(value).__name__)
            raise ValueError('The {} is expected to have the type "{}" but has the type "{}".'
                             .format(value_name, self.value_type.__name__, type(value).__name__))
        return converted_value

    def get_value(self, config_section: SectionProxy) -> Any:
        """Returns the value with the correct type from a config section

        :param SectionProxy config_section: The config section to read the value from
        :return: The value
        :rtype: Any
        """
        if self.value_type is str:
            try:
                value = config_section.get(self.name, fallback=self.default_value)
                if not value:
                    value = None
            except ValueError:
                value = None
        elif self.value_type is int:
            try:
                value = config_section.getint(self.name, fallback=self.default_value)
            except ValueError as e:
                value = None
        elif self.value_type is float:
            try:
                value = config_section.getfloat(self.name, fallback=self.default_value)
            except ValueError:
                value = None
        elif self.value_type is bool:
            try:
                value = config_section.getboolean(self.name, fallback=self.default_value)
            except ValueError:
                value = None
        elif self.value_type is Path:
            try:
                value = config_section.get(self.name, fallback=self.default_value)
                if not value:
                    value = None
            except ValueError:
                value = None
            if value is not None:
                try:
                    value = Path(value).resolve()
                except Exception as e:
                    self.logger.debug('get_value: %s', e)
                    value = None
        else:
            self.logger.error(
                'Unknown value type "%s" for the configuration option %s.', self.value_type.__name__, self.name)
            raise ValueError(
                'Unknown value type "{}" for the configuration option {}.'.format(self.value_type.__name__, self.name))
        return value

    def get_value_str(self, config_section: SectionProxy) -> str:
        value = self.get_value(config_section)
        if value is None:
            value = ''
        return str(value)

    def set_value(self, config_section: SectionProxy, value: Any):
        """Sets the value to a config section

        :param SectionProxy config_section: The config section to set the value to
        :param Any value: The value to set
        """
        config_section[self.name] = str(value)

    def _validate_value_type(self, value_name: str, value: Any) -> List[str]:
        """Validates the type of a value

        :param str value_name: The name of the value
        :param str value: The value to be validated
        :return: The validation errors detected for this value
        :rtype: List[str]
        """
        validation_errors = list()

        if not issubclass(type(value), self.value_type):
            self.logger.error(
                'The %s (%s) for the configuration option %s is expected to have the type "%s" but has the type "%s".',
                value_name, value, self.name, self.value_type.__name__, type(value).__name__)
            validation_errors.append('The value is expected to have the type "{}" but has the type "{}".'
                                     .format(self.value_type.__name__, type(value).__name__))
        return validation_errors

    def _validate_value(self, value_name: str, value: Any) -> List[str]:
        """Validates the value against the list of valid values

        :param str value_name: The name of the value
        :param str value: The value to be validated
        :return: The validation errors detected for this value
        :rtype: List[str]
        """
        validation_errors = list()

        valid_values = self.get_valid_values()

        if valid_values is not None:
            if value not in valid_values:
                self.logger.error(
                    'The %s (%s) for the configuration option %s is not in the valid values list (%s).',
                    value_name, value, self.name, str(valid_values))
                validation_errors.append('The {} is not in the valid values list ({}).'
                                         .format(value_name, str(valid_values)))
        elif self.validator is not None:
            result = self.validator(value)
            if not result:
                validation_errors.append(result.message)
        else:
            if self.value_type is str:
                pass
            elif self.value_type is int:
                pass
            elif self.value_type is float:
                pass
            elif self.value_type is bool:
                pass
            elif self.value_type is Path:
                pass

        return validation_errors

    def get_initial_option_value(self) -> str:
        """Returns the initial value for this option.

        :return: The initial value
        :rtype: str
        """
        initial_option_value = ''
        if self.default_value is not None:
            initial_option_value = str(self.default_value)
        return initial_option_value

    def is_enabled(self, config_section: SectionProxy) -> bool:
        """Determines if this config option is enabled

        :param SectionProxy config_section: The config section
        :return: True if it is enabled otherwise False
        :rtype: bool
        """
        if self.enabled_by is None:
            return True
        return self._is_enabled_by(config_section)

    def _is_enabled_by(self, config_section: SectionProxy) -> bool:
        """Determines if this config option is enabled by another config option in the same config section

        :param SectionProxy config_section: The config section
        :return: True if it is enabled otherwise False
        :rtype: bool
        """
        if self.enabled_by is None:
            self.logger.error(
                '"enabled_by" is not configured for the configuration option %s.', self.name)
            raise ValueError(
                '"enabled_by" is not configured for the configuration option {}.'.format(self.name))

        option_definition = self.enabled_by
        value = option_definition.get_value(config_section)
        value_type = type(value)
        if value_type == bool:
            return value
        else:
            self.logger.error(
                'Unknown value type "%s" for the "enabled_by" value for the configuration option %s.',
                value_type, self.name)
            raise ValueError(
                'Unknown value type "{}" for the "enabled_by" value for the configuration option {}.'.format(
                    str(value_type), self.name))


class ConfigSectionOptionDefinition:
    """
    Defines the metadata of a configuration option in a specific config section.
    """

    def __repr__(self) -> str:
        return f'ConfigSectionOptionDefinition(section_name={self.section_name},' \
               f' option_definition={self.option_definition.name})'

    def __str__(self) -> str:
        return repr(self)

    def __init__(self,
                 section_name: str,
                 option_definition: ConfigOptionDefinition):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)

        self.section_name = section_name
        self.option_definition = option_definition

        self.logger.debug(self)


@unique
class ConfigSectionEnableType(Enum):
    ALWAYS = 'Always'
    IF_ENABLED = 'If enabled'
    IF_REQUIRED = 'If required'


def config_section_definitions_sort_key(config_section_definition: 'ConfigSectionDefinition') -> str:
    return config_section_definition.sort_key()


class ConfigSectionDefinition:
    """
    Defines the metadata of a configuration section.
    """

    def __repr__(self) -> str:
        return f'ConfigSectionDefinition(name={self.name},' \
               f' option_definitions={list(self.option_definitions.keys())})'

    def __str__(self) -> str:
        return repr(self)

    def __init__(self,
                 name: str,
                 display_name: str,
                 option_definitions: List[ConfigOptionDefinition] = None,
                 enable_type: ConfigSectionEnableType = ConfigSectionEnableType.ALWAYS,
                 requires: List['ConfigSectionDefinition'] = None,
                 sort_key_prefix: int = 100,
                 ):
        super().__init__()

        self.logger = logging.getLogger(self.__class__.__name__)

        if option_definitions is None:
            option_definitions = list()
        if requires is None:
            requires = list()

        self.name = name
        self.display_name = display_name
        self.option_definitions = dict({option_definition.name: option_definition
                                        for option_definition in option_definitions})
        self.enable_type = enable_type
        self.requires = requires
        self.sort_key_prefix = sort_key_prefix

        self.enabled_by = None
        self.required_by = list()

        self.logger.debug(self)

    def sort_key(self):
        return '{} {}'.format(self.sort_key_prefix, self.name)

    def copy_from(self, temp_config_section_definition: 'ConfigSectionDefinition'):
        """Copies relevant values from another ConfigSectionDefinition to this ConfigSectionDefinition

        :param ConfigSectionDefinition temp_config_section_definition: The other ConfigSectionDefinition
        """
        for option_definition_name in temp_config_section_definition.option_definitions:
            self.add_option_definition(temp_config_section_definition.option_definitions[option_definition_name])

        if temp_config_section_definition.enabled_by is not None:
            self.set_enabled_by(temp_config_section_definition.enabled_by)

        for requires in temp_config_section_definition.required_by:
            self.add_required_by(requires)

    def add_option_definition(self, option_definition: ConfigOptionDefinition):
        """Adds an option definition to this config section

        :param ConfigOptionDefinition option_definition: The option definition to add
        """
        if option_definition.name in self.option_definitions.keys():
            self.logger.error('The configuration option definition for "%s" already exists.',
                              option_definition.name)
            raise ValueError('The configuration option definition for "{}" already exists.'
                             .format(option_definition.name))

        self.option_definitions[option_definition.name] = option_definition

    def set_enabled_by(self, config_section_option: ConfigSectionOptionDefinition):
        """Defines which config section option that is used to enable config section

        :param ConfigSectionOptionDefinition config_section_option: The config section option to set
        """
        if self.enabled_by is not None:
            self.logger.error('Enabled by is already defined for "%s".', self.name)
            raise ValueError('Enabled by is already defined for "{}".'.format(self.name))

        self.enabled_by = config_section_option

    def add_required_by(self, config_section: 'ConfigSectionDefinition'):
        """Adds a config section that is required by this config section

        :param ConfigSectionDefinition config_section: The config section to add
        """
        if config_section in self.required_by:
            self.logger.error('This configuration section definition (%s) is already required by "%s".',
                              self.name, config_section.name)
            raise ValueError('This configuration section definition ({}) is already required by "{}".'
                             .format(self.name, config_section.name))

        self.required_by.append(config_section)

    def get_initial_config_section(self) -> Dict[str, str]:
        """Returns the initial values for this section.

        :return: The initial values
        :rtype: Dict[str, str]
        """
        initial_config_section = dict()
        for option_definition in self.option_definitions.values():
            initial_config_section[option_definition.name] = option_definition.get_initial_option_value()

        return initial_config_section

    def is_enabled(self, config_sections: Dict[str, SectionProxy]) -> bool:
        """Determines if this config section is enabled

        :param Dict[str, SectionProxy] config_sections: The config sections
        :return: True if it is enabled otherwise False
        :rtype: bool
        """
        if self.enable_type is ConfigSectionEnableType.ALWAYS:
            return True
        elif self.enable_type is ConfigSectionEnableType.IF_ENABLED:
            return self._is_enabled_by(config_sections)
        elif self.enable_type is ConfigSectionEnableType.IF_REQUIRED:
            return self._is_enabled_if_required_by(config_sections)

    def _is_enabled_by(self, config_sections: Dict[str, SectionProxy]) -> bool:
        """Determines if this config section is enabled by a configuration in another config section

        :param Dict[str, SectionProxy] config_sections: The config sections
        :return: True if it is enabled otherwise False
        :rtype: bool
        """
        if self.enabled_by is None:
            self.logger.error(
                'Enable type is "%s" but "enabled_by" is not configured for the configuration section %s.',
                self.enable_type, self.name)
            raise ValueError(
                'Enable type is  "{}" but "enabled_by" is not configured for the configuration section {}.'.format(
                    self.enable_type, self.name))

        other_config_section = config_sections[self.enabled_by.section_name]
        option_definition = self.enabled_by.option_definition
        value = option_definition.get_value(other_config_section)

        if value is None:
            return False

        value_type = type(value)
        if value_type == bool:
            return value
        elif value_type == str:
            return value == self.name
        else:
            self.logger.error(
                'Unknown value type "%s" for the "enabled_by" value for the configuration section %s.',
                value_type, self.name)
            raise ValueError(
                'Unknown value type "{}" for the "enabled_by" value for the configuration section {}.'.format(
                    str(value_type), self.name))

    def _is_enabled_if_required_by(self, config_sections: Dict[str, SectionProxy]) -> bool:
        """Determines if this config section is enabled by checking if any of the requiring config sections are enabled

        :param Dict[str, SectionProxy] config_sections: The config sections
        :return: True if it is enabled otherwise False
        :rtype: bool
        """
        if not len(self.required_by):
            self.logger.error(
                'Enable type is "%s" but "required_by" is not configured for the configuration section %s.',
                self.enable_type, self.name)
            raise ValueError(
                'Enable type is  "{}" but "required_by" is not configured for the configuration section {}.'.format(
                    self.enable_type, self.name))

        for config_section_definition in self.required_by:
            if config_section_definition.is_enabled(config_sections):
                return True

        return False


class VerificationResult:

    def __init__(self, message: str, status: bool = True):

        if message is None:
            message = 'Select value:'

        self.message = message
        self.status = status

    def __repr__(self):
        return f'SelectionResult(message={self.message})'

    def __str__(self):
        return repr(self)

    def __unicode__(self):
        return repr(self)

    def __bool__(self):
        return self.status


class VerificationError(Exception):

    def __init__(self, function: Callable, message: str, args: Iterable[Tuple[str, Any]]):
        self.function = function
        self.message = message
        self.__dict__.update(args)

    def __repr__(self):
        return 'VerificationError(function={function}, message={message}, args={args})'.format(
            function=self.function.__name__,
            message=self.message,
            args=dict(
                [(k, v) for (k, v) in self.__dict__.items() if k != 'function' and k != 'message']
            )
        )

    def __str__(self):
        return repr(self)

    def __unicode__(self):
        return repr(self)

    def __bool__(self):
        return False


class ConfigVerifierDefinition:
    """
    Defines the metadata of a configuration verifier.
    """

    def __repr__(self) -> str:
        return f'ConfigVerifierDefinition(function={self.function},' \
               f' parameters={self.parameters},' \
               f' message={self.message})'

    def __str__(self) -> str:
        return repr(self)

    def __init__(self,
                 function: Callable,
                 parameters: [ConfigSectionOptionDefinition],
                 message: str = None):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)

        if message is None:
            message = 'Verification failed.'

        self.function = function
        self.parameters = parameters
        self.message = message

        self.logger.debug(self)

    def verify(self) -> bool or VerificationError:
        from utils.config import Config
        args = [p.option_definition.get_value(Config().get_section(p.section_name)) for p in self.parameters]

        result = self.function(*args)
        if not result:
            message = self.message
            if isinstance(result, VerificationResult):
                if result.message is not None:
                    message = result.message
            arg_names = inspect.getfullargspec(self.function)[0]
            return VerificationError(self.function, message, dict(zip(arg_names, args)))

        return result


class SelectionData:

    def __init__(self, value: Any, display_name: str):
        self.value = value
        self.display_name = display_name

    def __repr__(self):
        return 'SelectionData(value={value}, display_name={display_name})'.format(
            value=self.value, display_name=self.display_name)

    def __str__(self):
        return repr(self)

    def __unicode__(self):
        return repr(self)

    def __bool__(self):
        return True


@unique
class SelectionType(Enum):
    SINGLE = 'Single',
    MULTIPLE = 'Multiple',


class SelectionResult(Exception):

    def __init__(self, caption: str = None, message: str = None, selection_type: SelectionType = SelectionType.SINGLE):

        if caption is None:
            caption = 'Values'
        if message is None:
            message = 'Select value:'

        self.caption = caption
        self.message = message
        self.selection_type = selection_type

        self.values = []

    def add_value(self, value: SelectionData):
        self.values.append(value)

    def __repr__(self):
        return f'SelectionResult(caption={self.caption}, message={self.message}, ' \
               f'selection_type={self.selection_type}, values={self.values})'

    def __str__(self):
        return repr(self)

    def __unicode__(self):
        return repr(self)

    def __bool__(self):
        return True


class SelectionError(Exception):

    def __init__(self, function: Callable, message: str, args: Iterable[Tuple[str, Any]]):
        self.function = function
        self.message = message
        self.__dict__.update(args)

    def __repr__(self):
        return 'SelectionError(function={function}, message={message}, args={args})'.format(
            function=self.function.__name__,
            message=self.message,
            args=dict(
                [(k, v) for (k, v) in self.__dict__.items() if k != 'function' and k != 'message']
            )
        )

    def __str__(self):
        return repr(self)

    def __unicode__(self):
        return repr(self)

    def __bool__(self):
        return False


class ConfigSelectorDefinition:
    """
    Defines the metadata of a configuration selector.
    """

    def __repr__(self) -> str:
        return f'ConfigSelectorDefinition(function={self.function},' \
               f' parameters={self.parameters},' \
               f' message={self.message})'

    def __str__(self) -> str:
        return repr(self)

    def __init__(self,
                 function: Callable,
                 parameters: [ConfigSectionOptionDefinition],
                 message: str = None):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)

        if message is None:
            message = 'Value selection failed.'

        self.function = function
        self.parameters = parameters
        self.message = message

        self.logger.debug(self)

    def select(self, parent: wx.Window = None) -> SelectionResult or SelectionError:
        from utils.config import Config
        arg_names = inspect.getfullargspec(self.function)[0]
        args = [p.option_definition.get_value(Config().get_section(p.section_name))
                if type(p) == ConfigSectionOptionDefinition
                else p
                for p in self.parameters]

        if 'parent' in arg_names:
            result = self.function(parent, *args)
        else:
            result = self.function(*args)
        if not result:
            return SelectionError(self.function, self.message, dict(zip(arg_names, args)))
        return result
