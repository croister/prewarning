from unittest.mock import MagicMock, patch, call
from configparser import ConfigParser
import wx
import pytest

from utils.config_definitions import (
    ConfigOptionDefinition,
    ConfigSectionDefinition,
    RuntimeStateGroup,
    RuntimeStateOptionDefinition,
)
from utils.config import Config
from utils.config_dialog import (
    ConfigOptionValidator,
    ConfigSectionPanel,
    ConfigDialog,
)


# ---------------------------------------------------------------------------
# ConfigOptionValidator
# ---------------------------------------------------------------------------

class TestConfigOptionValidator:
    @pytest.fixture
    def config_option(self):
        return ConfigOptionDefinition('opt', 'Opt', str, 'desc',
                                       default_value='default')

    @pytest.fixture
    def config_section(self):
        return ConfigSectionDefinition('sec', 'Section')

    @pytest.fixture
    def config_mock(self, config_section):
        cfg = MagicMock(spec=Config)
        section = MagicMock()
        section.get.return_value = 'stored_value'
        section.__contains__.return_value = True
        section.__getitem__.return_value = 'stored_value'
        cfg.get_section.return_value = section
        cfg.config_sections = {config_section.name: section}
        return cfg

    @pytest.fixture
    def parent_frame(self, wx_app):
        frame = wx.Frame(None)
        yield frame
        frame.Destroy()



    def _make_validator(self, config_option, config_section, config_mock):
        return ConfigOptionValidator(config_option, config_section, config_mock)

    def test_clone(self, config_option, config_section, config_mock):
        v = self._make_validator(config_option, config_section, config_mock)
        clone = v.Clone()
        assert type(clone) is ConfigOptionValidator
        assert clone.config_option_definition is config_option
        assert clone.config_section_definition is config_section
        assert clone.config is config_mock

    def test_validate_section_not_enabled_returns_true(
            self, parent_frame, config_option, config_section, config_mock):
        config_section.is_enabled = MagicMock(return_value=False)
        v = self._make_validator(config_option, config_section, config_mock)
        ctrl = wx.TextCtrl(parent_frame, value='bad', validator=v)
        ctrl.SetValidator(v)
        assert v.Validate(parent_frame) is True

    def test_validate_valid_value_returns_true(
            self, parent_frame, config_option, config_section, config_mock):
        config_section.is_enabled = MagicMock(return_value=True)
        v = self._make_validator(config_option, config_section, config_mock)
        ctrl = wx.TextCtrl(parent_frame, value='ok', validator=v)
        v.SetWindow(ctrl)
        assert v.Validate(parent_frame) is True

    def test_validate_invalid_value_returns_false(
            self, wx_app, config_option, config_section, config_mock):
        config_section.is_enabled = MagicMock(return_value=True)
        config_option.mandatory = True
        import wx.lib.scrolledpanel
        grandparent = wx.lib.scrolledpanel.ScrolledPanel(wx.Frame(None))
        parent_panel = wx.Panel(grandparent)
        v = self._make_validator(config_option, config_section, config_mock)
        ctrl = wx.TextCtrl(parent_panel, value='', validator=v)
        v.SetWindow(ctrl)
        result = v.Validate(parent_panel)
        assert result is False
        assert ctrl.GetBackgroundColour() == wx.Colour('pink')
        assert ctrl.GetToolTip() is not None
        grandparent.GetParent().Destroy()

    def test_transfer_to_window_sets_value(
            self, parent_frame, config_option, config_section, config_mock):
        v = self._make_validator(config_option, config_section, config_mock)
        ctrl = wx.TextCtrl(parent_frame, value='', validator=v)
        v.SetWindow(ctrl)
        v.TransferToWindow()
        assert ctrl.GetValue() == 'stored_value'

    def test_transfer_to_window_runtime_state_only(
            self, parent_frame, config_section, config_mock):
        rsg = RuntimeStateGroup('test.dat')
        rt_option = RuntimeStateOptionDefinition(rsg, 'opt', 'Opt', str, 'desc')
        rt_section = ConfigSectionDefinition('rt_sec', 'Section')
        rt_section.option_definitions['opt'] = rt_option
        v = self._make_validator(rt_option, rt_section, config_mock)
        ctrl = wx.TextCtrl(parent_frame, value='', validator=v)
        v.SetWindow(ctrl)
        assert v.TransferToWindow() is True
        assert ctrl.GetValue() == ''

    def test_transfer_from_window(
            self, parent_frame, config_option, config_section, config_mock):
        section = config_mock.get_section.return_value
        v = self._make_validator(config_option, config_section, config_mock)
        ctrl = wx.TextCtrl(parent_frame, value='from_ctrl', validator=v)
        v.SetWindow(ctrl)
        v.TransferFromWindow()
        assert section.__setitem__.call_args_list == \
               [call('opt', 'from_ctrl')]


# ---------------------------------------------------------------------------
# ConfigSectionPanel - static / simple methods
# ---------------------------------------------------------------------------

class TestConfigSectionPanelStatic:
    def test_label_name(self):
        assert ConfigSectionPanel._label_name('foo') == 'foo_label_name'

    def test_default_button_name(self):
        assert ConfigSectionPanel._default_button_name('bar') == 'bar_default_button_name'

    def test_verify_button_name(self):
        assert ConfigSectionPanel._verify_button_name('baz') == 'baz_verify_button_name'

    def test_select_button_name(self):
        assert ConfigSectionPanel._select_button_name('qux') == 'qux_select_button_name'

    @pytest.mark.parametrize('size,expected', [
        (0, False),
        (20, False),
        (21, True),
        (100, True),
    ])
    def test_too_large_for_combo_box(self, size, expected):
        assert ConfigSectionPanel._too_large_for_combo_box(list(range(size))) is expected

    def test_use_combo_box_for_none(self):
        assert ConfigSectionPanel._use_combo_box_for(None) is False

    def test_use_combo_box_for_small(self):
        assert ConfigSectionPanel._use_combo_box_for([1, 2, 3]) is True

    def test_use_combo_box_for_large(self):
        assert ConfigSectionPanel._use_combo_box_for(list(range(21))) is False

    def test_use_selector_for_none(self):
        assert ConfigSectionPanel._use_selector_for(None) is False

    def test_use_selector_for_small(self):
        assert ConfigSectionPanel._use_selector_for([1, 2, 3]) is False

    def test_use_selector_for_large(self):
        assert ConfigSectionPanel._use_selector_for(list(range(21))) is True


class TestConfigSectionPanelTracking:
    @pytest.fixture
    def section_def(self):
        rsg = RuntimeStateGroup('filename.dat')
        opt = RuntimeStateOptionDefinition(rsg, 'track', 'Track', str, 'desc',
                                      default_value='val')
        sec = ConfigSectionDefinition('sec', 'Section')
        sec.option_definitions['track'] = opt
        return sec

    @pytest.fixture
    def config_mock(self):
        cfg = MagicMock(spec=Config)
        cfg.get_section.return_value = MagicMock()
        cfg.config_sections = {}
        return cfg

    def test_mark_dirty_if_tracking(self, wx_app, section_def, config_mock):
        frame = wx.Frame(None)
        panel = ConfigSectionPanel(
            section_def, config_mock.get_section.return_value,
            config_mock, frame, state_provider=MagicMock())
        ctrl = wx.TextCtrl(panel, value='x', name='track')
        event = wx.CommandEvent(wx.wxEVT_TEXT, ctrl.GetId())
        event.SetEventObject(ctrl)

        panel._tracking_controls['track'] = ctrl
        panel._tracking_dirty['track'] = False
        panel._mark_dirty_if_tracking(event)
        assert panel._tracking_dirty['track'] is True
        frame.Destroy()

    def test_mark_dirty_if_tracking_non_tracking(
            self, wx_app, section_def, config_mock):
        frame = wx.Frame(None)
        panel = ConfigSectionPanel(
            section_def, config_mock.get_section.return_value,
            config_mock, frame, state_provider=MagicMock())
        ctrl = wx.TextCtrl(panel, value='x')
        event = wx.CommandEvent(wx.wxEVT_TEXT, ctrl.GetId())
        event.SetEventObject(ctrl)

        panel._mark_dirty_if_tracking(event)
        # No KeyError because 'track' is not in _tracking_controls
        frame.Destroy()

    def test_save_runtime_state(
            self, wx_app, section_def, config_mock):
        state_provider = MagicMock()
        state_provider.get_runtime_value.return_value = 'runtime_val'
        frame = wx.Frame(None)
        panel = ConfigSectionPanel(
            section_def, config_mock.get_section.return_value,
            config_mock, frame, state_provider=state_provider)
        ctrl = wx.TextCtrl(panel, value='new_val', name='track')
        panel._tracking_controls['track'] = ctrl
        panel._tracking_dirty['track'] = True

        panel._save_runtime_state()
        state_provider.set_runtime_value.assert_called_once()
        frame.Destroy()

    def test_save_runtime_state_not_dirty(
            self, wx_app, section_def, config_mock):
        state_provider = MagicMock()
        frame = wx.Frame(None)
        panel = ConfigSectionPanel(
            section_def, config_mock.get_section.return_value,
            config_mock, frame, state_provider=state_provider)
        ctrl = wx.TextCtrl(panel, value='val', name='track')
        panel._tracking_controls['track'] = ctrl
        panel._tracking_dirty['track'] = False

        panel._save_runtime_state()
        state_provider.set_runtime_value.assert_not_called()
        frame.Destroy()

    def test_save_runtime_state_no_provider(
            self, wx_app, section_def, config_mock):
        frame = wx.Frame(None)
        panel = ConfigSectionPanel(
            section_def, config_mock.get_section.return_value,
            config_mock, frame, state_provider=None)
        # Should not raise
        panel._save_runtime_state()
        frame.Destroy()

    def test_constructor_no_provider_reads_state_file(self, wx_app, tmp_path):
        with patch('utils.config_definitions.DATA_DIR', tmp_path):
            rsg = RuntimeStateGroup('test.dat')
            opt = RuntimeStateOptionDefinition(
                rsg, 'track', 'Track', str, 'desc', default_value='x')
        sec = ConfigSectionDefinition('sec', 'Section')
        sec.option_definitions['track'] = opt
        config = ConfigParser()
        config['sec'] = {'track': 'from_file'}
        with open(tmp_path / 'test.dat', 'w') as f:
            config.write(f)
        cfg = MagicMock(spec=Config)
        cfg.get_section.return_value = MagicMock()
        cfg.config_sections = {'sec': MagicMock()}
        frame = wx.Frame(None)
        panel = ConfigSectionPanel(
            sec, cfg.get_section.return_value, cfg, frame, state_provider=None)
        ctrl = panel._tracking_controls.get('track')
        assert ctrl is not None
        assert ctrl.GetValue() == 'from_file'
        frame.Destroy()
        (tmp_path / 'test.dat').unlink()

    def test_save_runtime_state_no_provider_writes_file(
            self, wx_app, tmp_path):
        with patch('utils.config_definitions.DATA_DIR', tmp_path):
            rsg = RuntimeStateGroup('test.dat')
            opt = RuntimeStateOptionDefinition(
                rsg, 'track', 'Track', str, 'desc', default_value='x')
        sec = ConfigSectionDefinition('sec', 'Section')
        sec.option_definitions['track'] = opt
        cfg = MagicMock(spec=Config)
        cfg.get_section.return_value = MagicMock()
        cfg.config_sections = {'sec': MagicMock()}
        frame = wx.Frame(None)
        panel = ConfigSectionPanel(
            sec, cfg.get_section.return_value, cfg, frame, state_provider=None)
        ctrl = wx.TextCtrl(panel, value='saved_val', name='track')
        panel._tracking_controls['track'] = ctrl
        panel._tracking_dirty['track'] = True
        panel._save_runtime_state()
        config = ConfigParser()
        config.read(str(tmp_path / 'test.dat'))
        assert config['sec']['track'] == 'saved_val'
        frame.Destroy()
        (tmp_path / 'test.dat').unlink()

    def test_validate_resets_button_colors(
            self, wx_app, section_def, config_mock):
        frame = wx.Frame(None)
        panel = ConfigSectionPanel(
            section_def, config_mock.get_section.return_value,
            config_mock, frame, state_provider=MagicMock())
        btn = wx.Button(panel, name='track_default_button_name')
        btn.SetBackgroundColour(wx.Colour('pink'))
        btn.SetToolTip('old tip')
        panel.Validate()
        assert btn.GetBackgroundColour() != wx.Colour('pink')
        assert 'Reset' in btn.GetToolTip().GetTip()
        frame.Destroy()

    def test_update_calls_dialog_when_provided(
            self, wx_app, section_def, config_mock):
        frame = wx.Frame(None)
        dialog = MagicMock()
        panel = ConfigSectionPanel(
            section_def, config_mock.get_section.return_value,
            config_mock, frame, state_provider=MagicMock(), dialog=dialog)
        panel.update(validate=True)
        dialog.update_visibility.assert_called_once()
        dialog.Validate.assert_called_once()

    def test_update_skips_dialog_when_none(
            self, wx_app, section_def, config_mock):
        frame = wx.Frame(None)
        panel = ConfigSectionPanel(
            section_def, config_mock.get_section.return_value,
            config_mock, frame, state_provider=MagicMock())
        with patch.object(panel, 'update_visibility') as mock_self_update:
            panel.update(validate=True)
            mock_self_update.assert_called_once()


# ---------------------------------------------------------------------------
# ConfigDialog
# ---------------------------------------------------------------------------

class TestConfigDialog:
    @pytest.fixture
    def config_mock(self):
        cfg = MagicMock(spec=Config)
        cfg.CONFIG_SECTION_DEFINITIONS = {}
        cfg.config_sections = {}
        cfg.get_section.return_value = MagicMock()
        return cfg

    def test_save_runtime_state_calls_panels(self, wx_app, config_mock):
        parent = wx.Frame(None)
        dialog = ConfigDialog(config_mock, parent)
        mock_panel = MagicMock(spec=ConfigSectionPanel)
        dialog._panels = [mock_panel, mock_panel]

        dialog._save_runtime_state()
        assert mock_panel._save_runtime_state.call_count == 2
        parent.Destroy()
        dialog.Destroy()

    def test_constructor_creates_panels(self, wx_app):
        parent = wx.Frame(None)
        opt = ConfigOptionDefinition('o', 'O', str, 'desc', default_value='x')
        sec = ConfigSectionDefinition('s', 'S')
        sec.option_definitions['o'] = opt
        cfg = MagicMock(spec=Config)
        cfg.CONFIG_SECTION_DEFINITIONS = {'s': sec}
        cfg.get_section.return_value = MagicMock()
        cfg.config_sections = {'s': MagicMock()}

        dialog = ConfigDialog(cfg, parent)
        assert len(dialog._panels) == 1
        assert dialog._panels[0].config_section_definition is sec
        parent.Destroy()
        dialog.Destroy()
