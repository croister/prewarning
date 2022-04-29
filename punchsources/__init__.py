import inspect
import logging
import sys

from punchsources import punch_source_olresultat_se, punch_source_ola_mysql
from punchsources._base import _PunchSourceBase
from punchsources.punch_source_olresultat_se import PunchSourceOlresultatSe
from utils.config import Config
from utils.config_definitions import ConfigOptionDefinition


LOGGER_NAME = 'PunchSources'


def _import_all_modules():
    """ Dynamically imports all modules in this package. """
    import importlib
    import os
    import traceback
    global __all__
    __all__ = []
    globals_, locals_ = globals(), locals()

    # Dynamically import all the package modules in this file's directory.
    os.chdir(os.path.dirname(__file__))
    for filename in os.listdir(os.getcwd()):
        # Process all python files in directory that don't start
        # with underscore (which also prevents this module from
        # importing itself).
        if filename[0] != '_' and filename.split('.')[-1] in ('py', 'pyw', 'pyc', 'pyo'):
            modulename = filename.split('.')[0]  # Filename sans extension.
            package_module = '.'.join([__name__, modulename])
            try:
                module = importlib.import_module(package_module)
            except Exception:
                traceback.print_exc()
                raise
            for name in module.__dict__:
                if not name.startswith('_'):
                    globals_[name] = module.__dict__[name]
                    __all__.append(name)


_import_all_modules()

""" Dynamically generated dict with all available Start List Sources. """
PUNCH_SOURCES = dict()
__all__.append('PUNCH_SOURCES')


def add_punch_sources(classes):
    for cls in classes:
        if not inspect.isabstract(cls):
            PUNCH_SOURCES[cls.name] = cls
        add_punch_sources(cls.__subclasses__())


add_punch_sources(_PunchSourceBase.__subclasses__())

if not PUNCH_SOURCES:
    logging.getLogger(LOGGER_NAME).error('Error: No Punch Sources found.')
    sys.exit(1)

if NotImplemented in PUNCH_SOURCES.keys():
    logging.getLogger(LOGGER_NAME).error('Error: "%s" must override the "name" variable.', str(PUNCH_SOURCES[NotImplemented].__name__))
    sys.exit(1)

COMMON_PUNCH_SOURCE = ConfigOptionDefinition(
    name='PunchSource',
    display_name='Punch Source',
    value_type=str,
    description='Determines the source from which Punches are fetched.',
    default_value=PunchSourceOlresultatSe.__qualname__,
    valid_values=list(PUNCH_SOURCES.keys()),
    mandatory=True,
    enables=[PUNCH_SOURCES[punch_source_name].config_section_definition() for punch_source_name in PUNCH_SOURCES]
)

Config.register_config_option_definition(Config.SECTION_COMMON, COMMON_PUNCH_SOURCE)

for punch_source_name in PUNCH_SOURCES:
    punch_source = PUNCH_SOURCES[punch_source_name]

    if punch_source.display_name == NotImplemented:
        logging.getLogger(LOGGER_NAME).error('Error: "%s" must override the "display_name" variable.', punch_source_name)
        sys.exit(1)

    if punch_source.description == NotImplemented:
        logging.getLogger(LOGGER_NAME).error('Error: "%s" must override the "description" variable.', punch_source_name)
        sys.exit(1)
