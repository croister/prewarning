from unittest.mock import patch

from utils.voice_manager_dialog import parse_extra_ranges


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
