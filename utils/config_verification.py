# -*- coding: utf-8 -*-

import inspect
import logging
from typing import Callable, Iterable, Tuple, Any

from utils.config_definitions import ConfigSectionOptionDefinition
from validators.validation_error import ValidationError


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
        args = [p.option_definition.get_value(Config().get_section(p.section_name))
                if type(p) == ConfigSectionOptionDefinition
                else p
                for p in self.parameters]

        result = self.function(*args)
        if not result:
            arg_names = inspect.getfullargspec(self.function)[0]
            return ValidationError(self.function, self.message, dict(zip(arg_names, args)))
        return True
