from unittest.mock import MagicMock, patch

import pytest
from pymysql import OperationalError

from utils.config import Config
from utils.config_definitions import ConfigSectionDefinition


@pytest.fixture(autouse=True)
def _patch_deps():
    with patch("watchdog.observers.Observer") as mock_obs:
        mock_obs.return_value.is_alive.return_value = False
        mock_obs.return_value.name = "MockedObserver"
        with (
            patch.object(Config, "register_config_section_listener"),
            patch("startlistsources.start_list_source_ola_mysql.OlaMySql") as mock_ola,
        ):
            mock_ola_instance = MagicMock()
            mock_ola.return_value = mock_ola_instance
            yield mock_ola_instance


class TestStartListSourceOlaMySql:
    @pytest.fixture
    def source(self, _patch_deps):
        from startlistsources.start_list_source_ola_mysql import StartListSourceOlaMySql

        return StartListSourceOlaMySql()

    def test_class_attributes(self):
        from startlistsources.start_list_source_ola_mysql import StartListSourceOlaMySql

        assert StartListSourceOlaMySql.name == "StartListSourceOlaMySql"
        assert StartListSourceOlaMySql.display_name == "OLA MySQL Start List Source"
        assert "OLA" in StartListSourceOlaMySql.description

    def test_config_section_definition(self):
        from startlistsources.start_list_source_ola_mysql import StartListSourceOlaMySql

        sd = StartListSourceOlaMySql.config_section_definition()
        assert isinstance(sd, ConfigSectionDefinition)
        assert sd.name == "StartListSourceOlaMySql"

    def test_initial_state_not_running(self, source):
        assert source.is_running() is False
        assert source._running is False

    def test_start_sets_running_and_updates(self, source):
        with patch.object(source, "update") as mock_update:
            source.start()
            assert source._running is True
            assert source.is_running() is True
            mock_update.assert_called_once()

    def test_stop_clears_running(self, source):
        source.start()
        assert source.is_running() is True
        source.stop()
        assert source.is_running() is False

    def test_str_repr(self, source):
        r = repr(source)
        assert "StartListSourceOlaMySQL" in r

    def test_on_modified_does_nothing(self, source):
        source.on_modified(None)

    def test_config_updated_calls_update(self, source):
        with patch.object(source, "update") as mock_update:
            source.config_updated(["some_section"])
            mock_update.assert_called_once()

    def test_update_calls_parse_config(self, source):
        with patch.object(source, "_parse_config") as mock_parse:
            source.update()
            mock_parse.assert_called_once()

    def test_parse_config_is_pass(self, source):
        result = source._parse_config()
        assert result is None

    def test_lookup_returns_none_when_not_running(self, source):
        result = source.lookup_from_card_number("12345")
        assert result is None

    def test_lookup_delegates_to_ola_mysql(self, _patch_deps, source):
        mock_ola = _patch_deps
        mock_ola.get_event_race_pre_warning_data.return_value = {
            "bibNumber": "101",
            "relayLeg": 1,
        }
        source._running = True
        result = source.lookup_from_card_number("12345")
        assert result == {"bibNumber": "101", "relayLeg": 1}
        mock_ola.get_event_race_pre_warning_data.assert_called_once_with("12345")

    def test_lookup_returns_none_on_operational_error(self, _patch_deps, source):
        mock_ola = _patch_deps
        mock_ola.get_event_race_pre_warning_data.side_effect = OperationalError(
            "connection lost"
        )
        source._running = True
        result = source.lookup_from_card_number("12345")
        assert result is None

    def test_lookup_does_not_call_ola_when_not_running(self, _patch_deps, source):
        mock_ola = _patch_deps
        result = source.lookup_from_card_number("12345")
        assert result is None
        mock_ola.get_event_race_pre_warning_data.assert_not_called()

    def test_get_bib_range_returns_none_when_not_running(self, source):
        result = source.get_bib_range()
        assert result is None

    def test_get_bib_range_delegates_to_ola_mysql(self, _patch_deps, source):
        mock_ola = _patch_deps
        mock_ola.get_bib_range.return_value = (1, 150)
        source._running = True
        result = source.get_bib_range()
        assert result == (1, 150)
        mock_ola.get_bib_range.assert_called_once()

    def test_get_bib_range_returns_none_on_operational_error(self, _patch_deps, source):
        mock_ola = _patch_deps
        mock_ola.get_bib_range.side_effect = OperationalError("connection lost")
        source._running = True
        result = source.get_bib_range()
        assert result is None

    def test_get_bib_range_does_not_call_ola_when_not_running(
        self, _patch_deps, source
    ):
        mock_ola = _patch_deps
        result = source.get_bib_range()
        assert result is None
        mock_ola.get_bib_range.assert_not_called()

    def test_get_team_count_returns_none_when_not_running(self, source):
        result = source.get_team_count()
        assert result is None

    def test_get_team_count_delegates_to_ola_mysql(self, _patch_deps, source):
        mock_ola = _patch_deps
        mock_ola.get_team_count.return_value = 42
        source._running = True
        result = source.get_team_count()
        assert result == 42
        mock_ola.get_team_count.assert_called_once()

    def test_get_team_count_returns_none_on_operational_error(
        self, _patch_deps, source
    ):
        mock_ola = _patch_deps
        mock_ola.get_team_count.side_effect = OperationalError("connection lost")
        source._running = True
        result = source.get_team_count()
        assert result is None

    def test_get_team_count_does_not_call_ola_when_not_running(
        self, _patch_deps, source
    ):
        mock_ola = _patch_deps
        result = source.get_team_count()
        assert result is None
        mock_ola.get_team_count.assert_not_called()

    def test_get_runner_count_returns_none_when_not_running(self, source):
        result = source.get_runner_count()
        assert result is None

    def test_get_runner_count_delegates_to_ola_mysql(self, _patch_deps, source):
        mock_ola = _patch_deps
        mock_ola.get_runner_count.return_value = 126
        source._running = True
        result = source.get_runner_count()
        assert result == 126
        mock_ola.get_runner_count.assert_called_once()

    def test_get_runner_count_returns_none_on_operational_error(
        self, _patch_deps, source
    ):
        mock_ola = _patch_deps
        mock_ola.get_runner_count.side_effect = OperationalError("connection lost")
        source._running = True
        result = source.get_runner_count()
        assert result is None

    def test_get_runner_count_does_not_call_ola_when_not_running(
        self, _patch_deps, source
    ):
        mock_ola = _patch_deps
        result = source.get_runner_count()
        assert result is None
        mock_ola.get_runner_count.assert_not_called()
