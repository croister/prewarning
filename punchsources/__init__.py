import inspect

from typing import TYPE_CHECKING
from punchsources._base import _PunchSourceBase, _NOT_OVERRIDDEN
from punchsources.punch_source_olresultat_se import PunchSourceOlresultatSe
from utils.config import Config
from utils.config_definitions import ConfigOptionDefinition

if TYPE_CHECKING:
    _PunchSourceClass = type[_PunchSourceBase]
else:
    _PunchSourceClass = type

__all__: list[str] = []
PUNCH_SOURCES: dict[str, _PunchSourceClass]
COMMON_PUNCH_SOURCE: ConfigOptionDefinition

LOGGER_NAME = "PunchSources"

_module_initialized = False


def _ensure_init():
    global _module_initialized
    if _module_initialized:
        return
    _module_initialized = True

    _import_all_modules()
    _populate_punch_sources()
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


def _populate_punch_sources():
    global PUNCH_SOURCES
    PUNCH_SOURCES = dict()
    __all__.append("PUNCH_SOURCES")

    def add_punch_sources(classes):
        for cls in classes:
            if not inspect.isabstract(cls):
                PUNCH_SOURCES[cls.name] = cls
            add_punch_sources(cls.__subclasses__())

    add_punch_sources(_PunchSourceBase.__subclasses__())


def _validate_sources():
    if not PUNCH_SOURCES:
        raise RuntimeError("Error: No Punch Sources found.")
    if _NOT_OVERRIDDEN in PUNCH_SOURCES:
        source = PUNCH_SOURCES[_NOT_OVERRIDDEN]
        raise RuntimeError(
            f'Error: "{source.__name__}" must override the "name" variable.'
        )
    for punch_source_name, punch_source in PUNCH_SOURCES.items():
        if punch_source.display_name is _NOT_OVERRIDDEN:
            raise RuntimeError(
                f'Error: "{punch_source_name}" must override the "display_name" variable.'
            )
        if punch_source.description is _NOT_OVERRIDDEN:
            raise RuntimeError(
                f'Error: "{punch_source_name}" must override the "description" variable.'
            )


def _register_common_source():
    global COMMON_PUNCH_SOURCE
    COMMON_PUNCH_SOURCE = ConfigOptionDefinition(
        name="PunchSource",
        display_name="Punch Source",
        value_type=str,
        description="Determines the source from which Punches are fetched.",
        default_value=PunchSourceOlresultatSe.__qualname__,
        valid_values=list(PUNCH_SOURCES.keys()),
        mandatory=True,
        enables=[
            PUNCH_SOURCES[punch_source_name].config_section_definition()
            for punch_source_name in PUNCH_SOURCES
        ],
    )

    Config.register_config_option_definition(
        Config.SECTION_DATA_SOURCES, COMMON_PUNCH_SOURCE
    )
    __all__.append("COMMON_PUNCH_SOURCE")


def __getattr__(name):
    if name in ("PUNCH_SOURCES", "COMMON_PUNCH_SOURCE"):
        _ensure_init()
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
