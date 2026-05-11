"""Tests for punchsources/__init__.py and startlistsources/__init__.py.

Package-level initialization (source discovery, validation, COMMON_* creation)
is lazy — triggered on first access to PUNCH_SOURCES or COMMON_PUNCH_SOURCE.
However, the explicit submodule imports still execute their module-level code
(config definitions, registration) at import time.
"""
import punchsources
import startlistsources


class TestPunchSourcesModule:
    def test_PUNCH_SOURCES_is_populated(self):
        assert len(punchsources.PUNCH_SOURCES) > 0

    def test_PUNCH_SOURCES_contains_expected_keys(self):
        assert 'PunchSourceOlresultatSe' in punchsources.PUNCH_SOURCES
        assert 'PunchSourceOlaMySql' in punchsources.PUNCH_SOURCES

    def test_COMMON_PUNCH_SOURCE_is_ConfigOptionDefinition(self):
        from utils.config_definitions import ConfigOptionDefinition
        assert isinstance(punchsources.COMMON_PUNCH_SOURCE, ConfigOptionDefinition)

    def test_COMMON_PUNCH_SOURCE_properties(self):
        c = punchsources.COMMON_PUNCH_SOURCE
        assert c.name == 'PunchSource'
        assert c.mandatory is True
        assert sorted(c.valid_values) == sorted(punchsources.PUNCH_SOURCES.keys())

    def test_LOGGER_NAME_is_not_overwritten_by_submodules(self):
        assert punchsources.LOGGER_NAME == 'PunchSources'

    def test_default_value_is_known_source(self):
        assert punchsources.COMMON_PUNCH_SOURCE.default_value in punchsources.PUNCH_SOURCES


class TestStartListSourcesModule:
    def test_START_LIST_SOURCES_is_populated(self):
        assert len(startlistsources.START_LIST_SOURCES) > 0

    def test_START_LIST_SOURCES_contains_expected_keys(self):
        assert 'StartListSourceOlaMySql' in startlistsources.START_LIST_SOURCES
        assert 'StartListSourceFile' in startlistsources.START_LIST_SOURCES

    def test_COMMON_START_LIST_SOURCE_is_ConfigOptionDefinition(self):
        from utils.config_definitions import ConfigOptionDefinition
        assert isinstance(startlistsources.COMMON_START_LIST_SOURCE, ConfigOptionDefinition)

    def test_COMMON_START_LIST_SOURCE_properties(self):
        c = startlistsources.COMMON_START_LIST_SOURCE
        assert c.name == 'StartListSource'
        assert c.mandatory is True
        assert sorted(c.valid_values) == sorted(startlistsources.START_LIST_SOURCES.keys())

    def test_LOGGER_NAME_is_not_overwritten_by_submodules(self):
        assert startlistsources.LOGGER_NAME == 'StartListSources'

    def test_default_value_is_known_source(self):
        assert startlistsources.COMMON_START_LIST_SOURCE.default_value in startlistsources.START_LIST_SOURCES
