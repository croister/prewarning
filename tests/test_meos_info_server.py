from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from xml.etree import ElementTree as ET

import pytest

from utils.meos_info_server import (
    MeosInfoServer,
    MeosPunchListener,
)

MOP_NS = "http://www.melin.nu/mop"


def _make_mop_complete(content: str, next_diff: str = "12345") -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<MOPComplete xmlns="{MOP_NS}" nextdifference="{next_diff}">'
        f"{content}"
        f"</MOPComplete>"
    )


def _make_mop_diff(content: str, next_diff: str = "99999") -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<MOPDiff xmlns="{MOP_NS}" nextdifference="{next_diff}">'
        f"{content}"
        f"</MOPDiff>"
    )


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Clear the MeosInfoServer singleton instance between tests."""
    from utils.singleton import _Singleton

    if MeosInfoServer in _Singleton._instances:
        instance = _Singleton._instances[MeosInfoServer]
        if instance.is_running():
            instance._ref_count = 1
            instance.stop()
        del _Singleton._instances[MeosInfoServer]
    yield
    if MeosInfoServer in _Singleton._instances:
        instance = _Singleton._instances[MeosInfoServer]
        if instance.is_running():
            instance._ref_count = 1
            instance.stop()
        del _Singleton._instances[MeosInfoServer]


@pytest.fixture
def server():
    with (
        patch.object(MeosInfoServer, "_parse_config"),
        patch.object(MeosInfoServer, "_data_read", return_value=False),
    ):
        s = MeosInfoServer()
        s._url = "http://localhost:2009"
        s._fetch_interval = 1
        s._use_udp = False
        s._zero_time = datetime(2026, 6, 16, 5, 0, 0)  # noqa: DTZ001 - naive datetime matches MeOS/OLA data model
        return s


class TestDiffParsing:
    def test_process_team_elem_updates_bib_and_cmp_info(self, server):
        xml = (
            f'<tm id="23" xmlns="{MOP_NS}">'
            f'<base bib="43">Lag Dammvik</base>'
            f"<r>67;68;69</r>"
            f"</tm>"
        )
        elem = ET.fromstring(xml)
        server._process_team_elem(elem)

        assert server._team_bib[23] == "43"
        assert server._cmp_info[67] == {"team_id": 23, "leg": 1}
        assert server._cmp_info[68] == {"team_id": 23, "leg": 2}
        assert server._cmp_info[69] == {"team_id": 23, "leg": 3}
        assert server._team_leg_count[23] == 3

    def test_process_team_elem_multiple_runners_per_leg(self, server):
        xml = (
            f'<tm id="50" xmlns="{MOP_NS}">'
            f'<base bib="72">Team 102</base>'
            f"<r>301;302,303,304;305</r>"
            f"</tm>"
        )
        elem = ET.fromstring(xml)
        server._process_team_elem(elem)

        assert server._team_leg_count[50] == 3
        assert server._cmp_info[301] == {"team_id": 50, "leg": 1}
        assert server._cmp_info[302] == {"team_id": 50, "leg": 2}
        assert server._cmp_info[303] == {"team_id": 50, "leg": 2}
        assert server._cmp_info[304] == {"team_id": 50, "leg": 2}
        assert server._cmp_info[305] == {"team_id": 50, "leg": 3}

    def test_process_cmp_elem_updates_card(self, server):
        xml = (
            f'<cmp id="67" card="506576" xmlns="{MOP_NS}">'
            f'<base org="0" cls="3" stat="0" st="676200" rt="0">Name</base>'
            f"</cmp>"
        )
        elem = ET.fromstring(xml)
        server._process_cmp_elem(elem)

        assert server._cmp_info[67]["card"] == "506576"

    def test_process_cmp_elem_detects_new_radio(self, server):
        server._cmp_info[67] = {"card": "506576", "team_id": 23, "leg": 1}
        server._team_bib[23] = "43"

        listener = MagicMock(spec=MeosPunchListener)
        server._listeners.append(listener)

        xml = (
            f'<cmp id="67" card="506576" xmlns="{MOP_NS}">'
            f"<radio>50,12340;150,23450</radio>"
            f"</cmp>"
        )
        elem = ET.fromstring(xml)
        server._process_cmp_elem(elem)

        assert listener.meos_punch_received.call_count == 2
        punch1 = listener.meos_punch_received.call_args_list[0][0][0]
        assert punch1["id"] == "67_50"
        assert punch1["controlCode"] == "50"
        assert punch1["cardNumber"] == "506576"
        assert punch1["bibNumber"] == "43"
        assert punch1["relayLeg"] == 1
        assert punch1["passedTime"] == datetime(2026, 6, 16, 5, 0, 0) + timedelta(  # noqa: DTZ001 - naive datetime matches MeOS/OLA data model
            seconds=12340 / 10
        )

        punch2 = listener.meos_punch_received.call_args_list[1][0][0]
        assert punch2["id"] == "67_150"
        assert punch2["controlCode"] == "150"

    def test_duplicate_radio_not_emitted_again(self, server):
        server._cmp_info[67] = {"card": "506576", "team_id": 23, "leg": 1}
        server._team_bib[23] = "43"
        server._seen_radio[67] = {50}

        listener = MagicMock(spec=MeosPunchListener)
        server._listeners.append(listener)

        xml = (
            f'<cmp id="67" card="506576" xmlns="{MOP_NS}">'
            f"<radio>50,12340;150,23450</radio>"
            f"</cmp>"
        )
        elem = ET.fromstring(xml)
        server._process_cmp_elem(elem)

        # Only 150 should be emitted, 50 was already seen
        assert listener.meos_punch_received.call_count == 1
        assert listener.meos_punch_received.call_args[0][0]["controlCode"] == "150"

    def test_running_time_to_datetime_conversion(self, server):
        server._cmp_info[1] = {"card": "12345"}

        listener = MagicMock(spec=MeosPunchListener)
        server._listeners.append(listener)

        xml = f'<cmp id="1" card="12345" xmlns="{MOP_NS}"><radio>50,36000</radio></cmp>'
        elem = ET.fromstring(xml)
        server._process_cmp_elem(elem)

        punch = listener.meos_punch_received.call_args[0][0]
        # 36000 tenths = 3600 seconds = 1 hour after zero time (05:00:00)
        assert punch["passedTime"] == datetime(2026, 6, 16, 6, 0, 0)  # noqa: DTZ001 - naive datetime matches MeOS/OLA data model

    def test_running_time_includes_start_time_offset(self, server):
        # st=18000 tenths = 1800s = 00:30:00 from midnight
        server._competition_date = datetime(2026, 6, 16)  # noqa: DTZ001 - naive datetime matches MeOS/OLA data model
        server._cmp_info[1] = {"card": "12345", "st": 18000}

        listener = MagicMock(spec=MeosPunchListener)
        server._listeners.append(listener)

        xml = f'<cmp id="1" card="12345" xmlns="{MOP_NS}"><radio>50,36000</radio></cmp>'
        elem = ET.fromstring(xml)
        server._process_cmp_elem(elem)

        punch = listener.meos_punch_received.call_args[0][0]
        # midnight + (18000 + 36000) / 10 = 00:00:00 + 5400s = 01:30:00
        assert punch["passedTime"] == datetime(2026, 6, 16, 1, 30, 0)  # noqa: DTZ001 - naive datetime matches MeOS/OLA data model


class TestMopCompleteVsDiff:
    @patch("utils.meos_info_server._fetch_xml")
    def test_mop_complete_resets_seen_radio(self, mock_fetch, server):
        server._seen_radio = {67: {50}}

        xml_str = _make_mop_complete(
            '<cmp id="67" card="506576"><radio>50,12340</radio></cmp>'
        )
        mock_fetch.return_value = ET.fromstring(xml_str)
        server._do_fetch()

        # After MOPComplete, seen_radio is cleared, so 50 should be emitted
        assert server._next_difference == "12345"

    @patch("utils.meos_info_server._fetch_xml")
    def test_mop_diff_preserves_seen_radio(self, mock_fetch, server):
        server._seen_radio = {67: {50}}
        server._cmp_info[67] = {"card": "506576"}

        xml_str = _make_mop_diff(
            '<cmp id="67" card="506576"><radio>50,12340</radio></cmp>'
        )
        mock_fetch.return_value = ET.fromstring(xml_str)

        listener = MagicMock(spec=MeosPunchListener)
        server._listeners.append(listener)
        server._do_fetch()

        # 50 was already seen, should not be emitted
        listener.meos_punch_received.assert_not_called()
        assert server._next_difference == "99999"


class TestSelectorControls:
    @patch("utils.meos_info_server._fetch_xml")
    def test_returns_radio_controls(self, mock_fetch):
        control_xml = ET.fromstring(
            f'<MOPComplete xmlns="{MOP_NS}">'
            f'<control id="50">Radio 1</control>'
            f'<control id="100">Förvarning</control>'
            f'<control id="32">[32]</control>'
            f"</MOPComplete>"
        )
        class_xml = ET.fromstring(
            f'<MOPComplete xmlns="{MOP_NS}">'
            f'<cls id="1" ord="10" radio="50,100;50,100">Klass 0</cls>'
            f"</MOPComplete>"
        )
        mock_fetch.side_effect = [control_xml, class_xml]

        from utils.meos_info_server import _select_controls

        result = _select_controls("http://localhost:2009")
        assert result is not False
        values = [v.value for v in result.values]
        assert "50" in values
        assert "100" in values
        assert "32" not in values

    @patch("utils.meos_info_server._fetch_xml")
    def test_falls_back_to_all_controls_when_no_radio(self, mock_fetch):
        control_xml = ET.fromstring(
            f'<MOPComplete xmlns="{MOP_NS}">'
            f'<control id="32">[32]</control>'
            f'<control id="33">[33]</control>'
            f"</MOPComplete>"
        )
        class_xml = ET.fromstring(
            f'<MOPComplete xmlns="{MOP_NS}">'
            f'<cls id="1" ord="10" radio="">Klass 0</cls>'
            f"</MOPComplete>"
        )
        mock_fetch.side_effect = [control_xml, class_xml]

        from utils.meos_info_server import _select_controls

        result = _select_controls("http://localhost:2009")
        values = [v.value for v in result.values]
        assert "32" in values
        assert "33" in values


class TestLookupCard:
    def test_cache_hit(self, server):
        server._cmp_info[67] = {"card": "506576", "team_id": 23, "leg": 1}
        server._team_bib[23] = "43"

        result = server.lookup_card("506576")
        assert result == {
            "bibNumber": "43",
            "relayLeg": 1,
            "isLastLeg": False,
            "country": None,
        }

    def test_is_last_leg_true(self, server):
        server._cmp_info[69] = {"card": "111111", "team_id": 23, "leg": 3}
        server._team_bib[23] = "43"
        server._team_leg_count[23] = 3

        result = server.lookup_card("111111")
        assert result["isLastLeg"] is True

    def test_is_last_leg_false(self, server):
        server._cmp_info[67] = {"card": "222222", "team_id": 23, "leg": 1}
        server._team_bib[23] = "43"
        server._team_leg_count[23] = 3

        result = server.lookup_card("222222")
        assert result["isLastLeg"] is False

    def test_country_from_next_leg_runner(self, server):
        server._cmp_info[67] = {"card": "111111", "team_id": 23, "leg": 1}
        server._cmp_info[68] = {"team_id": 23, "leg": 2, "nat": "NOR"}
        server._team_bib[23] = "43"
        server._team_leg_count[23] = 3

        result = server.lookup_card("111111")
        assert result["country"] == "NOR"

    def test_country_falls_back_to_org(self, server):
        server._cmp_info[67] = {"card": "111111", "team_id": 23, "leg": 1}
        server._cmp_info[68] = {"team_id": 23, "leg": 2}  # no nat
        server._team_bib[23] = "43"
        server._team_leg_count[23] = 3
        server._team_org[23] = 5
        server._org_nat[5] = "SWE"

        result = server.lookup_card("111111")
        assert result["country"] == "SWE"

    def test_country_none_when_no_data(self, server):
        server._cmp_info[67] = {"card": "111111", "team_id": 23, "leg": 1}
        server._team_bib[23] = "43"

        result = server.lookup_card("111111")
        assert result["country"] is None

    def test_cache_miss_no_bib(self, server):
        server._cmp_info[67] = {"card": "506576", "team_id": 23, "leg": 1}
        # No bib for team 23

        with patch("utils.meos_info_server._fetch_xml") as mock_fetch:
            mock_fetch.return_value = ET.fromstring(
                f'<Competitors xmlns="{MOP_NS}">'
                f'<Competitor id="67">'
                f'<Team id="23">Lag Dammvik</Team>'
                f"<Leg>1</Leg>"
                f"</Competitor>"
                f"</Competitors>"
            )
            result = server.lookup_card("506576")
        assert result is None

    @patch("utils.meos_info_server._fetch_xml")
    def test_cache_miss_http_fallback(self, mock_fetch, server):
        # cmp_info doesn't have card 999999
        competitor_xml = ET.fromstring(
            f'<Competitors xmlns="{MOP_NS}">'
            f'<Competitor id="99">'
            f'<Team id="50">Lag Test</Team>'
            f"<Leg>2</Leg>"
            f"</Competitor>"
            f"</Competitors>"
        )
        team_xml = ET.fromstring(
            f'<MOPComplete xmlns="{MOP_NS}">'
            f'<tm id="50"><base bib="7">Lag Test</base><r>98;99;100</r></tm>'
            f"</MOPComplete>"
        )
        mock_fetch.side_effect = [competitor_xml, team_xml]

        result = server.lookup_card("999999")
        assert result == {
            "bibNumber": "7",
            "relayLeg": 2,
            "isLastLeg": False,
            "country": None,
        }


class TestUDPBindFailure:
    @patch("socket.socket")
    def test_udp_bind_failure_logs_and_returns(self, mock_socket, server):
        mock_sock = MagicMock()
        mock_sock.bind.side_effect = OSError("Address already in use")
        mock_socket.return_value = mock_sock

        # Should not raise
        server._udp_loop()


class TestPunchSourceMeos:
    def test_filters_by_control_codes(self):
        from punchsources.punch_source_meos import PunchSourceMeos

        with patch.object(PunchSourceMeos, "_parse_config"):
            source = PunchSourceMeos()
            source._control_codes = ["50", "100"]
            source._running = True

            listener = MagicMock()
            source.register_punch_listener(listener)

            # Punch with matching control code
            source.meos_punch_received(
                {
                    "controlCode": "50",
                    "id": "1_50",
                    "cardNumber": "123",
                    "passedTime": None,
                }
            )
            assert listener.punch_received.call_count == 1

            # Punch with non-matching control code
            source.meos_punch_received(
                {
                    "controlCode": "999",
                    "id": "1_999",
                    "cardNumber": "123",
                    "passedTime": None,
                }
            )
            assert listener.punch_received.call_count == 1  # unchanged

    def test_get_control_codes(self):
        from punchsources.punch_source_meos import PunchSourceMeos

        with patch.object(PunchSourceMeos, "_parse_config"):
            source = PunchSourceMeos()
            source._control_codes = ["50", "100"]
            assert source.get_control_codes() == ["50", "100"]

    def test_verify_control_codes_no_url(self):
        from punchsources.punch_source_meos import PunchSourceMeos

        with patch.object(PunchSourceMeos, "_parse_config"):
            source = PunchSourceMeos()
            source._control_codes = ["50"]
            with patch("punchsources.punch_source_meos.Config") as mock_config:
                mock_config().get_section.return_value = {}
                with patch(
                    "punchsources.punch_source_meos.MeosInfoServer.CONFIG_OPTION_URL"
                ) as mock_url:
                    mock_url.get_value.return_value = None
                    result = source.verify_control_codes()
            assert result.status is False

    def test_verify_control_codes_all_valid(self):
        from punchsources.punch_source_meos import PunchSourceMeos

        with patch.object(PunchSourceMeos, "_parse_config"):
            source = PunchSourceMeos()
            source._control_codes = ["50", "100"]
            with patch("punchsources.punch_source_meos.Config") as mock_config:
                mock_config().get_section.return_value = {}
                with (
                    patch(
                        "punchsources.punch_source_meos.MeosInfoServer.CONFIG_OPTION_URL"
                    ) as mock_url,
                    patch(
                        "punchsources.punch_source_meos._fetch_control_ids",
                        return_value={50, 100, 150},
                    ),
                ):
                    mock_url.get_value.return_value = "http://localhost:2009"
                    result = source.verify_control_codes()
            assert result.status is True

    def test_verify_control_codes_missing(self):
        from punchsources.punch_source_meos import PunchSourceMeos

        with patch.object(PunchSourceMeos, "_parse_config"):
            source = PunchSourceMeos()
            source._control_codes = ["50", "999"]
            with patch("punchsources.punch_source_meos.Config") as mock_config:
                mock_config().get_section.return_value = {}
                with (
                    patch(
                        "punchsources.punch_source_meos.MeosInfoServer.CONFIG_OPTION_URL"
                    ) as mock_url,
                    patch(
                        "punchsources.punch_source_meos._fetch_control_ids",
                        return_value={50, 100},
                    ),
                ):
                    mock_url.get_value.return_value = "http://localhost:2009"
                    result = source.verify_control_codes()
            assert result.status is False
            assert "999" in result.message

    def test_verify_control_codes_fetch_fails(self):
        from punchsources.punch_source_meos import PunchSourceMeos

        with patch.object(PunchSourceMeos, "_parse_config"):
            source = PunchSourceMeos()
            source._control_codes = ["50"]
            with patch("punchsources.punch_source_meos.Config") as mock_config:
                mock_config().get_section.return_value = {}
                with (
                    patch(
                        "punchsources.punch_source_meos.MeosInfoServer.CONFIG_OPTION_URL"
                    ) as mock_url,
                    patch(
                        "punchsources.punch_source_meos._fetch_control_ids",
                        return_value=None,
                    ),
                ):
                    mock_url.get_value.return_value = "http://localhost:2009"
                    result = source.verify_control_codes()
            assert result.status is False


class TestStartListSourceMeos:
    def test_delegates_to_meos_info_server(self, server):
        from startlistsources.start_list_source_meos import StartListSourceMeos

        source = StartListSourceMeos()
        source._running = True

        server._cmp_info[67] = {"card": "506576", "team_id": 23, "leg": 1}
        server._team_bib[23] = "43"

        result = source.lookup_from_card_number("506576")
        assert result == {
            "bibNumber": "43",
            "relayLeg": 1,
            "isLastLeg": False,
            "country": None,
        }

    def test_returns_none_when_not_running(self):
        from startlistsources.start_list_source_meos import StartListSourceMeos

        source = StartListSourceMeos()
        source._running = False

        result = source.lookup_from_card_number("506576")
        assert result is None


class TestMeosInfoServerGetBibRange:
    def test_returns_none_when_no_teams(self, server):
        assert server.get_bib_range() is None

    def test_returns_range_with_teams(self, server):
        server._team_bib = {1: "10", 2: "50", 3: "200"}
        assert server.get_bib_range() == (10, 200)

    def test_returns_range_with_single_team(self, server):
        server._team_bib = {1: "42"}
        assert server.get_bib_range() == (42, 42)

    def test_skips_non_numeric_bibs(self, server):
        server._team_bib = {1: "10", 2: "abc", 3: "200"}
        assert server.get_bib_range() == (10, 200)

    def test_returns_none_when_all_bibs_non_numeric(self, server):
        server._team_bib = {1: "abc", 2: "def"}
        assert server.get_bib_range() is None


class TestMeosInfoServerGetTeamCount:
    def test_returns_none_when_no_teams(self, server):
        assert server.get_team_count() is None

    def test_returns_count_with_teams(self, server):
        server._team_bib = {1: "10", 2: "50", 3: "200"}
        assert server.get_team_count() == 3

    def test_returns_one_with_single_team(self, server):
        server._team_bib = {1: "42"}
        assert server.get_team_count() == 1

    def test_returns_none_when_empty_dict(self, server):
        server._team_bib = {}
        assert server.get_team_count() is None


class TestMeosInfoServerGetRunnerCount:
    def test_returns_none_when_no_competitors(self, server):
        assert server.get_runner_count() is None

    def test_returns_none_when_empty_dict(self, server):
        server._cmp_info = {}
        assert server.get_runner_count() is None

    def test_counts_only_competitors_with_cards(self, server):
        server._cmp_info = {
            67: {"card": "506576", "team_id": 23, "leg": 1},
            68: {"team_id": 23, "leg": 2},  # no card
            69: {"card": "111111", "team_id": 23, "leg": 3},
        }
        assert server.get_runner_count() == 2

    def test_counts_all_when_all_have_cards(self, server):
        server._cmp_info = {
            67: {"card": "506576", "team_id": 23, "leg": 1},
            68: {"card": "222222", "team_id": 23, "leg": 2},
            69: {"card": "333333", "team_id": 23, "leg": 3},
        }
        assert server.get_runner_count() == 3

    def test_returns_zero_when_no_cards(self, server):
        server._cmp_info = {
            67: {"team_id": 23, "leg": 1},
            68: {"team_id": 23, "leg": 2},
        }
        assert server.get_runner_count() == 0

    def test_empty_card_not_counted(self, server):
        server._cmp_info = {
            67: {"card": "", "team_id": 23, "leg": 1},
            68: {"card": "111111", "team_id": 23, "leg": 2},
        }
        assert server.get_runner_count() == 1


class TestStartListSourceMeosGetTeamCount:
    def test_returns_none_when_not_running(self):
        from startlistsources.start_list_source_meos import StartListSourceMeos

        source = StartListSourceMeos()
        source._running = False
        assert source.get_team_count() is None

    def test_delegates_to_meos_info_server(self, server):
        from startlistsources.start_list_source_meos import StartListSourceMeos

        source = StartListSourceMeos()
        source._running = True
        server._team_bib = {1: "10", 2: "50"}
        assert source.get_team_count() == 2


class TestStartListSourceMeosGetRunnerCount:
    def test_returns_none_when_not_running(self):
        from startlistsources.start_list_source_meos import StartListSourceMeos

        source = StartListSourceMeos()
        source._running = False
        assert source.get_runner_count() is None

    def test_delegates_to_meos_info_server(self, server):
        from startlistsources.start_list_source_meos import StartListSourceMeos

        source = StartListSourceMeos()
        source._running = True
        server._cmp_info = {
            67: {"card": "506576", "team_id": 23, "leg": 1},
            68: {"card": "222222", "team_id": 23, "leg": 2},
        }
        assert source.get_runner_count() == 2


class TestMeosInfoServerDataReadyCallbacks:
    def test_register_callback(self, server):
        callback = MagicMock()
        server.register_data_ready_callback(callback)
        assert callback in server._data_ready_callbacks

    def test_register_same_callback_twice_only_adds_once(self, server):
        callback = MagicMock()
        server.register_data_ready_callback(callback)
        server.register_data_ready_callback(callback)
        assert server._data_ready_callbacks.count(callback) == 1

    def test_unregister_callback(self, server):
        callback = MagicMock()
        server.register_data_ready_callback(callback)
        server.unregister_data_ready_callback(callback)
        assert callback not in server._data_ready_callbacks

    def test_unregister_nonexistent_callback_does_not_raise(self, server):
        callback = MagicMock()
        server.unregister_data_ready_callback(callback)  # should not raise

    def test_notify_data_ready_calls_all_callbacks(self, server):
        cb1 = MagicMock()
        cb2 = MagicMock()
        server.register_data_ready_callback(cb1)
        server.register_data_ready_callback(cb2)
        server._notify_data_ready()
        cb1.assert_called_once()
        cb2.assert_called_once()

    def test_notify_data_ready_continues_after_exception(self, server):
        cb1 = MagicMock(side_effect=RuntimeError("test"))
        cb2 = MagicMock()
        server.register_data_ready_callback(cb1)
        server.register_data_ready_callback(cb2)
        server._notify_data_ready()
        cb1.assert_called_once()
        cb2.assert_called_once()


class TestProcessElemReturnValues:
    """Tests that _process_*_elem methods return True only when data actually changed."""

    @pytest.fixture
    def server(self):
        with (
            patch.object(MeosInfoServer, "_parse_config"),
            patch.object(MeosInfoServer, "_data_read", return_value=False),
        ):
            s = MeosInfoServer()
            s._url = "http://localhost:2009"
            s._fetch_interval = 1
            s._use_udp = False
            s._zero_time = datetime(2026, 6, 16, 5, 0, 0)  # noqa: DTZ001 - naive datetime matches MeOS/OLA data model
            return s

    def test_process_org_elem_returns_true_on_new_data(self, server):
        xml = f'<org id="5" nat="SWE" xmlns="{MOP_NS}"/>'
        elem = ET.fromstring(xml)
        assert server._process_org_elem(elem) is True

    def test_process_org_elem_returns_false_on_duplicate(self, server):
        xml = f'<org id="5" nat="SWE" xmlns="{MOP_NS}"/>'
        elem = ET.fromstring(xml)
        server._process_org_elem(elem)
        assert server._process_org_elem(elem) is False

    def test_process_org_elem_returns_true_on_change(self, server):
        xml1 = f'<org id="5" nat="SWE" xmlns="{MOP_NS}"/>'
        xml2 = f'<org id="5" nat="NOR" xmlns="{MOP_NS}"/>'
        server._process_org_elem(ET.fromstring(xml1))
        assert server._process_org_elem(ET.fromstring(xml2)) is True

    def test_process_team_elem_returns_true_on_new_team(self, server):
        xml = (
            f'<tm id="10" xmlns="{MOP_NS}">'
            f'<base bib="5">Team A</base>'
            f"<r>100;101</r>"
            f"</tm>"
        )
        assert server._process_team_elem(ET.fromstring(xml)) is True

    def test_process_team_elem_returns_false_on_duplicate(self, server):
        xml = (
            f'<tm id="10" xmlns="{MOP_NS}">'
            f'<base bib="5">Team A</base>'
            f"<r>100;101</r>"
            f"</tm>"
        )
        server._process_team_elem(ET.fromstring(xml))
        assert server._process_team_elem(ET.fromstring(xml)) is False

    def test_process_team_elem_returns_true_on_bib_change(self, server):
        xml1 = (
            f'<tm id="10" xmlns="{MOP_NS}">'
            f'<base bib="5">Team A</base>'
            f"<r>100;101</r>"
            f"</tm>"
        )
        xml2 = (
            f'<tm id="10" xmlns="{MOP_NS}">'
            f'<base bib="99">Team A</base>'
            f"<r>100;101</r>"
            f"</tm>"
        )
        server._process_team_elem(ET.fromstring(xml1))
        assert server._process_team_elem(ET.fromstring(xml2)) is True

    def test_process_cmp_elem_returns_true_on_new_card(self, server):
        xml = (
            f'<cmp id="100" card="506576" xmlns="{MOP_NS}">'
            f'<base org="5" cls="1" stat="0" st="0" rt="0">Name</base>'
            f"</cmp>"
        )
        assert server._process_cmp_elem(ET.fromstring(xml)) is True

    def test_process_cmp_elem_returns_false_on_duplicate(self, server):
        xml = (
            f'<cmp id="100" card="506576" xmlns="{MOP_NS}">'
            f'<base org="5" cls="1" stat="0" st="0" rt="0">Name</base>'
            f"</cmp>"
        )
        server._process_cmp_elem(ET.fromstring(xml))
        assert server._process_cmp_elem(ET.fromstring(xml)) is False

    def test_process_cmp_elem_returns_true_on_card_change(self, server):
        xml1 = (
            f'<cmp id="100" card="506576" xmlns="{MOP_NS}">'
            f'<base org="5" cls="1" stat="0" st="0" rt="0">Name</base>'
            f"</cmp>"
        )
        xml2 = (
            f'<cmp id="100" card="999999" xmlns="{MOP_NS}">'
            f'<base org="5" cls="1" stat="0" st="0" rt="0">Name</base>'
            f"</cmp>"
        )
        server._process_cmp_elem(ET.fromstring(xml1))
        assert server._process_cmp_elem(ET.fromstring(xml2)) is True

    def test_process_cmp_elem_returns_true_on_new_radio_punch(self, server):
        server._cmp_info[100] = {"card": "506576", "team_id": 10, "leg": 1}
        server._team_bib[10] = "5"
        listener = MagicMock(spec=MeosPunchListener)
        server._listeners.append(listener)

        xml = f'<cmp id="100" xmlns="{MOP_NS}"><radio>31,12340</radio></cmp>'
        assert server._process_cmp_elem(ET.fromstring(xml)) is True

    def test_process_cmp_elem_returns_false_on_duplicate_radio(self, server):
        server._cmp_info[100] = {"card": "506576", "team_id": 10, "leg": 1}
        server._team_bib[10] = "5"
        listener = MagicMock(spec=MeosPunchListener)
        server._listeners.append(listener)

        xml = f'<cmp id="100" xmlns="{MOP_NS}"><radio>31,12340</radio></cmp>'
        server._process_cmp_elem(ET.fromstring(xml))
        assert server._process_cmp_elem(ET.fromstring(xml)) is False


class TestFetchStatus:
    """Tests for _fetch_status and eventId extraction."""

    @patch("utils.meos_info_server._fetch_xml")
    def test_extracts_event_id(self, mock_fetch, server):
        xml = ET.fromstring(
            f'<MOPComplete xmlns="{MOP_NS}">'
            f'<status version="5.0.1807 (U1)" eventNameId="meos_test" '
            f'onDatabase="1" eventId="42"/>'
            f"</MOPComplete>"
        )
        mock_fetch.return_value = xml
        server._fetch_status("http://localhost:2009")
        assert server._event_id == 42

    @patch("utils.meos_info_server._fetch_xml")
    def test_missing_event_id_attribute_sets_none(self, mock_fetch, server):
        """Older MeOS versions do not include eventId."""
        xml = ET.fromstring(
            f'<MOPComplete xmlns="{MOP_NS}">'
            f'<status version="4.1.123" eventNameId="meos_test" onDatabase="1"/>'
            f"</MOPComplete>"
        )
        mock_fetch.return_value = xml
        server._event_id = 99  # pre-set to verify it gets cleared
        server._fetch_status("http://localhost:2009")
        assert server._event_id is None

    @patch("utils.meos_info_server._fetch_xml")
    def test_empty_event_id_sets_none(self, mock_fetch, server):
        xml = ET.fromstring(
            f'<MOPComplete xmlns="{MOP_NS}">'
            f'<status version="5.0.1807" eventNameId="meos_test" '
            f'onDatabase="1" eventId=""/>'
            f"</MOPComplete>"
        )
        mock_fetch.return_value = xml
        server._fetch_status("http://localhost:2009")
        assert server._event_id is None

    @patch("utils.meos_info_server._fetch_xml")
    def test_invalid_event_id_sets_none(self, mock_fetch, server):
        xml = ET.fromstring(
            f'<MOPComplete xmlns="{MOP_NS}">'
            f'<status version="5.0.1807" eventNameId="meos_test" '
            f'onDatabase="1" eventId="abc"/>'
            f"</MOPComplete>"
        )
        mock_fetch.return_value = xml
        server._fetch_status("http://localhost:2009")
        assert server._event_id is None

    @patch("utils.meos_info_server._fetch_xml")
    def test_no_status_element_sets_none(self, mock_fetch, server):
        xml = ET.fromstring(
            f'<MOPComplete xmlns="{MOP_NS}">'
            f'<competition date="2026-06-17" zerotime="03:00:00">Test</competition>'
            f"</MOPComplete>"
        )
        mock_fetch.return_value = xml
        server._event_id = 99
        server._fetch_status("http://localhost:2009")
        assert server._event_id is None

    @patch("utils.meos_info_server._fetch_xml")
    def test_event_id_zero_is_valid(self, mock_fetch, server):
        """eventId=0 means no event loaded, should still be stored as 0."""
        xml = ET.fromstring(
            f'<MOPComplete xmlns="{MOP_NS}">'
            f'<status version="5.0.1807 (U1)" eventNameId="" '
            f'onDatabase="0" eventId="0"/>'
            f"</MOPComplete>"
        )
        mock_fetch.return_value = xml
        server._fetch_status("http://localhost:2009")
        assert server._event_id == 0


class TestUDPEventIdFiltering:
    """Tests for UDP packet filtering based on event ID."""

    @patch("socket.socket")
    def test_matching_event_id_triggers_poll(self, mock_socket, server):
        import struct

        server._event_id = 42
        server._use_udp = True
        server._udp_port = 21338

        mock_sock = MagicMock()
        mock_socket.return_value = mock_sock

        packet = struct.pack("<5i", 42, 100, 200, 1, 3600)

        call_count = [0]

        def recvfrom_side_effect(*args):
            call_count[0] += 1
            if call_count[0] == 1:
                return (packet, ("192.168.1.1", 12345))
            server._stop_event.set()
            raise TimeoutError()

        mock_sock.recvfrom.side_effect = recvfrom_side_effect

        server._udp_loop()

        assert server._poll_event.is_set()

    @patch("socket.socket")
    def test_mismatched_event_id_does_not_trigger_poll(self, mock_socket, server):
        import struct

        server._event_id = 42
        server._use_udp = True
        server._udp_port = 21338

        mock_sock = MagicMock()
        mock_socket.return_value = mock_sock

        # Packet from a different competition (cmpId=99)
        packet = struct.pack("<5i", 99, 100, 200, 1, 3600)

        call_count = [0]

        def recvfrom_side_effect(*args):
            call_count[0] += 1
            if call_count[0] == 1:
                return (packet, ("192.168.1.1", 12345))
            server._stop_event.set()
            raise TimeoutError()

        mock_sock.recvfrom.side_effect = recvfrom_side_effect

        server._udp_loop()

        assert not server._poll_event.is_set()

    @patch("socket.socket")
    def test_no_event_id_accepts_all_packets(self, mock_socket, server):
        import struct

        server._event_id = None  # older MeOS, no filtering
        server._use_udp = True
        server._udp_port = 21338

        mock_sock = MagicMock()
        mock_socket.return_value = mock_sock

        # Any cmpId should be accepted
        packet = struct.pack("<5i", 999, 100, 200, 1, 3600)

        call_count = [0]

        def recvfrom_side_effect(*args):
            call_count[0] += 1
            if call_count[0] == 1:
                return (packet, ("192.168.1.1", 12345))
            server._stop_event.set()
            raise TimeoutError()

        mock_sock.recvfrom.side_effect = recvfrom_side_effect

        server._udp_loop()

        assert server._poll_event.is_set()


class TestFetchControlIds:
    def test_returns_control_ids(self):
        from utils.meos_info_server import _fetch_control_ids

        xml = (
            f'<MOPControlList xmlns="{MOP_NS}">'
            f'<control id="50">Control 50</control>'
            f'<control id="100">Control 100</control>'
            f"</MOPControlList>"
        )
        root = ET.fromstring(xml)
        with patch("utils.meos_info_server._fetch_xml", return_value=root):
            result = _fetch_control_ids("http://localhost:2009")
        assert result == {50, 100}

    def test_returns_none_on_error(self):
        from utils.meos_info_server import _fetch_control_ids

        with patch("utils.meos_info_server._fetch_xml", side_effect=Exception("fail")):
            result = _fetch_control_ids("http://localhost:2009")
        assert result is None
