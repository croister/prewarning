from unittest.mock import MagicMock, patch

from utils.ola_mysql import (
    _generate_in_format_str,
    EventForm,
    EventFormType,
    connect,
    get_database_names,
    is_ola_database,
    get_ola_db_version,
    get_events,
    get_event,
    is_valid_event,
    is_relay_event,
    get_event_races,
    is_valid_event_race,
    are_valid_event_race_control_ids,
    _verify_connection_parameters,
    _select_database,
    _verify_database,
    _select_event,
    _verify_event,
    _select_event_race,
    _verify_event_race,
)


class TestGenerateInFormatStr:
    def test_single_value(self):
        assert _generate_in_format_str(1) == "%s"

    def test_multiple_values(self):
        assert _generate_in_format_str(3) == "%s, %s, %s"

    def test_zero_values(self):
        assert _generate_in_format_str(0) == ""


class TestEventForm:
    def test_values(self):
        assert EventForm.INDIVIDUAL_SINGLE_DAY.value == "IndSingleDay"
        assert EventForm.INDIVIDUAL_MULTI_DAY.value == "IndMultiDay"
        assert EventForm.TEAM_SINGLE_DAY.value == "TeamSingleDay"
        assert EventForm.TEAM_MULTI_DAY.value == "TeamMultiDay"
        assert EventForm.RELAY_SINGLE_DAY.value == "RelaySingleDay"
        assert EventForm.RELAY_MULTI_DAY.value == "RelayMultiDay"
        assert EventForm.PATROL_SINGLE_DAY.value == "PatrolSingleDay"
        assert EventForm.PATROL_MULTI_DAY.value == "PatrolMultiDay"

    def test_str(self):
        assert str(EventForm.RELAY_SINGLE_DAY) == "RelaySingleDay"

    def test_eq_with_string(self):
        assert EventForm.RELAY_SINGLE_DAY == "RelaySingleDay"
        assert EventForm.RELAY_SINGLE_DAY != "Other"

    def test_as_list(self):
        assert EventForm.RELAY_SINGLE_DAY.as_list() == [EventForm.RELAY_SINGLE_DAY]

    def test_as_str_list(self):
        assert EventForm.RELAY_SINGLE_DAY.as_str_list() == ["RelaySingleDay"]


class TestEventFormType:
    def test_individual(self):
        assert EventForm.INDIVIDUAL_SINGLE_DAY in EventFormType.INDIVIDUAL.value
        assert EventForm.INDIVIDUAL_MULTI_DAY in EventFormType.INDIVIDUAL.value

    def test_relay(self):
        assert EventForm.RELAY_SINGLE_DAY in EventFormType.RELAY.value
        assert EventForm.RELAY_MULTI_DAY in EventFormType.RELAY.value

    def test_eq_with_string(self):
        assert EventFormType.RELAY == "RelaySingleDay"
        assert EventFormType.RELAY == "RelayMultiDay"
        assert EventFormType.RELAY != "IndSingleDay"

    def test_eq_with_event_form(self):
        assert EventFormType.RELAY == EventForm.RELAY_SINGLE_DAY

    def test_as_list(self):
        result = EventFormType.ALL.as_list()
        assert len(result) == 8
        assert EventForm.INDIVIDUAL_SINGLE_DAY in result
        assert EventForm.RELAY_MULTI_DAY in result

    def test_as_str_list(self):
        result = EventFormType.ALL.as_str_list()
        assert "RelaySingleDay" in result
        assert "IndSingleDay" in result

    def test_str(self):
        result = str(EventFormType.RELAY)
        assert "RelaySingleDay" in result


class TestConnect:
    def test_calls_pymysql_connect(self):
        with patch("utils.ola_mysql.pymysql.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn

            result = connect("host1", "user1", "pass1", "db1")

            assert result is mock_conn
            args, kwargs = mock_connect.call_args
            assert kwargs["host"] == "host1"
            assert kwargs["user"] == "user1"
            assert kwargs["database"] == "db1"
            from pymysql.cursors import DictCursor

            assert kwargs["cursorclass"] is DictCursor

    def test_connect_without_database(self):
        with patch("utils.ola_mysql.pymysql.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn

            result = connect("host1", "user1", "pass1")

            assert result is mock_conn
            args, kwargs = mock_connect.call_args
            assert kwargs["host"] == "host1"
            assert kwargs["database"] is None


class TestGetDatabaseNames:
    def test_returns_non_builtin_databases(self):
        mock_cursor = MagicMock()
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            {"Database": "ola_db"},
            {"Database": "information_schema"},
            {"Database": "test"},
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        result = get_database_names(mock_conn)

        assert result == ["ola_db", "test"]

    def test_empty_when_all_builtin(self):
        mock_cursor = MagicMock()
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            {"Database": "information_schema"},
            {"Database": "mysql"},
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        result = get_database_names(mock_conn)

        assert result == []

    def test_ignores_missing_key(self):
        mock_cursor = MagicMock()
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            {"Database": "ola_db"},
            {"other": "value"},
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        result = get_database_names(mock_conn)

        assert result == ["ola_db"]


class TestIsOlaDatabase:
    def test_true_when_version_nonzero(self):
        mock_conn = MagicMock()
        with patch("utils.ola_mysql.get_ola_db_version", return_value=565):
            assert is_ola_database(mock_conn) is True

    def test_false_when_version_zero(self):
        mock_conn = MagicMock()
        with patch("utils.ola_mysql.get_ola_db_version", return_value=0):
            assert is_ola_database(mock_conn) is False


class TestGetOlaDbVersion:
    def test_returns_max_version(self):
        mock_cursor = MagicMock()
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            {"versionNumber": 100, "comment": "", "moduleId": 1},
            {"versionNumber": 565, "comment": "", "moduleId": 2},
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        assert get_ola_db_version(mock_conn) == 565

    def test_zero_when_no_versions(self):
        mock_cursor = MagicMock()
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        assert get_ola_db_version(mock_conn) == 0


class TestGetEvents:
    def test_returns_events(self):
        mock_cursor = MagicMock()
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            {"eventId": 1, "name": "Event 1", "eventForm": "RelaySingleDay"},
            {"eventId": 2, "name": "Event 2", "eventForm": "IndSingleDay"},
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        result = get_events(mock_conn, EventFormType.RELAY)

        assert len(result) == 2

    def test_defaults_to_all(self):
        mock_cursor = MagicMock()
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        result = get_events(mock_conn)

        assert result == []


class TestGetEvent:
    def test_returns_event(self):
        mock_cursor = MagicMock()
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {"eventId": 1, "name": "Test"}
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        result = get_event(mock_conn, 1)

        assert result["eventId"] == 1

    def test_returns_none_when_not_found(self):
        mock_cursor = MagicMock()
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        assert get_event(mock_conn, 999) is None


class TestIsValidEvent:
    def test_valid_when_event_exists_and_correct_type(self):
        mock_conn = MagicMock()
        with patch(
            "utils.ola_mysql.get_event", return_value={"eventForm": "RelaySingleDay"}
        ):
            assert is_valid_event(mock_conn, 1, EventFormType.RELAY) is True

    def test_invalid_when_event_not_found(self):
        mock_conn = MagicMock()
        with patch("utils.ola_mysql.get_event", return_value=None):
            assert is_valid_event(mock_conn, 1) is False

    def test_invalid_when_wrong_type(self):
        mock_conn = MagicMock()
        with patch(
            "utils.ola_mysql.get_event", return_value={"eventForm": "IndSingleDay"}
        ):
            assert is_valid_event(mock_conn, 1, EventFormType.RELAY) is False


class TestIsRelayEvent:
    def test_relay_event(self):
        mock_conn = MagicMock()
        with patch("utils.ola_mysql.is_valid_event", return_value=True):
            assert is_relay_event(mock_conn, 1) is True

    def test_not_relay_event(self):
        mock_conn = MagicMock()
        with patch("utils.ola_mysql.is_valid_event", return_value=False):
            assert is_relay_event(mock_conn, 1) is False


class TestGetEventRaces:
    def test_returns_event_races(self):
        mock_cursor = MagicMock()
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            {"eventRaceId": 1, "name": "Race 1"},
            {"eventRaceId": 2, "name": "Race 2"},
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        result = get_event_races(mock_conn, 1)

        assert len(result) == 2


class TestIsValidEventRace:
    def test_valid_when_in_list(self):
        mock_conn = MagicMock()
        with patch(
            "utils.ola_mysql.get_event_races",
            return_value=[
                {"eventRaceId": 1},
                {"eventRaceId": 2},
                {"eventRaceId": 3},
            ],
        ):
            assert is_valid_event_race(mock_conn, 1, 2) is True

    def test_invalid_when_not_in_list(self):
        mock_conn = MagicMock()
        with patch(
            "utils.ola_mysql.get_event_races",
            return_value=[
                {"eventRaceId": 1},
                {"eventRaceId": 3},
            ],
        ):
            assert is_valid_event_race(mock_conn, 1, 2) is False


class TestAreValidEventRaceControlIds:
    def test_valid_when_all_in_list(self):
        mock_conn = MagicMock()
        with patch(
            "utils.ola_mysql.get_event_race_split_time_controls",
            return_value=[
                {"ID": 101},
                {"ID": 102},
                {"ID": 103},
            ],
        ):
            assert (
                are_valid_event_race_control_ids(mock_conn, 565, True, 1, [101, 102])
                is True
            )

    def test_invalid_when_some_missing(self):
        mock_conn = MagicMock()
        with patch(
            "utils.ola_mysql.get_event_race_split_time_controls",
            return_value=[
                {"ID": 101},
                {"ID": 103},
            ],
        ):
            assert (
                are_valid_event_race_control_ids(mock_conn, 565, True, 1, [101, 102])
                is False
            )

    def test_false_when_empty(self):
        mock_conn = MagicMock()
        assert are_valid_event_race_control_ids(mock_conn, 565, True, 1, []) is False


class TestVerifyConnectionParameters:
    def test_returns_true_on_success(self):
        mock_conn = MagicMock()
        with patch("utils.ola_mysql.connect", return_value=mock_conn):
            assert _verify_connection_parameters("host", "user", "pass") is True
            mock_conn.close.assert_called_once()

    def test_returns_false_on_exception(self):
        with patch("utils.ola_mysql.connect", side_effect=Exception("fail")):
            assert _verify_connection_parameters("host", "user", "pass") is False


class TestSelectDatabase:
    def test_returns_selection(self):
        mock_conn = MagicMock()
        with (
            patch("utils.ola_mysql.connect", return_value=mock_conn),
            patch("utils.ola_mysql.get_database_names", return_value=["db1", "db2"]),
        ):
            result = _select_database("host", "user", "pass")

            assert result is not False
            assert len(result.values) == 2
            assert result.values[0].value == "db1"

    def test_returns_false_on_exception(self):
        with patch("utils.ola_mysql.connect", side_effect=Exception("fail")):
            assert _select_database("host", "user", "pass") is False


class TestVerifyDatabase:
    def test_returns_true_when_ola(self):
        mock_conn = MagicMock()
        with (
            patch("utils.ola_mysql.connect", return_value=mock_conn),
            patch("utils.ola_mysql.is_ola_database", return_value=True),
        ):
            assert _verify_database("host", "user", "pass", "db") is True

    def test_returns_false_when_not_ola(self):
        mock_conn = MagicMock()
        with (
            patch("utils.ola_mysql.connect", return_value=mock_conn),
            patch("utils.ola_mysql.is_ola_database", return_value=False),
        ):
            assert _verify_database("host", "user", "pass", "db") is False

    def test_returns_false_on_exception(self):
        with patch("utils.ola_mysql.connect", side_effect=Exception("fail")):
            assert _verify_database("host", "user", "pass", "db") is False


class TestSelectEvent:
    def test_returns_selection(self):
        mock_conn = MagicMock()
        with (
            patch("utils.ola_mysql.connect", return_value=mock_conn),
            patch(
                "utils.ola_mysql.get_events",
                return_value=[
                    {
                        "eventId": 1,
                        "name": "E1",
                        "eventForm": "Relay",
                        "startDate": "2024-01-01",
                        "finishDate": "2024-01-01",
                    },
                ],
            ),
        ):
            result = _select_event("host", "user", "pass", "db")

            assert result is not False
            assert result.values[0].value == 1

    def test_returns_false_when_no_events(self):
        mock_conn = MagicMock()
        with (
            patch("utils.ola_mysql.connect", return_value=mock_conn),
            patch("utils.ola_mysql.get_events", return_value=[]),
        ):
            assert _select_event("host", "user", "pass", "db") is False


class TestVerifyEvent:
    def test_returns_true_when_valid(self):
        mock_conn = MagicMock()
        with (
            patch("utils.ola_mysql.connect", return_value=mock_conn),
            patch("utils.ola_mysql.is_valid_event", return_value=True),
        ):
            assert _verify_event("host", "user", "pass", "db", 1) is True

    def test_returns_false_when_invalid(self):
        mock_conn = MagicMock()
        with (
            patch("utils.ola_mysql.connect", return_value=mock_conn),
            patch("utils.ola_mysql.is_valid_event", return_value=False),
        ):
            assert _verify_event("host", "user", "pass", "db", 1) is False


class TestSelectEventRace:
    def test_returns_selection(self):
        mock_conn = MagicMock()
        with (
            patch("utils.ola_mysql.connect", return_value=mock_conn),
            patch(
                "utils.ola_mysql.get_event_races",
                return_value=[
                    {
                        "eventRaceId": 10,
                        "name": "R1",
                        "raceLightCondition": "Day",
                        "raceDistance": "5km",
                        "raceDate": "2024-01-01",
                    },
                ],
            ),
        ):
            result = _select_event_race("host", "user", "pass", "db", 1)

            assert result is not False
            assert result.values[0].value == 10


class TestVerifyEventRace:
    def test_returns_true_when_valid(self):
        mock_conn = MagicMock()
        with (
            patch("utils.ola_mysql.connect", return_value=mock_conn),
            patch("utils.ola_mysql.is_valid_event_race", return_value=True),
        ):
            assert _verify_event_race("host", "user", "pass", "db", 1, 10) is True

    def test_returns_false_when_invalid(self):
        mock_conn = MagicMock()
        with (
            patch("utils.ola_mysql.connect", return_value=mock_conn),
            patch("utils.ola_mysql.is_valid_event_race", return_value=False),
        ):
            assert _verify_event_race("host", "user", "pass", "db", 1, 10) is False
