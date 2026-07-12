from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest
import wx

from startlistsources.start_list_source_file import (
    DEFAULT_START_LIST_FILE_FOLDER,
    _read_start_list,
    _select_start_list_file,
    _verify_start_list_file,
)


class TestSelectStartListFile:
    def test_returns_selection_when_file_selected(self, wx_app):
        with patch(
            "startlistsources.start_list_source_file.select_file",
            return_value="/some/path/file.xml",
        ) as mock_select:
            parent = wx.Frame(None)
            result = _select_start_list_file(parent)

            assert result is not False
            assert result.values[0].value == "/some/path/file.xml"
            mock_select.assert_called_once()

    def test_returns_false_when_cancelled(self, wx_app):
        with patch(
            "startlistsources.start_list_source_file.select_file", return_value=None
        ):
            result = _select_start_list_file(wx.Frame(None))
            assert result is False

    def test_uses_relative_path_when_in_default_dir(self, wx_app):
        default = DEFAULT_START_LIST_FILE_FOLDER.as_posix()
        file_in_default = f"{default}/sub/file.xml"
        with patch(
            "startlistsources.start_list_source_file.select_file",
            return_value=file_in_default,
        ):
            result = _select_start_list_file(wx.Frame(None))
            assert result.values[0].value == "sub/file.xml"

    def test_uses_absolute_path_when_outside_default_dir(self, wx_app):
        with patch(
            "startlistsources.start_list_source_file.select_file",
            return_value="/other/path/file.xml",
        ):
            result = _select_start_list_file(wx.Frame(None))
            assert result.values[0].value == "/other/path/file.xml"

    def test_uses_prev_file_dir_as_default(self, wx_app):
        with patch(
            "startlistsources.start_list_source_file.select_file"
        ) as mock_select:
            mock_select.return_value = "/some/path/file.xml"
            _select_start_list_file(wx.Frame(None), prev_file=Path("/prev/dir/old.xml"))

            _args, kwargs = mock_select.call_args
            default_dir = kwargs.get("default_dir", "")
            assert ("/prev/dir/" in default_dir) or ("prev" in default_dir)

    def test_uses_default_dir_when_no_prev_file(self, wx_app):
        with patch(
            "startlistsources.start_list_source_file.select_file"
        ) as mock_select:
            mock_select.return_value = "/some/path/file.xml"
            _select_start_list_file(wx.Frame(None))

            _args, kwargs = mock_select.call_args
            assert kwargs["default_dir"] == DEFAULT_START_LIST_FILE_FOLDER.as_posix()


SAMPLE_XML = """<?xml version="1.0" encoding="windows-1252"?>
<StartList xmlns="http://www.orienteering.org/datastandard/3.0">
  <Event>
    <Id>EVT001</Id>
    <Name>Test Event</Name>
    <StartTime>
      <Date>2024-01-15</Date>
    </StartTime>
    <Organiser>
      <Id>ORG001</Id>
      <Name>Test Club</Name>
    </Organiser>
  </Event>
  <ClassStart>
    <TeamStart>
      <Name>Team Alpha</Name>
      <BibNumber>101</BibNumber>
      <TeamMemberStart>
        <Person>
          <Id>P001</Id>
          <Name>
            <Family>Smith</Family>
            <Given>John</Given>
          </Name>
        </Person>
        <Start>
          <Leg>1</Leg>
          <LegOrder>1</LegOrder>
          <BibNumber>1001</BibNumber>
          <ControlCard>12345</ControlCard>
        </Start>
      </TeamMemberStart>
    </TeamStart>
  </ClassStart>
</StartList>
"""


class TestReadStartList:
    def test_reads_xml_file(self):
        with patch("builtins.open", mock_open(read_data=SAMPLE_XML)):
            team_names, _teams, runners = _read_start_list("/path/file.xml")

            assert team_names == {"101": "Team Alpha"}
            assert "12345" in runners
            assert runners["12345"]["family"] == "Smith"
            assert runners["12345"]["given"] == "John"
            assert runners["12345"]["control_card"] == "12345"

    def test_reads_zip_file(self):
        mock_zip = MagicMock()
        mock_zip.read.return_value = SAMPLE_XML.encode("windows-1252")
        mock_zip.__enter__.return_value = mock_zip

        with patch(
            "startlistsources.start_list_source_file.ZipFile", return_value=mock_zip
        ):
            team_names, _teams, runners = _read_start_list("/path/file.zip")

            assert team_names == {"101": "Team Alpha"}
            assert "12345" in runners
            mock_zip.read.assert_called_once_with("SOFTSTRT.XML")

    def test_raises_on_invalid_root_tag(self):
        bad_xml = "<WrongRoot><Data/></WrongRoot>"
        with (
            patch("builtins.open", mock_open(read_data=bad_xml)),
            pytest.raises(ValueError, match="valid IOFv3"),
        ):
            _read_start_list("/path/file.xml")

    def test_empty_xml_returns_empty(self):
        empty = """<?xml version="1.0"?>
<StartList xmlns="http://www.orienteering.org/datastandard/3.0">
  <Event>
    <Id>EVT001</Id>
    <Name>Test</Name>
  </Event>
</StartList>"""
        with patch("builtins.open", mock_open(read_data=empty)):
            team_names, teams, runners = _read_start_list("/path/file.xml")

            assert team_names == {}
            assert teams == {}
            assert runners == {}


class TestVerifyStartListFile:
    def test_returns_error_when_none(self):
        result = _verify_start_list_file(None)
        assert result.status is False
        assert "must be configured" in result.message

    def test_resolves_relative_path(self):
        with patch(
            "startlistsources.start_list_source_file._read_start_list",
            return_value=({"101": "Team"}, {}, {}),
        ):
            path = Path("relative/file.xml")
            result = _verify_start_list_file(path)
            assert result.status is True

    def test_returns_error_when_no_teams(self):
        with patch(
            "startlistsources.start_list_source_file._read_start_list",
            return_value=({}, {}, {}),
        ):
            result = _verify_start_list_file(
                DEFAULT_START_LIST_FILE_FOLDER / "test.xml"
            )
            assert result.status is True
            assert "No Teams" in result.message

    def test_returns_success_with_team_count(self):
        with patch(
            "startlistsources.start_list_source_file._read_start_list",
            return_value=({"101": "Team A", "102": "Team B"}, {}, {}),
        ):
            result = _verify_start_list_file(
                DEFAULT_START_LIST_FILE_FOLDER / "test.xml"
            )
            assert result.status is True
            assert "2 Teams" in result.message

    def test_catches_exceptions(self):
        with patch(
            "startlistsources.start_list_source_file._read_start_list",
            side_effect=ValueError("bad file"),
        ):
            result = _verify_start_list_file(
                DEFAULT_START_LIST_FILE_FOLDER / "test.xml"
            )
            assert result.status is False
            assert "bad file" in result.message


class TestGetBibRange:
    @pytest.fixture
    def source(self, wx_app):
        with patch("watchdog.observers.Observer") as mock_obs:
            mock_obs.return_value.is_alive.return_value = False
            mock_obs.return_value.name = "MockedObserver"
            with patch.object(
                __import__("utils.config", fromlist=["Config"]).Config,
                "register_config_section_listener",
            ):
                from startlistsources.start_list_source_file import (
                    StartListSourceFile,
                )

                return StartListSourceFile()

    def test_returns_none_when_no_data(self, source):
        assert source.get_bib_range() is None

    def test_returns_range_with_single_team(self, source):
        source.team_names = {101: "Team Alpha"}
        assert source.get_bib_range() == (101, 101)

    def test_returns_range_with_multiple_teams(self, source):
        source.team_names = {50: "Team A", 101: "Team B", 200: "Team C"}
        assert source.get_bib_range() == (50, 200)


class TestGetTeamCount:
    @pytest.fixture
    def source(self, wx_app):
        with patch("watchdog.observers.Observer") as mock_obs:
            mock_obs.return_value.is_alive.return_value = False
            mock_obs.return_value.name = "MockedObserver"
            with patch.object(
                __import__("utils.config", fromlist=["Config"]).Config,
                "register_config_section_listener",
            ):
                from startlistsources.start_list_source_file import (
                    StartListSourceFile,
                )

                return StartListSourceFile()

    def test_returns_none_when_no_data(self, source):
        assert source.get_team_count() is None

    def test_returns_none_when_team_names_empty(self, source):
        source.team_names = {}
        assert source.get_team_count() is None

    def test_returns_count_with_teams(self, source):
        source.team_names = {101: "Team A", 102: "Team B", 103: "Team C"}
        assert source.get_team_count() == 3

    def test_returns_one_with_single_team(self, source):
        source.team_names = {101: "Team Alpha"}
        assert source.get_team_count() == 1


class TestGetRunnerCount:
    @pytest.fixture
    def source(self, wx_app):
        with patch("watchdog.observers.Observer") as mock_obs:
            mock_obs.return_value.is_alive.return_value = False
            mock_obs.return_value.name = "MockedObserver"
            with patch.object(
                __import__("utils.config", fromlist=["Config"]).Config,
                "register_config_section_listener",
            ):
                from startlistsources.start_list_source_file import (
                    StartListSourceFile,
                )

                return StartListSourceFile()

    def test_returns_none_when_no_data(self, source):
        assert source.get_runner_count() is None

    def test_returns_none_when_runners_empty(self, source):
        source.runners = {}
        assert source.get_runner_count() is None

    def test_returns_count_with_runners(self, source):
        source.runners = {
            "12345": {"control_card": "12345"},
            "67890": {"control_card": "67890"},
        }
        assert source.get_runner_count() == 2

    def test_returns_one_with_single_runner(self, source):
        source.runners = {"12345": {"control_card": "12345"}}
        assert source.get_runner_count() == 1
