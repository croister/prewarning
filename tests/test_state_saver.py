from pathlib import Path

import pytest

from utils.config_definitions import RuntimeStateGroup, RuntimeStateOptionDefinition
from utils.state_saver import StateSaverMixin, _StateSaverGroup


class FakeStateSaver(StateSaverMixin):
    def __init__(self, config_section_name: str,
                 runtime_state_groups, data_dir: Path):
        super().__init__(config_section_name, runtime_state_groups, data_dir)

    def _save_state(self):
        pass


@pytest.fixture
def group_defs():
    rsg = RuntimeStateGroup('test_state.ini')
    RuntimeStateOptionDefinition(rsg, 'last_value', 'Last Value', str, 'The last value', default_value='default')
    RuntimeStateOptionDefinition(rsg, 'counter', 'Counter', int, 'A counter', default_value=0)
    RuntimeStateOptionDefinition(rsg, 'flag', 'Flag', bool, 'A flag', default_value=False)
    return [rsg]


class TestStateSaverMixin:
    def test_initialization_creates_state_file(self, tmp_path, group_defs):
        saver = FakeStateSaver('TestSection', group_defs, tmp_path)
        state_file = tmp_path / 'test_state.ini'
        assert state_file.exists()
        saver._cleanup()

    def test_reads_default_values(self, tmp_path, group_defs):
        saver = FakeStateSaver('TestSection', group_defs, tmp_path)
        option_defs = list(group_defs[0].option_definitions.values())
        assert saver._get_value(option_defs[0]) == 'default'
        assert saver._get_value(option_defs[1]) == 0
        assert saver._get_value(option_defs[2]) is False
        saver._cleanup()

    def test_save_and_read_value(self, tmp_path, group_defs):
        saver = FakeStateSaver('TestSection', group_defs, tmp_path)
        option_defs = list(group_defs[0].option_definitions.values())
        saver._save_value(option_defs[0], 'saved_value')
        assert saver._get_value(option_defs[0]) == 'saved_value'
        saver._cleanup()

    def test_data_read_tracking_new_file(self, tmp_path, group_defs):
        saver = FakeStateSaver('TestSection', group_defs, tmp_path)
        option_defs = list(group_defs[0].option_definitions.values())
        assert not saver._data_read(option_defs[0])
        saver._cleanup()

    def test_save_multiple_values(self, tmp_path, group_defs):
        saver = FakeStateSaver('TestSection', group_defs, tmp_path)
        option_defs = list(group_defs[0].option_definitions.values())
        saver._save_values({
            option_defs[0]: 'hello',
            option_defs[1]: 42,
            option_defs[2]: True,
        })
        assert saver._get_value(option_defs[0]) == 'hello'
        assert saver._get_value(option_defs[1]) == 42
        assert saver._get_value(option_defs[2]) is True
        saver._cleanup()

    def test_cleanup_removes_file(self, tmp_path, group_defs):
        saver = FakeStateSaver('TestSection', group_defs, tmp_path)
        state_file = tmp_path / 'test_state.ini'
        assert state_file.exists()
        saver._cleanup()
        assert not state_file.exists()

    def test_data_read_true_after_file_exists(self, tmp_path):
        rsg = RuntimeStateGroup('test.ini')
        RuntimeStateOptionDefinition(rsg, 'val', 'Val', str, 'desc', default_value='x')
        opt_defs = list(rsg.option_definitions.values())
        saver1 = FakeStateSaver('Section', [rsg], tmp_path)
        assert not saver1._data_read(opt_defs[0])
        saver2 = FakeStateSaver('Section', [rsg], tmp_path)
        assert saver2._data_read(opt_defs[0])
        saver2._cleanup()
        saver1._cleanup()

    def test_multiple_groups(self, tmp_path):
        rsg1 = RuntimeStateGroup('group1.ini')
        RuntimeStateOptionDefinition(rsg1, 'a', 'A', str, 'desc', default_value='x')
        rsg2 = RuntimeStateGroup('group2.ini')
        RuntimeStateOptionDefinition(rsg2, 'b', 'B', str, 'desc', default_value='y')
        saver = FakeStateSaver('Section', [rsg1, rsg2], tmp_path)
        assert (tmp_path / 'group1.ini').exists()
        assert (tmp_path / 'group2.ini').exists()
        saver._cleanup()
        assert not (tmp_path / 'group1.ini').exists()
        assert not (tmp_path / 'group2.ini').exists()

    def test_save_values_multiple_groups(self, tmp_path):
        rsg1 = RuntimeStateGroup('g1.ini')
        opt1 = RuntimeStateOptionDefinition(rsg1, 'a', 'A', str, 'desc', default_value='x')
        rsg2 = RuntimeStateGroup('g2.ini')
        opt2 = RuntimeStateOptionDefinition(rsg2, 'b', 'B', str, 'desc', default_value='y')
        saver = FakeStateSaver('Section', [rsg1, rsg2], tmp_path)
        saver._save_values({opt1: 'from_1', opt2: 'from_2'})
        assert saver._get_value(opt1) == 'from_1'
        assert saver._get_value(opt2) == 'from_2'
        saver._cleanup()

    def test_validation_error_resets_to_default(self, tmp_path):
        rsg = RuntimeStateGroup('test.ini')
        RuntimeStateOptionDefinition(
            rsg, 'val', 'Val', str, 'desc',
            default_value='valid', valid_values=['valid', 'ok'])
        opt_defs = list(rsg.option_definitions.values())
        saver1 = FakeStateSaver('Section', [rsg], tmp_path)
        assert saver1._get_value(opt_defs[0]) == 'valid'
        saver1._cleanup()
        with open(tmp_path / 'test.ini', 'w') as f:
            f.write('[Section]\nval = invalid\n')
        rsg2 = RuntimeStateGroup('test.ini')
        opt2 = RuntimeStateOptionDefinition(
            rsg2, 'val', 'Val', str, 'desc',
            default_value='valid', valid_values=['valid', 'ok'])
        group = _StateSaverGroup('Section', rsg2, tmp_path)
        assert group._get_value(opt2) == 'valid'

    def test_state_saver_group_save_values(self, tmp_path):
        rsg = RuntimeStateGroup('test.ini')
        opt = RuntimeStateOptionDefinition(rsg, 'val', 'Val', str, 'desc', default_value='x')
        group = _StateSaverGroup('Section', rsg, tmp_path)
        group._save_values({opt: 'batched'})
        assert group._get_value(opt) == 'batched'
        group._cleanup()

    def test_state_saver_group_cleanup(self, tmp_path):
        rsg = RuntimeStateGroup('test.ini')
        RuntimeStateOptionDefinition(rsg, 'val', 'Val', str, 'desc', default_value='x')
        group = _StateSaverGroup('Section', rsg, tmp_path)
        state_file = tmp_path / 'test.ini'
        assert state_file.exists()
        group._cleanup()
        assert not state_file.exists()
