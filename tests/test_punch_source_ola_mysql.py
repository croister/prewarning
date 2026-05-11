from unittest.mock import MagicMock, patch

from punchsources.punch_source_ola_mysql import (
    _split_time_control_name,
    _split_time_control_description,
    _select_control_ids,
    _verify_control_ids,
    _verify_fetch,
    PunchSourceOlaMySql,
)


class TestSplitTimeControlName:
    def test_uses_split_time_control_name(self):
        ctrl = {'splitTimeControlName': 'Split1', 'controlName': 'Ctrl1'}
        assert _split_time_control_name(ctrl) == 'Split1'

    def test_falls_back_to_control_name(self):
        ctrl = {'splitTimeControlName': '', 'controlName': 'Ctrl1'}
        assert _split_time_control_name(ctrl) == 'Ctrl1'

    def test_falls_back_to_control_name_when_none(self):
        ctrl = {'splitTimeControlName': None, 'controlName': 'Ctrl1'}
        assert _split_time_control_name(ctrl) == 'Ctrl1'

    def test_returns_empty_when_both_empty(self):
        ctrl = {'splitTimeControlName': '', 'controlName': ''}
        assert _split_time_control_name(ctrl) == ''

    def test_returns_empty_when_both_none(self):
        ctrl = {'splitTimeControlName': None, 'controlName': None}
        assert _split_time_control_name(ctrl) == ''


class TestSplitTimeControlDescription:
    def test_uses_name_from_split_time_control_name(self):
        ctrl = {
            'ID': 101,
            'splitTimeControlName': 'MySplit',
            'controlName': 'Backup',
            'punchingCodes': '1,2,3',
            'classCount': 5,
            'classNames': 'Class A, Class B',
        }
        result = _split_time_control_description(ctrl)
        assert '101' in result
        assert 'MySplit' in result
        assert '1,2,3' in result
        assert '5 classes' in result or '5' in result
        assert 'Class A' in result

    def test_truncates_long_class_names(self):
        ctrl = {
            'ID': 1,
            'splitTimeControlName': 'Test',
            'controlName': 'Test',
            'punchingCodes': '1',
            'classCount': 2,
            'classNames': 'A' * 100,
        }
        result = _split_time_control_description(ctrl)
        assert '...' in result
        assert len(result) < 200

    def test_handles_none_class_names(self):
        ctrl = {
            'ID': 1,
            'splitTimeControlName': 'Test',
            'controlName': 'Test',
            'punchingCodes': '1',
            'classCount': 1,
            'classNames': None,
        }
        result = _split_time_control_description(ctrl)
        assert result is not None


class TestSelectControlIds:
    def test_returns_selection(self):
        mock_conn = MagicMock()
        with patch('punchsources.punch_source_ola_mysql.connect', return_value=mock_conn), \
             patch('punchsources.punch_source_ola_mysql.get_ola_db_version', return_value=565), \
             patch('punchsources.punch_source_ola_mysql.is_relay_event', return_value=True), \
             patch('punchsources.punch_source_ola_mysql.get_event_race_split_time_controls',
                   return_value=[{'ID': 1, 'splitTimeControlName': 'C1', 'controlName': 'X',
                                  'punchingCodes': '10', 'classCount': 3, 'classNames': 'A'}]):

            result = _select_control_ids('host', 'user', 'pass', 'db', 1, 10)

            assert result is not False
            assert result.values[0].value == 1

    def test_returns_false_on_exception(self):
        with patch('punchsources.punch_source_ola_mysql.connect', side_effect=Exception('fail')):
            result = _select_control_ids('host', 'user', 'pass', 'db', 1, 10)
            assert result is False


class TestVerifyControlIds:
    def test_returns_true_when_valid(self):
        mock_conn = MagicMock()
        with patch('punchsources.punch_source_ola_mysql.connect', return_value=mock_conn), \
             patch('punchsources.punch_source_ola_mysql.get_ola_db_version', return_value=565), \
             patch('punchsources.punch_source_ola_mysql.is_relay_event', return_value=True), \
             patch('punchsources.punch_source_ola_mysql.are_valid_event_race_control_ids', return_value=True):

            result = _verify_control_ids('host', 'user', 'pass', 'db', 1, 10, '101 102')
            assert result is True

    def test_parses_space_separated_ids(self):
        mock_conn = MagicMock()
        with patch('punchsources.punch_source_ola_mysql.connect', return_value=mock_conn), \
             patch('punchsources.punch_source_ola_mysql.get_ola_db_version', return_value=565), \
             patch('punchsources.punch_source_ola_mysql.is_relay_event', return_value=True), \
             patch('punchsources.punch_source_ola_mysql.are_valid_event_race_control_ids', return_value=True) as mock_valid:

            _verify_control_ids('host', 'user', 'pass', 'db', 1, 10, '101 102')

            kwargs = mock_valid.call_args[1]
            assert kwargs['control_ids'] == [101, 102]

    def test_handles_empty_ids(self):
        mock_conn = MagicMock()
        with patch('punchsources.punch_source_ola_mysql.connect', return_value=mock_conn), \
             patch('punchsources.punch_source_ola_mysql.get_ola_db_version', return_value=565), \
             patch('punchsources.punch_source_ola_mysql.is_relay_event', return_value=True), \
             patch('punchsources.punch_source_ola_mysql.are_valid_event_race_control_ids', return_value=True) as mock_valid:

            _verify_control_ids('host', 'user', 'pass', 'db', 1, 10, '')

            kwargs = mock_valid.call_args[1]
            assert kwargs['control_ids'] == []

    def test_returns_false_on_exception(self):
        with patch('punchsources.punch_source_ola_mysql.connect', side_effect=Exception('fail')):
            result = _verify_control_ids('host', 'user', 'pass', 'db', 1, 10, '101')
            assert result is False


class TestVerifyFetch:
    def test_returns_success_with_punches(self):
        mock_conn = MagicMock()
        with patch('punchsources.punch_source_ola_mysql.connect', return_value=mock_conn), \
             patch('punchsources.punch_source_ola_mysql.get_ola_db_version', return_value=565), \
             patch('punchsources.punch_source_ola_mysql.get_event_race_split_times',
                   return_value=[{'id': '1_1_1'}, {'id': '1_2_2'}]):

            result = _verify_fetch('host', 'user', 'pass', 'db', 1, 10, '101', '2024-01-01 00:00:00.000')
            assert result.status is True
            assert '2 Punches' in result.message

    def test_no_punches_message(self):
        mock_conn = MagicMock()
        with patch('punchsources.punch_source_ola_mysql.connect', return_value=mock_conn), \
             patch('punchsources.punch_source_ola_mysql.get_ola_db_version', return_value=565), \
             patch('punchsources.punch_source_ola_mysql.get_event_race_split_times', return_value=[]):

            result = _verify_fetch('host', 'user', 'pass', 'db', 1, 10, '101', '2024-01-01 00:00:00.000')
            assert result.status is True
            assert 'No Punches' in result.message

    def test_handles_last_received_punch_id(self):
        mock_conn = MagicMock()
        with patch('punchsources.punch_source_ola_mysql.connect', return_value=mock_conn), \
             patch('punchsources.punch_source_ola_mysql.get_ola_db_version', return_value=565), \
             patch('punchsources.punch_source_ola_mysql.get_event_race_split_times',
                   return_value=[{'id': 'dup_1'}, {'id': 'new_1'}]):

            result = _verify_fetch('host', 'user', 'pass', 'db', 1, 10, '101', '2024-01-01 00:00:00.000',
                                   last_received_punch_id='dup_1')
            assert result.status is True
            assert '1 ignored' in result.message

    def test_parses_control_ids(self):
        mock_conn = MagicMock()
        with patch('punchsources.punch_source_ola_mysql.connect', return_value=mock_conn), \
             patch('punchsources.punch_source_ola_mysql.get_ola_db_version', return_value=565), \
             patch('punchsources.punch_source_ola_mysql.get_event_race_split_times',
                   return_value=[]) as mock_split:

            _verify_fetch('host', 'user', 'pass', 'db', 1, 10, '101 102', '2024-01-01 00:00:00.000')

            kwargs = mock_split.call_args[1]
            assert kwargs['control_ids'] == [101, 102]

    def test_returns_false_on_exception(self):
        with patch('punchsources.punch_source_ola_mysql.connect', side_effect=Exception('fail')):
            result = _verify_fetch('host', 'user', 'pass', 'db', 1, 10, '101', '2024-01-01 00:00:00.000')
            assert result.status is False
            assert 'fail' in result.message


class TestPunchSourceOlaMySql:
    def test_fetch_punches_logs_unexpected_exception(self):
        mock_ola = MagicMock()
        mock_ola.get_event_race_split_times.side_effect = KeyError('test_key')
        with patch('punchsources.punch_source_ola_mysql.OlaMySql', return_value=mock_ola), \
             patch.object(PunchSourceOlaMySql, 'update'):
            source = PunchSourceOlaMySql()
            source.fetch_interval_seconds = 0
            mock_stop = MagicMock()
            mock_stop.is_set.side_effect = [False, True]
            source._stop_event = mock_stop
            with patch.object(source, '_save_state'), \
                 patch.object(source.logger, 'error') as mock_log:
                source._fetch_punches()
                assert any('Unexpected error fetching punches' in str(c)
                           for c in mock_log.call_args_list), \
                    f'Expected log not found. Calls: {mock_log.call_args_list}'
