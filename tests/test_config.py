from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils.config import Config
from utils.config_definitions import (
    ConfigOptionDefinition,
    ConfigSectionDefinition,
    RuntimeStateGroup,
    RuntimeStateOptionDefinition,
)

tmp_config_path = "/tmp/test_config.ini"


@pytest.fixture(autouse=True)
def reset_config_class_state():
    saved_defs = dict(Config.CONFIG_SECTION_DEFINITIONS)
    saved_listeners = dict(Config.CONFIG_SECTION_LISTENERS)
    Config.CONFIG_SECTION_DEFINITIONS = {}
    Config.CONFIG_SECTION_LISTENERS = {}
    yield
    Config.CONFIG_SECTION_DEFINITIONS = saved_defs
    Config.CONFIG_SECTION_LISTENERS = saved_listeners


# ---------------------------------------------------------------------------
# Class methods (no instance required)
# ---------------------------------------------------------------------------


class TestConfigRegisterConfigSectionDefinition:
    def test_register_section_definition(self):
        sd = ConfigSectionDefinition("test", "Test")
        Config.register_config_section_definition(sd)
        assert "test" in Config.CONFIG_SECTION_DEFINITIONS
        assert Config.CONFIG_SECTION_DEFINITIONS["test"] is sd

    def test_register_duplicate_section_definition_raises(self):
        Config.register_config_section_definition(ConfigSectionDefinition("dup", "Dup"))
        with pytest.raises(ValueError, match="Duplicate config section definition"):
            Config.register_config_section_definition(
                ConfigSectionDefinition("dup", "Dup")
            )

    def test_register_multiple_sections(self):
        s1 = ConfigSectionDefinition("a", "A")
        s2 = ConfigSectionDefinition("b", "B")
        Config.register_config_section_definition(s1)
        Config.register_config_section_definition(s2)
        assert set(Config.CONFIG_SECTION_DEFINITIONS.keys()) == {"a", "b"}

    def test_register_section_with_requires(self):
        other = ConfigSectionDefinition("other", "Other")
        sd = ConfigSectionDefinition("main", "Main", requires=[other])
        Config.register_config_section_definition(sd)
        assert sd in other.required_by

    def test_register_section_sorts_by_sort_key(self):
        a = ConfigSectionDefinition("b_section", "B", sort_key_prefix=200)
        b = ConfigSectionDefinition("a_section", "A", sort_key_prefix=100)
        Config.register_config_section_definition(a)
        Config.register_config_section_definition(b)
        keys = list(Config.CONFIG_SECTION_DEFINITIONS.keys())
        assert keys == ["a_section", "b_section"]

    def test_register_section_with_option_enables_section(self):
        opt = ConfigOptionDefinition("en", "En", bool, "desc", default_value=False)
        child = ConfigSectionDefinition("child", "Child")
        opt.enables.append(child)
        parent = ConfigSectionDefinition("parent", "Parent", [opt])
        Config.register_config_section_definition(parent)
        assert child.enabled_by is not None
        assert child.enabled_by.section_name == "parent"
        assert child.enabled_by.option_definition is opt

    def test_register_merges_with_temporary(self):
        Config._create_temporary_config_section_definition_if_needed("temp_sect")
        temp_name = "_temp_sect"
        assert temp_name in Config.CONFIG_SECTION_DEFINITIONS
        real = ConfigSectionDefinition("temp_sect", "Temp Sect")
        Config.register_config_section_definition(real)
        assert temp_name not in Config.CONFIG_SECTION_DEFINITIONS
        assert "temp_sect" in Config.CONFIG_SECTION_DEFINITIONS


class TestConfigRegisterOptionDefinition:
    def test_register_option_definition_creates_temp_section(self):
        opt = ConfigOptionDefinition("o", "O", str, "desc")
        Config.register_config_option_definition("new_sect", opt)
        assert "_new_sect" in Config.CONFIG_SECTION_DEFINITIONS

    def test_register_option_definition_adds_to_existing_section(self):
        sd = ConfigSectionDefinition("sect", "Sect")
        Config.register_config_section_definition(sd)
        opt = ConfigOptionDefinition("o", "O", str, "desc")
        Config.register_config_option_definition("sect", opt)
        assert "o" in Config.CONFIG_SECTION_DEFINITIONS["sect"].option_definitions

    def test_register_option_duplicate_raises(self):
        sd = ConfigSectionDefinition("sect", "Sect")
        Config.register_config_section_definition(sd)
        opt = ConfigOptionDefinition("o", "O", str, "desc")
        Config.register_config_option_definition("sect", opt)
        with pytest.raises(ValueError, match="already exists"):
            Config.register_config_option_definition("sect", opt)


class TestConfigCreateTemporarySection:
    def test_create_temp_section(self):
        result = Config._create_temporary_config_section_definition_if_needed(
            "new_sect"
        )
        assert result == "_new_sect"
        assert "_new_sect" in Config.CONFIG_SECTION_DEFINITIONS

    def test_existing_section_returns_name_as_is(self):
        sd = ConfigSectionDefinition("existing", "Existing")
        Config.register_config_section_definition(sd)
        result = Config._create_temporary_config_section_definition_if_needed(
            "existing"
        )
        assert result == "existing"

    def test_temp_already_exists_returns_temp_name(self):
        result1 = Config._create_temporary_config_section_definition_if_needed("sect")
        assert result1 == "_sect"
        result2 = Config._create_temporary_config_section_definition_if_needed("sect")
        assert result2 == "_sect"


class TestConfigRegisterSectionListener:
    def test_register_listener(self):
        sd = ConfigSectionDefinition("sect", "Sect")
        Config.register_config_section_definition(sd)
        listener = MagicMock()
        Config.register_config_section_listener("sect", listener)
        assert listener in Config.CONFIG_SECTION_LISTENERS["sect"]

    def test_register_listener_no_duplicate(self):
        sd = ConfigSectionDefinition("sect", "Sect")
        Config.register_config_section_definition(sd)
        listener = MagicMock()
        Config.register_config_section_listener("sect", listener)
        Config.register_config_section_listener("sect", listener)
        assert len(Config.CONFIG_SECTION_LISTENERS["sect"]) == 1

    def test_register_listener_unregistered_section_raises(self):
        with pytest.raises(ValueError, match="not registered"):
            Config.register_config_section_listener("nonexistent", MagicMock())


# ---------------------------------------------------------------------------
# Instance creation and basic instance methods
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_watchdog():
    mock_observer = MagicMock()
    with (
        patch("utils.config.Observer", return_value=mock_observer),
        patch("watchdog.events.LoggingEventHandler.__init__", return_value=None),
        patch.object(Config, "DEFAULT_CONFIG_FILE_LOCATION", Path(tmp_config_path)),
    ):
        yield mock_observer


class TestConfigInstance:
    def test_create_instance_sets_default_location(self, mock_watchdog):
        c = Config()
        assert "test_config.ini" in str(c.config_file_location)
        c.stop()

    def test_create_instance_with_path(self, mock_watchdog):
        with (
            patch.object(Path, "is_file", return_value=True),
            patch.object(Path, "is_absolute", return_value=True),
        ):
            c = Config(Path("/custom/path/config.ini"))
            assert c.config_file_location == Path("/custom/path/config.ini")
            c.stop()

    def test_create_instance_with_str_path(self, mock_watchdog):
        with (
            patch.object(Path, "is_file", return_value=True),
            patch.object(Path, "is_absolute", return_value=True),
        ):
            c = Config("/string/path/config.ini")
            assert c.config_file_location == Path("/string/path/config.ini")
            c.stop()

    def test_create_instance_makes_relative_path_absolute(self, mock_watchdog):
        with (
            patch.object(Path, "is_file", return_value=True),
            patch.object(Path, "is_absolute", return_value=False),
            patch.object(Path, "resolve", return_value=Path("/abs/path/config.ini")),
        ):
            c = Config("relative.ini")
            c.stop()

    def test_create_instance_starts_observer(self, mock_watchdog):
        c = Config()
        assert c.observer is mock_watchdog
        mock_watchdog.start.assert_called_once()
        c.stop()

    def test_stop_stops_observer(self, mock_watchdog):
        c = Config()
        c.stop()
        c.observer.stop.assert_called_once()
        c.observer.join.assert_called_once()

    def test_repr_str(self, mock_watchdog):
        c = Config()
        assert "config_file_location" in repr(c)
        assert "config_file_location" in str(c)
        c.stop()

    def test_singleton_returns_same_instance(self, mock_watchdog):
        c1 = Config()
        c2 = Config()
        assert c1 is c2
        c1.stop()

    def test_get_section_returns_section_proxy(self, mock_watchdog):
        c = Config()
        c.config.add_section("mysection")
        c.config["mysection"]["key"] = "val"
        section = c.get_section("mysection")
        assert section["key"] == "val"
        c.stop()

    def test_get_section_nonexistent_raises(self, mock_watchdog):
        c = Config()
        with pytest.raises(ValueError, match="not available"):
            c.get_section("nonexistent")
        c.stop()

    def test_update_live_section_option(self, mock_watchdog):
        c = Config()
        c.config.add_section("sect")
        c.prev_config_sections["sect"] = {}
        opt = ConfigOptionDefinition("opt", "Opt", str, "desc")
        c.update_live_section_option("sect", opt, "new_value")
        assert c.config["sect"]["opt"] == "new_value"
        assert c.prev_config_sections["sect"]["opt"] == "new_value"
        c.stop()

    def test_update_live_section_nonexistent_section_raises(self, mock_watchdog):
        c = Config()
        opt = ConfigOptionDefinition("opt", "Opt", str, "desc")
        with pytest.raises(ValueError, match="not available"):
            c.update_live_section_option("nonexistent", opt, "val")
        c.stop()

    def test_update_live_section_missing_prev_raises(self, mock_watchdog):
        c = Config()
        c.config.add_section("sect")
        opt = ConfigOptionDefinition("opt", "Opt", str, "desc")
        with pytest.raises(ValueError, match="not available in prev config"):
            c.update_live_section_option("sect", opt, "val")
        c.stop()


# ---------------------------------------------------------------------------
# Config file operations (mocked file I/O)
# ---------------------------------------------------------------------------


class TestConfigReadWrite:
    def test_read_config_with_registered_section(self, mock_watchdog):
        c = Config()
        c.config.add_section("sect")
        c.config["sect"]["opt"] = "val"
        sd = ConfigSectionDefinition(
            "sect", "Sect", [ConfigOptionDefinition("opt", "Opt", str, "desc")]
        )
        Config.register_config_section_definition(sd)
        c.config_sections["sect"] = c.config["sect"]
        c.prev_config_sections["sect"] = dict(c.config["sect"])
        c.stop()

    def test_write_removes_runtime_state_options(self, mock_watchdog, tmp_path):
        config_file = tmp_path / "config.ini"
        config_file.write_text("[sect]\nopt = val\nruntime = hidden\n")
        with patch.object(Config, "DEFAULT_CONFIG_FILE_LOCATION", config_file):
            c = Config()
            rsg = RuntimeStateGroup("sect_runtime.dat")
            sd = ConfigSectionDefinition(
                "sect",
                "Sect",
                [
                    ConfigOptionDefinition("opt", "Opt", str, "desc"),
                    RuntimeStateOptionDefinition(
                        rsg, "runtime", "Runtime", str, "desc"
                    ),
                ],
            )
            Config.register_config_section_definition(sd)
            c.read_config()
            c.write()
            content = config_file.read_text()
            assert "runtime" not in content
            assert "opt" in content
            c.stop()

    def test_validate_empty_with_no_sections(self, mock_watchdog):
        c = Config()
        result = c.validate()
        assert result == {}
        c.stop()

    def test_validate_with_valid_section(self, mock_watchdog):
        c = Config()
        c.config.add_section("sect")
        c.config["sect"]["opt"] = "val"
        c.config_sections["sect"] = c.config["sect"]
        opt = ConfigOptionDefinition("opt", "Opt", str, "desc")
        sd = ConfigSectionDefinition("sect", "Sect", [opt])
        Config.register_config_section_definition(sd)
        result = c.validate()
        assert result == {}
        c.stop()


# ---------------------------------------------------------------------------
# Notification logic
# ---------------------------------------------------------------------------


class TestConfigNotifications:
    def test_notify_updates_calls_listeners(self, mock_watchdog):
        c = Config()
        listener = MagicMock()
        sd = ConfigSectionDefinition("sect", "Sect")
        Config.register_config_section_definition(sd)
        Config.register_config_section_listener("sect", listener)
        c._notify_updates(["sect"])
        listener.config_updated.assert_called_once_with(["sect"])
        c.stop()

    def test_notify_updates_multiple_listeners(self, mock_watchdog):
        c = Config()
        l1 = MagicMock()
        l2 = MagicMock()
        sd = ConfigSectionDefinition("sect", "Sect")
        Config.register_config_section_definition(sd)
        Config.register_config_section_listener("sect", l1)
        Config.register_config_section_listener("sect", l2)
        c._notify_updates(["sect"])
        l1.config_updated.assert_called_once_with(["sect"])
        l2.config_updated.assert_called_once_with(["sect"])
        c.stop()

    def test_notify_updates_ignores_unregistered_section(self, mock_watchdog):
        c = Config()
        listener = MagicMock()
        c._notify_updates(["unknown_section"])
        listener.config_updated.assert_not_called()
        c.stop()

    def test_section_definition_changed_unknown_section_does_not_raise(
        self, mock_watchdog
    ):
        c = Config()
        c.config_section_definition_changed("nonexistent")
        c.stop()
