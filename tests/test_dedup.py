from datetime import datetime
from time import time
from unittest.mock import MagicMock, patch

import pytest

from prewarning import PreWarning
from startlistsources.start_list_source_ola_mysql import StartListSourceOlaMySql


def _make_pw(**kwargs):
    pw = MagicMock()
    pw.logger = MagicMock()
    pw._dedup_lock = MagicMock()
    pw._dedup_card_control = {}
    pw._dedup_bib_leg = {}
    pw._dedup_card_control_enabled = True
    pw._dedup_bib_leg_enabled = True
    pw._dedup_timeout = 0
    pw.start_list_source = MagicMock()
    pw.start_list_source_name = "MockStartList"
    pw._to_str = staticmethod(PreWarning._to_str)
    pw._is_deduped = lambda cache, key, current_passed_time: PreWarning._is_deduped(
        pw, cache, key, current_passed_time
    )
    pw._parse_passed_time = lambda passed_time: PreWarning._parse_passed_time(
        passed_time
    )
    pw.sound = MagicMock()
    pw.announcement_queue = MagicMock()
    for k, v in kwargs.items():
        setattr(pw, k, v)
    return pw


class TestIsDeduped:
    def test_key_not_present(self):
        pw = MagicMock()
        pw._dedup_timeout = 0
        cache: dict = {}
        assert PreWarning._is_deduped(pw, cache, ("card1", "31"), 1000.0) is False

    def test_key_present_timeout_zero(self):
        pw = MagicMock()
        pw._dedup_timeout = 0
        cache: dict = {("card1", "31"): 500.0}
        assert PreWarning._is_deduped(pw, cache, ("card1", "31"), 1000.0) is True

    def test_key_present_not_expired(self):
        pw = MagicMock()
        pw._dedup_timeout = 60
        cache: dict = {("card1", "31"): 1000.0}
        assert PreWarning._is_deduped(pw, cache, ("card1", "31"), 1050.0) is True

    def test_key_expired_and_removed(self):
        pw = MagicMock()
        pw._dedup_timeout = 30
        cache: dict = {("card1", "31"): 1000.0}
        assert PreWarning._is_deduped(pw, cache, ("card1", "31"), 1100.0) is False
        assert ("card1", "31") not in cache

    def test_different_key_not_affected(self):
        pw = MagicMock()
        pw._dedup_timeout = 0
        cache: dict = {("card1", "31"): 500.0}
        assert PreWarning._is_deduped(pw, cache, ("card2", "32"), 1000.0) is False
        assert ("card1", "31") in cache


class TestParsePassedTime:
    def test_datetime_object(self):
        dt = datetime(2026, 6, 14, 12, 0, 0)  # noqa: DTZ001 - naive datetime matches MeOS/OLA data model
        result = PreWarning._parse_passed_time(dt)
        assert isinstance(result, float)
        assert result == dt.timestamp()

    def test_none_falls_back_to_time(self):
        before = time()
        result = PreWarning._parse_passed_time(None)
        after = time()
        assert before <= result <= after


class TestProcessPunchesDedup:
    def test_card_control_dedup_skips_before_lookup(self):
        pw = _make_pw()
        pw._dedup_card_control = {("card1", "31"): time()}

        punch = {
            "cardNumber": "card1",
            "controlCode": "31",
            "passedTime": datetime(2026, 6, 14, 12, 0, 0),  # noqa: DTZ001 - naive datetime matches MeOS/OLA data model
        }
        pw.punch_queue = MagicMock()
        pw.punch_queue.get.side_effect = [punch, StopIteration]

        with patch("prewarning.wx.CallAfter"), pytest.raises(StopIteration):
            PreWarning._process_punches(pw)

        pw.start_list_source.lookup_from_card_number.assert_not_called()
        pw.announcement_queue.put.assert_not_called()

    def test_card_control_dedup_disabled_allows(self):
        pw = _make_pw(_dedup_card_control_enabled=False)
        pw._dedup_card_control = {("card1", "31"): time()}

        punch = {
            "cardNumber": "card1",
            "controlCode": "31",
            "passedTime": datetime(2026, 6, 14, 12, 0, 0),  # noqa: DTZ001 - naive datetime matches MeOS/OLA data model
            "bibNumber": 101,
            "relayLeg": 1,
            "country": "SWE",
        }
        pw.punch_queue = MagicMock()
        pw.punch_queue.get.side_effect = [punch, StopIteration]

        with patch("prewarning.wx.CallAfter"), pytest.raises(StopIteration):
            PreWarning._process_punches(pw)

        pw.announcement_queue.put.assert_called_once()

    def test_different_control_not_affected(self):
        pw = _make_pw()
        pw._dedup_card_control = {("card1", "31"): time()}

        punch = {
            "cardNumber": "card1",
            "controlCode": "32",
            "passedTime": datetime(2026, 6, 14, 12, 0, 0),  # noqa: DTZ001 - naive datetime matches MeOS/OLA data model
            "bibNumber": 101,
            "relayLeg": 1,
            "country": "SWE",
        }
        pw.punch_queue = MagicMock()
        pw.punch_queue.get.side_effect = [punch, StopIteration]

        with patch("prewarning.wx.CallAfter"), pytest.raises(StopIteration):
            PreWarning._process_punches(pw)

        pw.announcement_queue.put.assert_called_once()

    def test_bib_leg_dedup_skips_after_lookup(self):
        pw = _make_pw()

        punch = {
            "cardNumber": "card1",
            "controlCode": "31",
            "passedTime": datetime(2026, 6, 14, 12, 0, 0),  # noqa: DTZ001 - naive datetime matches MeOS/OLA data model
        }
        pw.start_list_source.lookup_from_card_number.return_value = {
            "bibNumber": 101,
            "relayLeg": 1,
            "isLastLeg": False,
            "country": "SWE",
        }
        pw._dedup_bib_leg = {("101", "1"): time()}

        pw.punch_queue = MagicMock()
        pw.punch_queue.get.side_effect = [punch, StopIteration]

        with patch("prewarning.wx.CallAfter"), pytest.raises(StopIteration):
            PreWarning._process_punches(pw)

        pw.start_list_source.lookup_from_card_number.assert_called_once_with("card1")
        pw.announcement_queue.put.assert_not_called()

    def test_bib_leg_dedup_disabled_allows(self):
        pw = _make_pw(_dedup_bib_leg_enabled=False)

        punch = {
            "cardNumber": "card1",
            "controlCode": "31",
            "passedTime": datetime(2026, 6, 14, 12, 0, 0),  # noqa: DTZ001 - naive datetime matches MeOS/OLA data model
        }
        pw.start_list_source.lookup_from_card_number.return_value = {
            "bibNumber": 101,
            "relayLeg": 1,
            "isLastLeg": False,
            "country": "SWE",
        }
        pw._dedup_bib_leg = {("101", "1"): time()}

        pw.punch_queue = MagicMock()
        pw.punch_queue.get.side_effect = [punch, StopIteration]

        with patch("prewarning.wx.CallAfter"), pytest.raises(StopIteration):
            PreWarning._process_punches(pw)

        pw.announcement_queue.put.assert_called_once()

    def test_different_leg_not_affected(self):
        pw = _make_pw()

        punch = {
            "cardNumber": "card1",
            "controlCode": "31",
            "passedTime": datetime(2026, 6, 14, 12, 0, 0),  # noqa: DTZ001 - naive datetime matches MeOS/OLA data model
        }
        pw.start_list_source.lookup_from_card_number.return_value = {
            "bibNumber": 101,
            "relayLeg": 2,
            "isLastLeg": True,
            "country": "SWE",
        }
        pw._dedup_bib_leg = {("101", "1"): time()}

        pw.punch_queue = MagicMock()
        pw.punch_queue.get.side_effect = [punch, StopIteration]

        with patch("prewarning.wx.CallAfter"), pytest.raises(StopIteration):
            PreWarning._process_punches(pw)

        pw.announcement_queue.put.assert_called_once()

    def test_records_keys_after_announce(self):
        pw = _make_pw()

        punch = {
            "cardNumber": "card1",
            "controlCode": "31",
            "passedTime": datetime(2026, 6, 14, 12, 0, 0),  # noqa: DTZ001 - naive datetime matches MeOS/OLA data model
            "bibNumber": 101,
            "relayLeg": 1,
            "country": "SWE",
        }
        pw.punch_queue = MagicMock()
        pw.punch_queue.get.side_effect = [punch, StopIteration]

        with patch("prewarning.wx.CallAfter"), pytest.raises(StopIteration):
            PreWarning._process_punches(pw)

        assert ("card1", "31") in pw._dedup_card_control
        assert ("101", "1") in pw._dedup_bib_leg

    def test_both_filters_active(self):
        pw = _make_pw()

        punch_skip_card = {
            "cardNumber": "card1",
            "controlCode": "31",
            "passedTime": datetime(2026, 6, 14, 12, 0, 0),  # noqa: DTZ001 - naive datetime matches MeOS/OLA data model
        }

        punch_skip_bib = {
            "cardNumber": "card2",
            "controlCode": "32",
            "passedTime": datetime(2026, 6, 14, 12, 1, 0),  # noqa: DTZ001 - naive datetime matches MeOS/OLA data model
        }

        punch_allowed = {
            "cardNumber": "card3",
            "controlCode": "33",
            "passedTime": datetime(2026, 6, 14, 12, 2, 0),  # noqa: DTZ001 - naive datetime matches MeOS/OLA data model
            "bibNumber": 103,
            "relayLeg": 1,
            "country": "SWE",
        }

        pw._dedup_card_control = {("card1", "31"): time()}
        pw.start_list_source.lookup_from_card_number.side_effect = [
            {"bibNumber": 102, "relayLeg": 1, "isLastLeg": False, "country": "SWE"},
            {"bibNumber": 103, "relayLeg": 1, "isLastLeg": False, "country": "SWE"},
        ]
        pw._dedup_bib_leg = {("102", "1"): time()}

        pw.punch_queue = MagicMock()
        pw.punch_queue.get.side_effect = [
            punch_skip_card,
            punch_skip_bib,
            punch_allowed,
            StopIteration,
        ]

        with patch("prewarning.wx.CallAfter"), pytest.raises(StopIteration):
            PreWarning._process_punches(pw)

        pw.announcement_queue.put.assert_called_once()
        call_args = pw.announcement_queue.put.call_args[0][0]
        assert call_args["sound"] == "103"

    def test_card_control_skip_with_ola_mysql_source(self):
        pw = _make_pw(start_list_source_name=StartListSourceOlaMySql.__qualname__)
        pw._dedup_card_control = {("card1", "31"): time()}

        punch = {
            "cardNumber": "card1",
            "controlCode": "31",
            "passedTime": datetime(2026, 6, 14, 12, 0, 0),  # noqa: DTZ001 - naive datetime matches MeOS/OLA data model
            "bibNumber": 101,
            "relayLeg": 1,
        }
        pw.punch_queue = MagicMock()
        pw.punch_queue.get.side_effect = [punch, StopIteration]

        with patch("prewarning.wx.CallAfter"), pytest.raises(StopIteration):
            PreWarning._process_punches(pw)

        pw.start_list_source.lookup_from_card_number.assert_not_called()
        pw.announcement_queue.put.assert_not_called()
