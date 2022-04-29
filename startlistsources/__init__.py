import inspect
import logging
import sys

from startlistsources import start_list_source_file, start_list_source_ola_mysql
from startlistsources._base import _StartListSourceBase
from startlistsources.start_list_source_ola_mysql import StartListSourceOlaMySql
from utils.config import Config
from utils.config_definitions import ConfigOptionDefinition


LOGGER_NAME = 'StartListSources'


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
START_LIST_SOURCES = dict()
__all__.append('START_LIST_SOURCES')


def add_start_list_sources(classes):
    for cls in classes:
        if not inspect.isabstract(cls):
            START_LIST_SOURCES[cls.name] = cls
        add_start_list_sources(cls.__subclasses__())


add_start_list_sources(_StartListSourceBase.__subclasses__())

if not START_LIST_SOURCES:
    logging.getLogger(LOGGER_NAME).error('Error: No Start List Sources found.')
    sys.exit(1)

if NotImplemented in START_LIST_SOURCES.keys():
    logging.getLogger(LOGGER_NAME).error('Error: "%s" must override the "name" variable.', str(START_LIST_SOURCES[NotImplemented].__qualname__))
    sys.exit(1)

COMMON_START_LIST_SOURCE = ConfigOptionDefinition(
    name='StartListSource',
    display_name='Start List Source',
    value_type=str,
    description='Determines the source of the Start List to look up team information from.',
    default_value=StartListSourceOlaMySql.__qualname__,
    valid_values=list(START_LIST_SOURCES.keys()),
    mandatory=True,
    enables=[START_LIST_SOURCES[start_list_source_name].config_section_definition()
             for start_list_source_name in START_LIST_SOURCES]
)

Config.register_config_option_definition(Config.SECTION_COMMON, COMMON_START_LIST_SOURCE)

for start_list_source_name in START_LIST_SOURCES:
    start_list_source = START_LIST_SOURCES[start_list_source_name]

    if start_list_source.display_name == NotImplemented:
        logging.getLogger(LOGGER_NAME).error('Error: "%s" must override the "display_name" variable.', start_list_source_name)
        sys.exit(1)

    if start_list_source.description == NotImplemented:
        logging.getLogger(LOGGER_NAME).error('Error: "%s" must override the "description" variable.', start_list_source_name)
        sys.exit(1)
