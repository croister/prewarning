# -*- coding: utf-8 -*-

import logging
from configparser import SectionProxy
from pathlib import Path
from typing import Any, Dict, List, cast

import wx
import wx.lib.scrolledpanel

from utils.config import Config
from utils.config_definitions import ConfigSectionDefinition, ConfigOptionDefinition, SelectionError, SelectionType, \
    SelectionResult, VerificationResult, SelectionData, RuntimeStateOptionDefinition


def _default_value(option_definition: ConfigOptionDefinition):
    default_value = option_definition.default_value
    if option_definition.value_type is bool:
        value = default_value
    else:
        value = str(default_value)
    return value


def _value(option_definition: ConfigOptionDefinition, config_section: SectionProxy):
    if option_definition.value_type is bool:
        value = option_definition.get_value(config_section)
    else:
        value = option_definition.get_value_str(config_section)
    return value


def _has_default_value(option_definition: ConfigOptionDefinition, config_section: SectionProxy):
    value = _value(option_definition, config_section)
    default_value = _default_value(option_definition)
    return value == default_value


def _set_value(control: wx.TextEntry | wx.CheckBox | wx.ListBox, value: Any):
    if type(control) == wx.TextCtrl:
        control.ChangeValue(str(value))
    elif type(control) == wx.ComboBox:
        control.SetValue(value)
    elif type(control) == wx.ListBox:
        control.SetStringSelection(value)
    else:
        control.SetValue(value)


def _get_value(control: wx.TextEntry | wx.CheckBox | wx.ListBox) -> str | None:
    if type(control) == wx.ListBox:
        selection = control.GetSelection()
        if selection != wx.NOT_FOUND:
            return control.GetString(selection)
        return None
    else:
        return control.GetValue()


def _default_tooltip(function: str) -> str:
    if function == 'default':
        return 'Reset to the default value.'
    elif function == 'verify':
        return 'Test the value(s).'
    elif function == 'select':
        return 'Select a value.'
    else:
        logging.error('_default_tooltip: Invalid function "%s".', function)
        raise ValueError('_default_tooltip: Invalid function "{}".'.format(function))


class ConfigOptionValidator(wx.Validator):

    def __repr__(self) -> str:
        return f'ConfigOptionValidator({self.config_section_definition.name}, {self.config_option_definition.name})'

    def __str__(self) -> str:
        return repr(self)

    def __init__(self,
                 config_option_definition: ConfigOptionDefinition,
                 config_section_definition: ConfigSectionDefinition,
                 config: Config):
        wx.Validator.__init__(self)

        self.config_option_definition = config_option_definition
        self.config_section_definition = config_section_definition
        self.config = config

        self.config_section = self.config.get_section(self.config_section_definition.name)

    def Clone(self):
        return ConfigOptionValidator(self.config_option_definition, self.config_section_definition, self.config)

    def Validate(self, win):
        if not self.config_section_definition.is_enabled(self.config.config_sections):
            return True

        control = self.GetWindow()
        value = _get_value(control)

        validation_errors = self.config_option_definition.validate(value)

        if len(validation_errors) > 0:
            control.SetBackgroundColour(wx.Colour("pink"))
            control.SetToolTip('\n'.join(validation_errors))
            control.SetFocus()
            control.Refresh()
            control.GetParent().GetParent().ScrollChildIntoView(control.GetParent())
            return False
        else:
            control.SetBackgroundColour(wx.NullColour)
            control.SetToolTip(None)
            control.Refresh()
            return True

    def TransferToWindow(self):
        if isinstance(self.config_option_definition, RuntimeStateOptionDefinition):
            return True
        control = self.GetWindow()
        value = _value(self.config_option_definition, self.config_section)
        _set_value(control, value)
        return True

    def TransferFromWindow(self):
        control = self.GetWindow()
        value = _get_value(control)
        self.config_section[self.config_option_definition.name] = str(value)
        return True


class ConfigSectionPanel(wx.Panel):

    def __repr__(self) -> str:
        return f'ConfigSectionPanel({self.config_section_definition.name})'

    def __str__(self) -> str:
        return repr(self)

    def __init__(self, config_section_definition: ConfigSectionDefinition,
                 config_section: SectionProxy,
                 config: Config,
                 *args,
                 state_provider=None,
                 dialog=None,
                 **kwargs):
        wx.Panel.__init__(self, *args, **kwargs, name=config_section_definition.name)

        self.logger = logging.getLogger(self.__class__.__name__)

        self.config_section_definition = config_section_definition
        self.config_section = config_section
        self.config = config
        self.state_provider = state_provider
        self._dialog = dialog

        self.options_sizer = None

        self._tracking_controls: Dict[str, wx.Window] = {}
        self._tracking_dirty: Dict[str, bool] = {}
        self._destroyed = False

        self.Bind(wx.EVT_WINDOW_DESTROY, self._on_window_destroy)

        self._create_widgets()

        if self.state_provider is not None:
            for option_definition in self.config_section_definition.option_definitions.values():
                if isinstance(option_definition, RuntimeStateOptionDefinition):
                    control = self._tracking_controls.get(option_definition.name)
                    if control is not None:
                        value = self.state_provider.get_runtime_value(option_definition)
                        if value is not None:
                            _set_value(control, value)
                            self._tracking_dirty[option_definition.name] = False
            self.state_provider.register_tracking_listener(self._on_tracking_update)
        else:
            section_name = self.config_section_definition.name
            for option_definition in self.config_section_definition.option_definitions.values():
                if isinstance(option_definition, RuntimeStateOptionDefinition):
                    group = option_definition.runtime_state_group
                    control = self._tracking_controls.get(option_definition.name)
                    if control is not None:
                        value = group.get_value(section_name, option_definition)
                        if value is not None:
                            _set_value(control, value)
                            self._tracking_dirty[option_definition.name] = False

        self.logger.debug(self)

    def _on_window_destroy(self, event):
        self._destroyed = True
        if self.state_provider is not None:
            self.state_provider.unregister_tracking_listener(self._on_tracking_update)
        event.Skip()

    def _on_tracking_update(self, state: Dict[str, str]):
        if self._destroyed:
            return
        for option_name, value in state.items():
            if not self._tracking_dirty.get(option_name, True):
                control = self._tracking_controls.get(option_name)
                if control is not None:
                    try:
                        _set_value(control, value)
                    except RuntimeError:
                        self._destroyed = True
                        if self.state_provider is not None:
                            self.state_provider.unregister_tracking_listener(self._on_tracking_update)
                        return

    def _save_runtime_state(self):
        if self.state_provider is not None:
            for option_name, control in self._tracking_controls.items():
                if self._tracking_dirty.get(option_name, False):
                    option_definition = self.config_section_definition.option_definitions.get(option_name)
                    if option_definition is not None and isinstance(option_definition, RuntimeStateOptionDefinition):
                        value = _get_value(control)
                        self.state_provider.set_runtime_value(option_definition, value)
                        # Defer dirty clear so stale wx.CallAfter updates from
                        # before/ during save are processed first and skipped.
                        wx.CallAfter(lambda n=option_name: self._tracking_dirty.update({n: False}))
        else:
            section_name = self.config_section_definition.name
            for option_name, control in self._tracking_controls.items():
                if self._tracking_dirty.get(option_name, False):
                    option_definition = self.config_section_definition.option_definitions.get(option_name)
                    if option_definition is not None and isinstance(option_definition, RuntimeStateOptionDefinition):
                        group = option_definition.runtime_state_group
                        value = _get_value(control)
                        group.set_value(section_name, option_definition, value)
                        wx.CallAfter(lambda n=option_name: self._tracking_dirty.update({n: False}))

    def _create_widgets(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        self.options_sizer = wx.FlexGridSizer(rows=len(self.config_section_definition.option_definitions),
                                              cols=3,
                                              hgap=5,
                                              vgap=5)

        self.section_label = wx.StaticText(self, label=self.config_section_definition.display_name)
        self.section_label.SetFont(self.section_label.GetFont().Bold())
        if len(self.config_section_definition.requires) != 0:
            self.section_label.SetToolTip('Depends on: {}'.format(', '.join([req.display_name
                                                                             for req in
                                                                             self.config_section_definition.requires])))

        image_size = wx.Size(16, 16)
        image_reset_to_default = wx.ArtProvider.GetBitmapBundle(wx.ART_UNDO, client=wx.ART_TOOLBAR, size=image_size)
        image_test = wx.ArtProvider.GetBitmapBundle(wx.ART_TICK_MARK)
        image_select = wx.ArtProvider.GetBitmapBundle(wx.ART_FILE_OPEN, client=wx.ART_MENU, size=image_size)

        main_sizer.Add(self.section_label, 0, wx.ALL, 5)

        for option_definition_name in self.config_section_definition.option_definitions:
            option_definition = self.config_section_definition.option_definitions[option_definition_name]

            option_label = wx.StaticText(self,
                                         label=option_definition.display_name,
                                         name=self._label_name(option_definition.name))
            option_label.SetToolTip(option_definition.description)

            self.options_sizer.Add(option_label, 0, wx.ALL, 5)

            validator = ConfigOptionValidator(option_definition, self.config_section_definition, self.config)

            valid_values = option_definition.get_valid_values()
            if ConfigSectionPanel._use_combo_box_for(valid_values):
                option_input = wx.ComboBox(self,
                                           validator=validator,
                                           size=wx.DefaultSize,
                                           choices=[str(val) for val in valid_values],
                                           style=wx.CB_DROPDOWN | wx.CB_READONLY,
                                           name=option_definition_name)
                option_input.Bind(wx.EVT_COMBOBOX, self.on_combo_box_changed)
            else:
                if option_definition.value_type is str:
                    option_input = wx.TextCtrl(self,
                                               validator=validator,
                                               name=option_definition_name)
                    option_input.Bind(wx.EVT_TEXT, self.on_text_ctrl_changed)
                elif option_definition.value_type is int:
                    option_input = wx.TextCtrl(self,
                                               validator=validator,
                                               name=option_definition_name)
                    option_input.Bind(wx.EVT_TEXT, self.on_text_ctrl_changed)
                elif option_definition.value_type is float:
                    option_input = wx.TextCtrl(self,
                                               validator=validator,
                                               name=option_definition_name)
                    option_input.Bind(wx.EVT_TEXT, self.on_text_ctrl_changed)
                elif option_definition.value_type is bool:
                    option_input = wx.CheckBox(self,
                                               validator=validator,
                                               name=option_definition_name)
                    option_input.Bind(wx.EVT_CHECKBOX, self.on_check_box_changed)
                elif option_definition.value_type is Path:
                    option_input = wx.TextCtrl(self,
                                               validator=validator,
                                               name=option_definition_name)
                    option_input.Bind(wx.EVT_TEXT, self.on_text_ctrl_changed)
                else:
                    self.logger.error(
                        'Unknown value type "%s" for the configuration option %s.',
                        str(option_definition.value_type),
                        option_definition_name)
                    raise ValueError(
                        'Unknown value type "{}" for the configuration option {}.'.format(
                            str(option_definition.value_type), option_definition_name))

            self.options_sizer.Add(option_input, 1, wx.ALL | wx.EXPAND, 5)

            if isinstance(option_definition, RuntimeStateOptionDefinition):
                self._tracking_controls[option_definition_name] = option_input
                self._tracking_dirty[option_definition_name] = False

            if not option_definition.is_enabled(self.config_section):
                option_input.Disable()

            option_buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
            if option_definition.default_value is not None:
                option_default_button = wx.BitmapButton(self,
                                                        bitmap=image_reset_to_default,
                                                        name=self._default_button_name(option_definition.name))
                option_default_button.SetToolTip(_default_tooltip('default'))
                option_default_button.Bind(wx.EVT_BUTTON, self.on_button)

                option_buttons_sizer.Add(option_default_button)

                if not option_definition.is_enabled(self.config_section) \
                        or (not isinstance(option_definition, RuntimeStateOptionDefinition)
                            and _has_default_value(option_definition, self.config_section)):
                    option_default_button.Disable()
            if option_definition.selector is not None or ConfigSectionPanel._use_selector_for(valid_values):
                option_select_button = wx.BitmapButton(self,
                                                       bitmap=image_select,
                                                       name=self._select_button_name(option_definition.name))
                option_select_button.SetToolTip(_default_tooltip('select'))
                option_select_button.Bind(wx.EVT_BUTTON, self.on_button)

                option_buttons_sizer.Add(option_select_button)

                if not option_definition.is_enabled(self.config_section):
                    option_select_button.Disable()
            if option_definition.verifier is not None:
                option_verify_button = wx.BitmapButton(self,
                                                       bitmap=image_test,
                                                       name=self._verify_button_name(option_definition.name))
                option_verify_button.SetToolTip(_default_tooltip('verify'))
                option_verify_button.Bind(wx.EVT_BUTTON, self.on_button)

                option_buttons_sizer.Add(option_verify_button)

                if not option_definition.is_enabled(self.config_section):
                    option_verify_button.Disable()

            self.options_sizer.Add(option_buttons_sizer, 0, wx.TOP | wx.BOTTOM, 5)

        self.options_sizer.AddGrowableCol(0, 1)
        self.options_sizer.AddGrowableCol(1, 2)

        if len(self.GetChildren()) == 1:
            option_label = wx.StaticText(self, label='No options available.')

            main_sizer.Add(option_label, 0, wx.ALL, 5)
        else:
            main_sizer.Add(self.options_sizer, 0, wx.EXPAND)

        self.SetSizer(main_sizer)

        self.logger.debug(self)

    @staticmethod
    def _label_name(option_name: str) -> str:
        return '{}_label_name'.format(option_name)

    @staticmethod
    def _default_button_name(option_name: str) -> str:
        return '{}_default_button_name'.format(option_name)

    @staticmethod
    def _verify_button_name(option_name: str) -> str:
        return '{}_verify_button_name'.format(option_name)

    @staticmethod
    def _select_button_name(option_name: str) -> str:
        return '{}_select_button_name'.format(option_name)

    @staticmethod
    def _too_large_for_combo_box(valid_values: List[Any]) -> bool:
        return len(valid_values) > 20

    @staticmethod
    def _use_combo_box_for(valid_values: List[Any]) -> bool:
        return valid_values is not None and not ConfigSectionPanel._too_large_for_combo_box(valid_values)

    @staticmethod
    def _use_selector_for(valid_values: List[Any]) -> bool:
        return valid_values is not None and ConfigSectionPanel._too_large_for_combo_box(valid_values)

    def update(self, validate=True):
        self.update_visibility()
        if self._dialog is not None:
            self._dialog.update_visibility()
            if validate:
                self._dialog.Validate()

    def update_visibility(self):
        self.TransferDataFromWindow()

        for config_option_definition_name in self.config_section_definition.option_definitions:
            config_option_definition = self.config_section_definition.option_definitions[config_option_definition_name]

            option_label = wx.FindWindowByName(self._label_name(config_option_definition_name), parent=self)
            if option_label is None:
                self.logger.error('Unable to find the %s label.', config_option_definition_name)
                raise ValueError('Unable to find the {} label.'.format(config_option_definition_name))

            option_input = wx.FindWindowByName(config_option_definition_name, parent=self)
            if option_input is None:
                self.logger.error('Unable to find the %s input.', config_option_definition_name)
                raise ValueError('Unable to find the {} input.'.format(config_option_definition_name))

            option_default_button = wx.FindWindowByName(self._default_button_name(config_option_definition_name),
                                                        parent=self)

            option_verify_button = wx.FindWindowByName(self._verify_button_name(config_option_definition_name),
                                                       parent=self)

            option_select_button = wx.FindWindowByName(self._select_button_name(config_option_definition_name),
                                                       parent=self)

            if config_option_definition.is_enabled(self.config_section):
                option_input.Enable()
                if option_default_button is not None:
                    if isinstance(config_option_definition, RuntimeStateOptionDefinition):
                        option_default_button.Enable()
                    elif _has_default_value(config_option_definition, self.config_section):
                        option_default_button.Disable()
                    else:
                        option_default_button.Enable()
                if option_verify_button is not None:
                    option_verify_button.Enable()
                if option_select_button is not None:
                    option_select_button.Enable()
            else:
                option_input.Disable()
                if option_default_button is not None:
                    option_default_button.Disable()
                if option_verify_button is not None:
                    option_verify_button.Disable()
                if option_select_button is not None:
                    option_select_button.Disable()

    def _mark_dirty_if_tracking(self, event: wx.CommandEvent):
        control = event.GetEventObject()
        option_name = control.GetName()
        if option_name in self._tracking_controls:
            self._tracking_dirty[option_name] = True

    def on_combo_box_changed(self, event: wx.CommandEvent):
        self.logger.debug('on_combo_box_changed: %s', event)
        self._mark_dirty_if_tracking(event)
        self.update()

    def on_list_box_changed(self, event: wx.CommandEvent):
        self.logger.debug('on_list_box_changed: %s', event)
        self._mark_dirty_if_tracking(event)
        self.update()

    def on_text_ctrl_changed(self, event: wx.CommandEvent):
        self.logger.debug('on_text_ctrl_changed: %s', event)
        self._mark_dirty_if_tracking(event)
        self.update(validate=False)

    def on_check_box_changed(self, event: wx.CommandEvent):
        self.logger.debug('on_check_box_changed: %s', event)
        self._mark_dirty_if_tracking(event)
        self.update()

    def on_button(self, event: wx.CommandEvent):
        if self._dialog is not None:
            self._dialog.TransferDataFromWindow()

        button = event.GetEventObject()
        if isinstance(button, wx.Button):
            (name, function) = button.GetName().split('_')[0:2]
            option_definition = self.config_section_definition.option_definitions[name]

            if function == 'default':
                default_value = _default_value(option_definition)

                option_input = wx.FindWindowByName(name, parent=self)
                if option_input is None:
                    self.logger.error('Unable to find the %s input.', name)
                    raise ValueError('Unable to find the {} input.'.format(name))

                _set_value(option_input, default_value)
                if name in self._tracking_controls:
                    self._tracking_dirty[name] = True
                    for opt_def in self.config_section_definition.option_definitions.values():
                        if isinstance(opt_def, RuntimeStateOptionDefinition):
                            ctrl = self._tracking_controls.get(opt_def.name)
                            if ctrl is not None:
                                _set_value(ctrl, _default_value(opt_def))
                                self._tracking_dirty[opt_def.name] = True
                option_input.SetFocus()

                self.update()

            elif function == 'verify':
                result = option_definition.verifier.verify()

                self.update()

                if not result:
                    button.SetBackgroundColour(wx.Colour('pink'))
                    button.SetToolTip(result.message)
                    button.SetFocus()
                    button.Refresh()
                else:
                    message = 'Success'
                    if isinstance(result, VerificationResult):
                        if result.message is not None:
                            message = f'Success: {result.message}'
                    button.SetBackgroundColour(wx.GREEN)
                    button.SetToolTip(message)
                    button.Refresh()

            elif function == 'select':
                valid_values = option_definition.get_valid_values()
                if option_definition.selector is not None:
                    result = option_definition.selector.select(parent=self.GetParent())
                elif ConfigSectionPanel._use_selector_for(valid_values):
                    result = SelectionResult(caption='Valid Values',
                                             message='Select a Value:')
                    for value in valid_values:
                        result.add_value(SelectionData(value, value))
                else:
                    self.logger.error('Unknown select method.')
                    raise ValueError('Unknown select method.')

                if result is not None:
                    if type(result) == SelectionError:
                        button.SetBackgroundColour(wx.Colour('pink'))
                        button.SetToolTip(result.message)
                        button.SetFocus()
                        button.Refresh()

                    elif type(result) == SelectionResult:
                        option_input = wx.FindWindowByName(name, parent=self)
                        if option_input is None:
                            self.logger.error('Unable to find the %s input.', name)
                            raise ValueError('Unable to find the {} input.'.format(name))

                        selected = None

                        if len(result.values) > 1:
                            old_value = str(option_definition.get_value(self.config.get_section(
                                self.config_section_definition.name)))
                            new_values = [str(s.value) for s in result.values]

                            value_dict = {str(r.display_name): r for r in result.values}
                            value_list = list(value_dict.keys())

                            if result.selection_type == SelectionType.SINGLE:
                                old_selected = 0
                                if old_value is not None and old_value in new_values:
                                    old_selected = new_values.index(old_value)

                                with wx.SingleChoiceDialog(self.GetParent(),
                                                           'Select a value',
                                                           'Values',
                                                           value_list) as dialog:
                                    dialog.SetSelection(old_selected)

                                    if dialog.ShowModal() == wx.ID_OK:
                                        self.logger.debug('You selected: "%s"', dialog.GetStringSelection())
                                        selected = [value_dict[dialog.GetStringSelection()]]

                            elif result.selection_type == SelectionType.MULTIPLE:
                                old_selected = []
                                if old_value is not None:
                                    old_values = old_value.split()
                                    for old_val in old_values:
                                        if old_val in new_values:
                                            old_selected.append(new_values.index(old_val))

                                with wx.MultiChoiceDialog(self.GetParent(),
                                                          'Select value(s)',
                                                          'Values',
                                                          value_list) as dialog:
                                    dialog.SetSelections(old_selected)

                                    if dialog.ShowModal() == wx.ID_OK:
                                        selections = dialog.GetSelections()
                                        selected = [value_dict[value_list[x]] for x in selections]
                                        self.logger.debug('You selected: "%s"', selected)

                        elif len(result.values) == 1:
                            selected = result.values

                        if selected is not None:
                            value = ' '.join([str(s.value) for s in selected])

                            _set_value(option_input, value)
                            if name in self._tracking_controls:
                                self._tracking_dirty[name] = True

                            self.update()

                            button.SetBackgroundColour(wx.GREEN)
                            button.SetToolTip('Success')
                            button.Refresh()
                        else:
                            self.update()

    def Validate(self) -> bool:
        for child in self.GetChildren():
            if isinstance(child, wx.Button) and '_button_name' in child.GetName():
                (name, function) = child.GetName().split('_')[0:2]
                child.SetBackgroundColour(wx.NullColour)
                child.SetToolTip(_default_tooltip(function))
        return super(ConfigSectionPanel, self).Validate()


class ConfigDialog(wx.Dialog):

    def __repr__(self) -> str:
        return f'ConfigDialog({self.config})'

    def __str__(self) -> str:
        return repr(self)

    def __init__(self, config: Config, *args, state_providers: Dict[str, Any] | None = None, **kwargs):
        wx.Dialog.__init__(self, *args, **kwargs, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        self.logger = logging.getLogger(self.__class__.__name__)

        self.config = config
        self.state_providers = state_providers if state_providers is not None else {}

        self.sections_sizer = None
        self._panels = []

        self.SetMinSize(self.GetParent().GetMinSize())
        self.SetSize(self.GetParent().GetMinSize())

        icon = wx.Icon()
        icon.CopyFromBitmap(wx.ArtProvider.GetBitmap(wx.ART_EXECUTABLE_FILE,
                                                      client=wx.ART_FRAME_ICON,
                                                      size=wx.Size(16, 16)))
        self.SetIcon(icon)

        self._create_widgets()

        self.logger.debug(self)

    def _create_widgets(self):
        scroll_panel = wx.lib.scrolledpanel.ScrolledPanel(self)

        button_sizer = wx.StdDialogButtonSizer()
        self.sections_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        for config_section_definition_name in self.config.CONFIG_SECTION_DEFINITIONS:
            config_section_definition = self.config.CONFIG_SECTION_DEFINITIONS[config_section_definition_name]

            state_provider = self.state_providers.get(config_section_definition_name)
            config_section_panel = ConfigSectionPanel(config_section_definition,
                                                       self.config.get_section(config_section_definition_name),
                                                       self.config,
                                                       scroll_panel,
                                                       state_provider=state_provider,
                                                       dialog=self)

            self.sections_sizer.Add(config_section_panel, proportion=0, flag=wx.EXPAND | wx.ALL, border=5)
            self._panels.append(config_section_panel)

            if not config_section_definition.is_enabled(self.config.config_sections) \
                    or len(config_section_panel.GetChildren()) == 1:
                self.sections_sizer.Show(config_section_panel, False)

        self.button_ok = wx.Button(self, label="OK")
        self.button_ok.Bind(wx.EVT_BUTTON, self.on_ok)
        button_sizer.Add(self.button_ok)

        self.button_save = wx.Button(self, label="Save")
        self.button_save.Bind(wx.EVT_BUTTON, self.on_save)
        button_sizer.Add(self.button_save)

        self.button_cancel = wx.Button(self, label="Cancel")
        self.button_cancel.Bind(wx.EVT_BUTTON, self.on_cancel)
        button_sizer.Add(self.button_cancel)
        button_sizer.Realize()

        scroll_panel.SetSizer(self.sections_sizer)
        scroll_panel.SetupScrolling()

        main_sizer.Add(scroll_panel, proportion=1, flag=wx.EXPAND)

        main_sizer.Add(button_sizer, proportion=0, flag=wx.ALL | wx.ALIGN_RIGHT, border=5)

        self.SetSizer(main_sizer)
        self.Fit()

    def update_visibility(self):
        self.TransferDataFromWindow()

        for config_section_definition_name in self.config.CONFIG_SECTION_DEFINITIONS:
            config_section_definition = self.config.CONFIG_SECTION_DEFINITIONS[config_section_definition_name]

            config_section_panel = wx.FindWindowByName(config_section_definition_name, parent=self)
            if config_section_panel is None:
                self.logger.error('Unable to find the %s panel.', config_section_definition_name)
                raise ValueError('Unable to find the {} panel.'.format(config_section_definition_name))

            if not config_section_definition.is_enabled(self.config.config_sections) \
                    or len(config_section_panel.GetChildren()) == 1:
                self.sections_sizer.Show(config_section_panel, False)
            else:
                self.sections_sizer.Show(config_section_panel, True)

        self.Layout()
        self.Fit()

    def on_ok(self, e):
        self.logger.debug('on_ok: %s', e)

        self.TransferDataFromWindow()

        if self.Validate():
            self.config.write()
            self._save_runtime_state()

            if self.IsModal():
                self.EndModal(wx.ID_OK)
            else:
                self.SetReturnCode(wx.ID_OK)
                self.Show(False)

    def on_save(self, e):
        self.logger.debug('on_save: %s', e)

        self.TransferDataFromWindow()

        if self.Validate():
            self.config.write()
            self._save_runtime_state()

    def _save_runtime_state(self):
        for panel in self._panels:
            panel._save_runtime_state()

    def on_cancel(self, e):
        self.logger.debug('on_cancel: %s', e)

        self.EndModal(wx.ID_CANCEL)
