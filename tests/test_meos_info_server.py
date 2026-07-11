# -*- coding: utf-8 -*-

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
    with patch.object(MeosInfoServer, "_parse_config"):
        with patch.object(MeosInfoServer, "_data_read", return_value=False):
            s = MeosInfoServer()
            s._url = "http://localhost:2009"
            s._fetch_interval = 1
            s._use_udp = False
            s._zero_time = datetime(2026, 6, 16, 5, 0, 0)
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
        assert punch1["passedTime"] == datetime(2026, 6, 16, 5, 0, 0) + timedelta(
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
        assert punch["passedTime"] == datetime(2026, 6, 16, 6, 0, 0)

    def test_running_time_includes_start_time_offset(self, server):
        # st=18000 tenths = 1800s = 00:30:00 from midnight
        server._competition_date = datetime(2026, 6, 16)
        server._cmp_info[1] = {"card": "12345", "st": 18000}

        listener = MagicMock(spec=MeosPunchListener)
        server._listeners.append(listener)

        xml = f'<cmp id="1" card="12345" xmlns="{MOP_NS}"><radio>50,36000</radio></cmp>'
        elem = ET.fromstring(xml)
        server._process_cmp_elem(elem)

        punch = listener.meos_punch_received.call_args[0][0]
        # midnight + (18000 + 36000) / 10 = 00:00:00 + 5400s = 01:30:00
        assert punch["passedTime"] == datetime(2026, 6, 16, 1, 30, 0)


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
