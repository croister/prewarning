from unittest.mock import patch

from utils.voice_manager_dialog import (
    _is_valid_extra_ranges_format,
    _select_default_country,
    _verify_default_country,
    _verify_extra_ranges,
    _verify_voice,
    get_installed_voice_shortnames,
    parse_extra_ranges,
    validate_extra_ranges,
)


class TestParseExtraRanges:
    """Tests for parse_extra_ranges()"""

    def test_none_returns_empty_list(self):
        assert parse_extra_ranges(None) == []

    def test_empty_string_returns_empty_list(self):
        assert parse_extra_ranges("") == []

    def test_single_range(self):
        assert parse_extra_ranges("1000-1999") == [(1000, 1999)]

    def test_multiple_ranges(self):
        assert parse_extra_ranges("1000-1999,5000-5999") == [(1000, 1999), (5000, 5999)]

    def test_trailing_comma_ignores_empty_last_part(self):
        assert parse_extra_ranges("1000-1999,") == [(1000, 1999)]

    def test_ignores_whitespace_around_values(self):
        assert parse_extra_ranges("  1000-1999  ") == [(1000, 1999)]

    def test_ignores_internal_spaces(self):
        assert parse_extra_ranges("1000-1999, 2000-2999") == [
            (1000, 1999),
            (2000, 2999),
        ]

    def test_three_ranges(self):
        assert parse_extra_ranges("1000-1999,2000-2999,3000-3999") == [
            (1000, 1999),
            (2000, 2999),
            (3000, 3999),
        ]

    def test_start_equals_end_parsed(self):
        assert parse_extra_ranges("0-0") == [(0, 0)]

    def test_start_greater_than_end_skipped(self):
        assert parse_extra_ranges("10-5") == []

    def test_missing_start_skipped(self):
        assert parse_extra_ranges("-5") == []

    def test_missing_end_skipped(self):
        assert parse_extra_ranges("5-") == []

    def test_non_numeric_range_skipped(self):
        assert parse_extra_ranges("abc-def") == []

    def test_negative_start_skipped(self):
        assert parse_extra_ranges("-10-5") == []

    def test_invalid_part_among_valid_ones(self):
        assert parse_extra_ranges("1000-1999,invalid,3000-3999") == [
            (1000, 1999),
            (3000, 3999),
        ]

    def test_type_error_from_int_is_caught(self):
        with patch("builtins.int", side_effect=TypeError("mock")):
            assert parse_extra_ranges("1000-1999") == []


class TestGetInstalledVoiceShortnames:
    def test_empty_when_sounds_dir_missing(self, tmp_path):
        with patch("utils.voice_manager_dialog.SOUNDS_DIR", tmp_path / "nonexistent"):
            assert get_installed_voice_shortnames() == []

    def test_empty_list_when_no_voices_installed(self, tmp_path):
        sounds_dir = tmp_path / "sounds"
        sounds_dir.mkdir()
        with patch("utils.voice_manager_dialog.SOUNDS_DIR", sounds_dir):
            assert get_installed_voice_shortnames() == []

    def test_includes_voice_dirs_with_metadata(self, tmp_path):
        sounds_dir = tmp_path / "sounds"
        sounds_dir.mkdir()
        voice_dir = sounds_dir / "en-US-JennyNeural"
        voice_dir.mkdir()
        (voice_dir / "voice.json").write_text('{"ShortName": "en-US-JennyNeural"}')
        with patch("utils.voice_manager_dialog.SOUNDS_DIR", sounds_dir):
            result = get_installed_voice_shortnames()
            assert "en-US-JennyNeural" in result

    def test_skips_dirs_without_metadata(self, tmp_path):
        sounds_dir = tmp_path / "sounds"
        sounds_dir.mkdir()
        (sounds_dir / "en-US-JennyNeural").mkdir()
        with patch("utils.voice_manager_dialog.SOUNDS_DIR", sounds_dir):
            assert get_installed_voice_shortnames() == []

    def test_skips_invalid_voice_dirnames(self, tmp_path):
        sounds_dir = tmp_path / "sounds"
        sounds_dir.mkdir()
        bad_dir = sounds_dir / "invalid"
        bad_dir.mkdir()
        (bad_dir / "voice.json").write_text("{}")
        with (
            patch("utils.voice_manager_dialog.SOUNDS_DIR", sounds_dir),
            patch(
                "utils.voice_manager_dialog._is_valid_voice_dirname",
                return_value=False,
            ),
        ):
            assert get_installed_voice_shortnames() == []

    def test_skips_files_not_directories(self, tmp_path):
        sounds_dir = tmp_path / "sounds"
        sounds_dir.mkdir()
        (sounds_dir / "some_file.txt").write_text("hello")
        with patch("utils.voice_manager_dialog.SOUNDS_DIR", sounds_dir):
            assert get_installed_voice_shortnames() == []

    def test_multiple_voices_sorted(self, tmp_path):
        sounds_dir = tmp_path / "sounds"
        sounds_dir.mkdir()
        for name in ["en-US-JennyNeural", "en-GB-SoniaNeural", "de-DE-KatjaNeural"]:
            d = sounds_dir / name
            d.mkdir()
            (d / "voice.json").write_text("{}")
        with (
            patch("utils.voice_manager_dialog.SOUNDS_DIR", sounds_dir),
            patch(
                "utils.voice_manager_dialog._is_valid_voice_dirname",
                return_value=True,
            ),
        ):
            result = get_installed_voice_shortnames()
            assert result == [
                "de-DE-KatjaNeural",
                "en-GB-SoniaNeural",
                "en-US-JennyNeural",
            ]


class TestIsValidExtraRangesFormat:
    def test_none_is_valid(self):
        assert _is_valid_extra_ranges_format(None) is True

    def test_empty_string_is_valid(self):
        assert _is_valid_extra_ranges_format("") is True

    def test_single_range_is_valid(self):
        assert _is_valid_extra_ranges_format("1000-1999") is True

    def test_multiple_ranges_valid(self):
        assert _is_valid_extra_ranges_format("1000-1999, 3000-3999") is True

    def test_start_greater_than_end_invalid(self):
        assert _is_valid_extra_ranges_format("10-5") is False

    def test_negative_start_invalid(self):
        assert _is_valid_extra_ranges_format("-10-5") is False

    def test_negative_end_invalid(self):
        assert _is_valid_extra_ranges_format("5--1") is False

    def test_non_numeric_range_invalid(self):
        assert _is_valid_extra_ranges_format("abc-def") is False

    def test_missing_dash_invalid(self):
        assert _is_valid_extra_ranges_format("1000") is False

    def test_invalid_part_among_valid_returns_false(self):
        assert _is_valid_extra_ranges_format("1000-1999,invalid,3000-3999") is False

    def test_trailing_comma_valid(self):
        assert _is_valid_extra_ranges_format("1000-1999,") is True

    def test_range_within_default_is_invalid(self):
        assert _is_valid_extra_ranges_format("0-0") is False

    def test_range_overlapping_default_is_invalid(self):
        assert _is_valid_extra_ranges_format("500-1500") is False

    def test_range_starting_at_default_boundary_is_invalid(self):
        assert _is_valid_extra_ranges_format("0-100") is False

    def test_range_after_default_is_valid(self):
        assert _is_valid_extra_ranges_format("1000-1999") is True


class TestValidateExtraRanges:
    def test_empty_returns_true(self):
        result = validate_extra_ranges("")
        assert result is True

    def test_valid_range_returns_true(self):
        result = validate_extra_ranges("1000-1999")
        assert result is True

    def test_overlapping_default_range_returns_validation_error(self):
        from validators.validation_error import ValidationError

        result = validate_extra_ranges("0-0")
        assert isinstance(result, ValidationError)
        assert "must not overlap" in result.message

    def test_format_error_has_format_message(self):
        from validators.validation_error import ValidationError

        result = validate_extra_ranges("abc")
        assert isinstance(result, ValidationError)
        assert "Invalid extra ranges format" in result.message

    def test_invalid_range_returns_validation_error(self):
        from validators.validation_error import ValidationError

        result = validate_extra_ranges("abc-def")
        assert isinstance(result, ValidationError)

    def test_invalid_range_has_message(self):
        from validators.validation_error import ValidationError

        result = validate_extra_ranges("abc")
        assert isinstance(result, ValidationError)
        assert "Invalid extra ranges format" in result.message

    def test_reversed_range_has_reversed_message(self):
        from validators.validation_error import ValidationError

        result = validate_extra_ranges("100-50")
        assert isinstance(result, ValidationError)
        assert "must not be greater" in result.message


class TestVerifyDefaultCountry:
    def test_valid_country_returns_true(self):
        assert _verify_default_country("SWE") is True

    def test_valid_country_lowercase_returns_true(self):
        assert _verify_default_country("swe") is True

    def test_empty_returns_false(self):
        assert _verify_default_country("") is False

    def test_invalid_code_returns_false(self):
        assert _verify_default_country("XYZ") is False


class TestVerifyVoice:
    def test_empty_returns_false(self):
        assert _verify_voice("") is False

    def test_missing_voice_returns_false(self, tmp_path):
        with patch("utils.voice_manager_dialog.SOUNDS_DIR", tmp_path / "sounds"):
            assert _verify_voice("en-US-JennyNeural") is False

    def test_existing_voice_with_metadata_returns_true(self, tmp_path):
        sounds_dir = tmp_path / "sounds"
        sounds_dir.mkdir()
        voice_dir = sounds_dir / "en-US-JennyNeural"
        voice_dir.mkdir()
        (voice_dir / "voice.json").write_text("{}")
        with patch("utils.voice_manager_dialog.SOUNDS_DIR", sounds_dir):
            assert _verify_voice("en-US-JennyNeural") is True

    def test_existing_voice_without_metadata_returns_false(self, tmp_path):
        sounds_dir = tmp_path / "sounds"
        sounds_dir.mkdir()
        (sounds_dir / "en-US-JennyNeural").mkdir()
        with patch("utils.voice_manager_dialog.SOUNDS_DIR", sounds_dir):
            assert _verify_voice("en-US-JennyNeural") is False

    def test_nonexistent_voice_returns_false(self, tmp_path):
        sounds_dir = tmp_path / "sounds"
        sounds_dir.mkdir()
        with patch("utils.voice_manager_dialog.SOUNDS_DIR", sounds_dir):
            assert _verify_voice("en-US-Missing") is False


class TestVerifyExtraRanges:
    def test_empty_returns_true(self):
        assert _verify_extra_ranges("") is True

    def test_valid_range_after_default_returns_true(self):
        assert _verify_extra_ranges("1000-1999") is True

    def test_single_item_range_after_default_returns_true(self):
        assert _verify_extra_ranges("1000-1000") is True

    def test_range_within_default_returns_verification_result(self):
        from utils.config_definitions import VerificationResult

        result = _verify_extra_ranges("0-0")
        assert isinstance(result, VerificationResult)
        assert not result

    def test_range_overlapping_default_returns_verification_result(self):
        from utils.config_definitions import VerificationResult

        result = _verify_extra_ranges("500-1500")
        assert isinstance(result, VerificationResult)
        assert not result

    def test_overlap_message_describes_overlap(self):
        from utils.config_definitions import VerificationResult

        result = _verify_extra_ranges("0-0")
        assert isinstance(result, VerificationResult)
        assert "must not overlap" in result.message

    def test_invalid_format_returns_verification_result(self):
        from utils.config_definitions import VerificationResult

        result = _verify_extra_ranges("abc-def")
        assert isinstance(result, VerificationResult)
        assert not result

    def test_format_message_describes_format(self):
        from utils.config_definitions import VerificationResult

        result = _verify_extra_ranges("abc-def")
        assert isinstance(result, VerificationResult)
        assert "Invalid extra ranges format" in result.message

    def test_start_greater_than_end_returns_verification_result(self):
        from utils.config_definitions import VerificationResult

        result = _verify_extra_ranges("10-5")
        assert isinstance(result, VerificationResult)
        assert not result

    def test_start_greater_than_end_has_reversed_message(self):
        from utils.config_definitions import VerificationResult

        result = _verify_extra_ranges("10-5")
        assert isinstance(result, VerificationResult)
        assert "must not be greater" in result.message


class TestSelectDefaultCountry:
    def test_returns_selection_result(self):
        result = _select_default_country()
        from utils.config_definitions import SelectionResult

        assert isinstance(result, SelectionResult)

    def test_contains_sweden(self):
        result = _select_default_country()
        display_names = [v.display_name for v in result.values]
        assert "Sweden (SWE)" in display_names

    def test_contains_all_countries(self):
        from utils.country_dict_by_ioc import COUNTRIES

        result = _select_default_country()
        assert len(result.values) == len(COUNTRIES)

    def test_stores_ioc_code_as_value(self):
        result = _select_default_country()
        sweden = next(v for v in result.values if v.display_name == "Sweden (SWE)")
        assert sweden.value == "SWE"

    def test_sorted_by_country_name(self):
        result = _select_default_country()
        display_names = [v.display_name for v in result.values]
        assert display_names == sorted(display_names)
