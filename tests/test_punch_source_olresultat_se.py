from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from punchsources.punch_source_olresultat_se import (
    PunchSourceOlresultatSe,
    _fetch_punches,
    _verify_control_codes,
    _verify_date_time,
    _verify_last_id,
)

MODULE = "punchsources.punch_source_olresultat_se"


def _mock_response(data: str, charset: str = "utf-8"):
    resp = MagicMock()
    resp.info.return_value.get_content_charset.return_value = charset
    resp.read.return_value = data.encode(charset)
    return resp


class TestFetchPunches:
    def test_raises_on_empty_url(self):
        with pytest.raises(ValueError, match="URL must be configured"):
            _fetch_punches("", "unit1", 0)

    def test_raises_on_empty_unit_id(self):
        with pytest.raises(ValueError, match="Device Id"):
            _fetch_punches("http://example.com", "", 0)

    def test_fetches_and_parses_csv(self):
        csv_data = "1;101;1001;12:30:00\n2;102;1002;12:31:00\n"
        resp = _mock_response(csv_data)

        with patch(f"{MODULE}.urlopen", return_value=resp):
            punches = _fetch_punches("http://example.com/punches", "unit1", 0)

        assert len(punches) == 2
        assert punches[0]["controlCode"] == "101"
        assert punches[0]["cardNumber"] == "1001"
        assert punches[1]["controlCode"] == "102"

    def test_applies_control_code_filter(self):
        csv_data = "1;101;1001;12:30:00\n2;102;1002;12:31:00\n3;103;1003;12:32:00\n"
        resp = _mock_response(csv_data)

        with patch(f"{MODULE}.urlopen", return_value=resp):
            punches = _fetch_punches(
                "http://example.com", "u1", 0, control_codes=["101", "103"]
            )

        assert len(punches) == 2
        assert punches[0]["controlCode"] == "101"
        assert punches[1]["controlCode"] == "103"

    def test_returns_empty_when_no_punches(self):
        resp = _mock_response("")

        with patch(f"{MODULE}.urlopen", return_value=resp):
            punches = _fetch_punches("http://example.com", "u1", 0)

        assert punches == []

    def test_includes_query_parameters(self):
        resp = _mock_response("")
        with patch(f"{MODULE}.urlopen", return_value=resp) as mock_urlopen:
            _fetch_punches(
                "http://example.com",
                "unit42",
                99,
                from_date="2024-01-15",
                from_time="10:00:00",
            )

        url_str = mock_urlopen.call_args[0][0].full_url
        assert "unitId=unit42" in url_str
        assert "lastId=99" in url_str
        assert "date=2024-01-15" in url_str
        assert "time=10%3A00%3A00" in url_str

    def test_raises_http_error(self):
        resp = MagicMock()
        resp.info.return_value.get_content_charset.return_value = "utf-8"
        resp.read.side_effect = HTTPError(
            "http://example.com", 404, "Not Found", {}, None
        )

        with patch(f"{MODULE}.urlopen", return_value=resp), pytest.raises(HTTPError):
            _fetch_punches("http://example.com", "u1", 0)

    def test_raises_url_error(self):
        resp = MagicMock()
        resp.info.return_value.get_content_charset.return_value = "utf-8"
        resp.read.side_effect = URLError("connection failed")

        with patch(f"{MODULE}.urlopen", return_value=resp), pytest.raises(URLError):
            _fetch_punches("http://example.com", "u1", 0)

    def test_uses_default_encoding_when_missing(self):
        csv_data = "1;101;1001;12:00:00"
        resp = MagicMock()
        resp.info.return_value.get_content_charset.return_value = None
        resp.read.return_value = csv_data.encode("utf-8")

        with patch(f"{MODULE}.urlopen", return_value=resp):
            punches = _fetch_punches("http://example.com", "u1", 0)

        assert len(punches) == 1

    def test_no_filter_when_control_codes_is_none(self):
        csv_data = "1;101;1001;12:00:00\n2;102;1002;12:01:00\n"
        resp = _mock_response(csv_data)

        with patch(f"{MODULE}.urlopen", return_value=resp):
            punches = _fetch_punches("http://example.com", "u1", 0, control_codes=None)

        assert len(punches) == 2

    def test_raises_on_unknown_exception(self):
        resp = MagicMock()
        resp.info.return_value.get_content_charset.return_value = "utf-8"
        resp.read.side_effect = Exception("something went wrong")

        with (
            patch(f"{MODULE}.urlopen", return_value=resp),
            pytest.raises(Exception, match="something went wrong"),
        ):
            _fetch_punches("http://example.com", "u1", 0)


class TestVerifyLastId:
    def test_success_with_punches(self):
        with patch(
            "punchsources.punch_source_olresultat_se._fetch_punches",
            return_value=[{"id": "1"}],
        ):
            result = _verify_last_id("http://ex.com", "u1", 0)
            assert result.status is True
            assert "1 Punches" in result.message

    def test_success_no_punches(self):
        with patch(
            "punchsources.punch_source_olresultat_se._fetch_punches", return_value=[]
        ):
            result = _verify_last_id("http://ex.com", "u1", 0)
            assert result.status is True
            assert "No Punches" in result.message

    def test_catches_exception(self):
        with patch(
            "punchsources.punch_source_olresultat_se._fetch_punches",
            side_effect=ValueError("bad"),
        ):
            result = _verify_last_id("http://ex.com", "u1", 0)
            assert result.status is False
            assert "bad" in result.message


class TestVerifyDateTime:
    def test_success_with_punches(self):
        with patch(
            "punchsources.punch_source_olresultat_se._fetch_punches",
            return_value=[{"id": "1"}],
        ):
            result = _verify_date_time(
                "http://ex.com", "u1", 0, "2024-01-01", "10:00:00"
            )
            assert result.status is True
            assert "1 Punches" in result.message

    def test_success_no_punches(self):
        with patch(
            "punchsources.punch_source_olresultat_se._fetch_punches", return_value=[]
        ):
            result = _verify_date_time(
                "http://ex.com", "u1", 0, "2024-01-01", "10:00:00"
            )
            assert result.status is True
            assert "No Punches" in result.message

    def test_catches_exception(self):
        with patch(
            "punchsources.punch_source_olresultat_se._fetch_punches",
            side_effect=ValueError("bad"),
        ):
            result = _verify_date_time(
                "http://ex.com", "u1", 0, "2024-01-01", "10:00:00"
            )
            assert result.status is False
            assert "bad" in result.message


class TestVerifyControlCodes:
    def test_success_with_punches(self):
        with patch(
            "punchsources.punch_source_olresultat_se._fetch_punches",
            return_value=[{"id": "1"}],
        ):
            result = _verify_control_codes(
                "http://ex.com", "u1", 0, "2024-01-01", "10:00:00", ["101"]
            )
            assert result.status is True
            assert "1 Punches" in result.message

    def test_error_when_control_codes_none(self):
        result = _verify_control_codes(
            "http://ex.com", "u1", 0, "2024-01-01", "10:00:00", None
        )
        assert result.status is False
        assert "must be configured" in result.message

    def test_success_no_punches(self):
        with patch(
            "punchsources.punch_source_olresultat_se._fetch_punches", return_value=[]
        ):
            result = _verify_control_codes(
                "http://ex.com", "u1", 0, "2024-01-01", "10:00:00", ["101"]
            )
            assert result.status is True
            assert "No Punches" in result.message

    def test_catches_exception(self):
        with patch(
            "punchsources.punch_source_olresultat_se._fetch_punches",
            side_effect=ValueError("bad"),
        ):
            result = _verify_control_codes(
                "http://ex.com", "u1", 0, "2024-01-01", "10:00:00", ["101"]
            )
            assert result.status is False
            assert "bad" in result.message


class TestPunchSourceOlresultatSe:
    def test_fetch_punches_logs_unexpected_exception(self):
        with (
            patch("punchsources.punch_source_olresultat_se.Config"),
            patch(
                "punchsources.punch_source_olresultat_se.urlopen",
                side_effect=KeyError("test_key"),
            ),
        ):
            source = PunchSourceOlresultatSe()
            source.url = "http://example.com"
            source.competition_id = "u1"
            source.control_codes = ["101"]
            source.last_received_punch_id = 0
            source.fetch_interval_seconds = 0
            mock_stop = MagicMock()
            mock_stop.is_set.side_effect = [False, True]
            source._stop_event = mock_stop
            with (
                patch.object(source, "_save_state"),
                patch.object(source.logger, "error") as mock_log,
            ):
                source._fetch_punches()
                assert any(
                    "Unexpected error fetching punches" in str(c)
                    for c in mock_log.call_args_list
                ), f"Expected log not found. Calls: {mock_log.call_args_list}"

    def test_get_control_codes(self):
        with patch("punchsources.punch_source_olresultat_se.Config"):
            source = PunchSourceOlresultatSe()
            source.control_codes = ["101", "102"]
            assert source.get_control_codes() == ["101", "102"]

    def test_verify_control_codes_returns_none(self):
        with patch("punchsources.punch_source_olresultat_se.Config"):
            source = PunchSourceOlresultatSe()
            # OLResultat.se has no control-list API, so verification is skipped.
            assert source.verify_control_codes() is None
