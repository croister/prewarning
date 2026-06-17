import inspect

from typing import TYPE_CHECKING
from startlistsources._base import _StartListSourceBase, _NOT_OVERRIDDEN
from startlistsources.start_list_source_ola_mysql import StartListSourceOlaMySql
from utils.config import Config
from utils.config_definitions import ConfigOptionDefinition

if TYPE_CHECKING:
    _StartListSourceClass = type[_StartListSourceBase]
else:
    _StartListSourceClass = type

__all__: list[str] = []
START_LIST_SOURCES: dict[str, _StartListSourceClass]
COMMON_START_LIST_SOURCE: ConfigOptionDefinition

LOGGER_NAME = "StartListSources"

_module_initialized = False


def _ensure_init():
    global _module_initialized
    if _module_initialized:
        return
    _module_initialized = True

    _import_all_modules()
    _populate_start_list_sources()
    _validate_sources()
    _register_common_source()


def _import_all_modules():
    import importlib
    import os
    import traceback

    globals_, locals_ = globals(), locals()

    os.chdir(os.path.dirname(__file__))
    for filename in os.listdir(os.getcwd()):
        if filename[0] != "_" and filename.split(".")[-1] in (
            "py",
            "pyw",
            "pyc",
            "pyo",
        ):
            modulename = filename.split(".")[0]
            package_module = ".".join([__name__, modulename])
            try:
                module = importlib.import_module(package_module)
            except Exception:
                traceback.print_exc()
                raise
            for name in module.__dict__:
                if not name.startswith("_"):
                    globals_[name] = module.__dict__[name]
                    __all__.append(name)


def _populate_start_list_sources():
    global START_LIST_SOURCES
    START_LIST_SOURCES = dict()
    __all__.append("START_LIST_SOURCES")

    def add_start_list_sources(classes):
        for cls in classes:
            if not inspect.isabstract(cls):
                START_LIST_SOURCES[cls.name] = cls
            add_start_list_sources(cls.__subclasses__())

    add_start_list_sources(_StartListSourceBase.__subclasses__())


def _validate_sources():
    if not START_LIST_SOURCES:
        raise RuntimeError("Error: No Start List Sources found.")
    if _NOT_OVERRIDDEN in START_LIST_SOURCES:
        source = START_LIST_SOURCES[_NOT_OVERRIDDEN]
        raise RuntimeError(
            f'Error: "{source.__qualname__}" must override the "name" variable.'
        )
    for source_name, source in START_LIST_SOURCES.items():
        if source.display_name is _NOT_OVERRIDDEN:
            raise RuntimeError(
                f'Error: "{source_name}" must override the "display_name" variable.'
            )
        if source.description is _NOT_OVERRIDDEN:
            raise RuntimeError(
                f'Error: "{source_name}" must override the "description" variable.'
            )


def _register_common_source():
    global COMMON_START_LIST_SOURCE
    COMMON_START_LIST_SOURCE = ConfigOptionDefinition(
        name="StartListSource",
        display_name="Start List Source",
        value_type=str,
        description="Determines the source of the Start List to look up team information from.",
        default_value=StartListSourceOlaMySql.__qualname__,
        valid_values=list(START_LIST_SOURCES.keys()),
        mandatory=True,
        enables=[
            START_LIST_SOURCES[source_name].config_section_definition()
            for source_name in START_LIST_SOURCES
        ],
    )

    Config.register_config_option_definition(
        Config.SECTION_DATA_SOURCES, COMMON_START_LIST_SOURCE
    )
    __all__.append("COMMON_START_LIST_SOURCE")


def __getattr__(name):
    if name in ("START_LIST_SOURCES", "COMMON_START_LIST_SOURCE"):
        _ensure_init()
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
