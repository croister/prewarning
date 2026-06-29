# -*- coding: utf-8 -*-

import logging
import threading
from configparser import SectionProxy
from pathlib import Path
from typing import Any, Dict, List

import wx
import wx.lib.scrolledpanel

from utils.config import Config
from utils.config_definitions import (
    ConfigSectionDefinition,
    ConfigOptionDefinition,
    SelectionError,
    SelectionType,
    SelectionResult,
    VerificationError,
    VerificationResult,
    SelectionData,
    RuntimeStateOptionDefinition,
)
from utils.i18n import _, N_


def _default_value(option_definition: ConfigOptionDefinition):
    default_value = option_definition.default_value
    if option_definition.value_type is bool:
        value = default_value
    else:
        value = str(default_value)
    return value


UI_BORDER = 5
OPTIONS_GRID_COLS = 3
OPTIONS_GRID_GAP = 5
DEFAULT_ICON_SIZE = 16

LABEL_NAME_FMT = "{}_label_name"
DEFAULT_BUTTON_NAME_FMT = "{}_default_button_name"
VERIFY_BUTTON_NAME_FMT = "{}_verify_button_name"
SELECT_BUTTON_NAME_FMT = "{}_select_button_name"
ERR_UNKNOWN_VALUE_TYPE = 'Unknown value type "{}" for the configuration option {}.'
ERR_LABEL_NOT_FOUND = "Unable to find the {} label."
ERR_INPUT_NOT_FOUND = "Unable to find the {} input."
ERR_PANEL_NOT_FOUND = "Unable to find the {} panel."
MSG_VERIFY_FAILED = N_("Verification failed.")
MSG_SUCCESS = N_("Success")
MSG_SUCCESS_FMT = N_("Success: {}")
DLG_VALID_VALUES_CAPTION = N_("Valid Values")
DLG_SELECT_VALUE_LABEL = N_("Select a Value:")
DLG_VALUES = N_("Values")
DLG_SELECT_VALUES = N_("Select value(s)")
ERR_UNKNOWN_SELECT_METHOD = "Unknown select method."
MSG_NO_OPTIONS_AVAILABLE = N_("No options available.")
TOOLTIP_DEPENDS_ON = N_("Depends on: {}")
FILTER_HINT = N_("Type to filter...")
DLG_INITIAL_WIDTH = 400
DLG_INITIAL_HEIGHT = 500
DLG_MIN_WIDTH = 300
DLG_MIN_HEIGHT = 300


def _value(option_definition: ConfigOptionDefinition, config_section: SectionProxy):
    if option_definition.value_type is bool:
        value = option_definition.get_value(config_section)
    else:
        value = option_definition.get_value_str(config_section)
    return value


def _has_default_value(
    option_definition: ConfigOptionDefinition, config_section: SectionProxy
):
    value = _value(option_definition, config_section)
    default_value = _default_value(option_definition)
    return value == default_value


def _set_value(control: wx.TextEntry | wx.CheckBox | wx.ListBox, value: Any):
    if isinstance(control, wx.TextCtrl):
        control.ChangeValue(str(value))
    elif isinstance(control, wx.ComboBox):
        control.SetValue(value)
    elif isinstance(control, wx.ListBox):
        control.SetStringSelection(value)
    else:
        control.SetValue(value)


def _get_value(control: wx.TextEntry | wx.CheckBox | wx.ListBox) -> str | None:
    if isinstance(control, wx.ListBox):
        selection = control.GetSelection()
        if selection != wx.NOT_FOUND:
            return control.GetString(selection)
        return None
    else:
        return control.GetValue()


TOOLTIP_DEFAULT = N_("Reset to the default value.")
TOOLTIP_VERIFY = N_("Test the value(s).")
TOOLTIP_SELECT = N_("Select a value.")
TOOLTIP_ERR_INVALID_FUNCTION = '_default_tooltip: Invalid function "{}".'
TOOLTIP_WORKING = N_("Working...")


def _default_tooltip(function: str) -> str:
    if function == "default":
        return _(TOOLTIP_DEFAULT)
    elif function == "verify":
        return _(TOOLTIP_VERIFY)
    elif function == "select":
        return _(TOOLTIP_SELECT)
    else:
        logging.error('_default_tooltip: Invalid function "%s".', function)
        raise ValueError(TOOLTIP_ERR_INVALID_FUNCTION.format(function))


class ConfigOptionValidator(wx.Validator):
    def __repr__(self) -> str:
        return f"ConfigOptionValidator({self.config_section_definition.name}, {self.config_option_definition.name})"

    def __str__(self) -> str:
        return repr(self)

    def __init__(
        self,
        config_option_definition: ConfigOptionDefinition,
        config_section_definition: ConfigSectionDefinition,
        config: Config,
    ):
        wx.Validator.__init__(self)

        self.config_option_definition = config_option_definition
        self.config_section_definition = config_section_definition
        self.config = config

        self.config_section = self.config.get_section(
            self.config_section_definition.name
        )

    def Clone(self):
        return ConfigOptionValidator(
            self.config_option_definition, self.config_section_definition, self.config
        )

    def Validate(self, win):
        if not self.config_section_definition.is_enabled(self.config.config_sections):
            return True

        control = self.GetWindow()
        value = _get_value(control)

        validation_errors = self.config_option_definition.validate(value)

        if len(validation_errors) > 0:
            control.SetBackgroundColour(wx.Colour("pink"))
            control.SetToolTip("\n".join(validation_errors))
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


class FilterableChoiceDialog(wx.Dialog):
    """A dialog with a filter text field and a listbox for single selection."""

    def __init__(
        self,
        parent: wx.Window,
        caption: str,
        message: str,
        choices: list[str],
        initial_selection: int = 0,
    ):
        wx.Dialog.__init__(
            self,
            parent,
            title=caption,
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._all_choices = list(choices)
        self._filtered_choices = list(choices)

        sizer = wx.BoxSizer(wx.VERTICAL)

        label = wx.StaticText(self, label=message)
        sizer.Add(label, 0, wx.ALL, UI_BORDER)

        self._filter_ctrl = wx.TextCtrl(self)
        self._filter_ctrl.SetHint(_(FILTER_HINT))
        self._filter_ctrl.Bind(wx.EVT_TEXT, self._on_filter)
        sizer.Add(self._filter_ctrl, 0, wx.ALL | wx.EXPAND, UI_BORDER)

        self._listbox = wx.ListBox(
            self, choices=self._filtered_choices, style=wx.LB_SINGLE
        )
        if self._filtered_choices:
            if 0 <= initial_selection < len(self._filtered_choices):
                self._listbox.SetSelection(initial_selection)
            else:
                self._listbox.SetSelection(0)
        self._listbox.Bind(wx.EVT_LISTBOX_DCLICK, self._on_dclick)
        sizer.Add(self._listbox, 1, wx.ALL | wx.EXPAND, UI_BORDER)

        btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        sizer.Add(btn_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, UI_BORDER)

        self.SetSizer(sizer)
        self.SetInitialSize(wx.Size(DLG_INITIAL_WIDTH, DLG_INITIAL_HEIGHT))
        self.SetMinSize(wx.Size(DLG_MIN_WIDTH, DLG_MIN_HEIGHT))

    def _on_filter(self, event) -> None:
        text = self._filter_ctrl.GetValue().lower()
        if not text:
            self._filtered_choices = list(self._all_choices)
        else:
            self._filtered_choices = [c for c in self._all_choices if text in c.lower()]
        self._listbox.Clear()
        self._listbox.AppendItems(self._filtered_choices)
        if self._filtered_choices:
            self._listbox.SetSelection(0)

    def _on_dclick(self, event) -> None:
        self.EndModal(wx.ID_OK)

    def GetStringSelection(self) -> str:
        return self._listbox.GetStringSelection()

    def SetSelection(self, index: int) -> None:
        if 0 <= index < self._listbox.GetCount():
            self._listbox.SetSelection(index)


class ConfigSectionPanel(wx.Panel):
    def __repr__(self) -> str:
        return f"ConfigSectionPanel({self.config_section_definition.name})"

    def __str__(self) -> str:
        return repr(self)

    def __init__(
        self,
        config_section_definition: ConfigSectionDefinition,
        config_section: SectionProxy,
        config: Config,
        *args,
        state_provider=None,
        dialog=None,
        **kwargs,
    ):
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
            for (
                option_definition
            ) in self.config_section_definition.option_definitions.values():
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
            for (
                option_definition
            ) in self.config_section_definition.option_definitions.values():
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
                            self.state_provider.unregister_tracking_listener(
                                self._on_tracking_update
                            )
                        return

    def _save_runtime_state(self):
        if self.state_provider is not None:
            for option_name, control in self._tracking_controls.items():
                if self._tracking_dirty.get(option_name, False):
                    option_definition = (
                        self.config_section_definition.option_definitions.get(
                            option_name
                        )
                    )
                    if option_definition is not None and isinstance(
                        option_definition, RuntimeStateOptionDefinition
                    ):
                        value = _get_value(control)
                        self.state_provider.set_runtime_value(option_definition, value)
                        # Defer dirty clear so stale wx.CallAfter updates from
                        # before/ during save are processed first and skipped.
                        wx.CallAfter(
                            lambda n=option_name: self._tracking_dirty.update(
                                {n: False}
                            )
                        )
        else:
            section_name = self.config_section_definition.name
            for option_name, control in self._tracking_controls.items():
                if self._tracking_dirty.get(option_name, False):
                    option_definition = (
                        self.config_section_definition.option_definitions.get(
                            option_name
                        )
                    )
                    if option_definition is not None and isinstance(
                        option_definition, RuntimeStateOptionDefinition
                    ):
                        group = option_definition.runtime_state_group
                        value = _get_value(control)
                        group.set_value(section_name, option_definition, value)
                        wx.CallAfter(
                            lambda n=option_name: self._tracking_dirty.update(
                                {n: False}
                            )
                        )

    def _create_widgets(self) -> None:
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        self.options_sizer = wx.FlexGridSizer(
            rows=len(self.config_section_definition.option_definitions),
            cols=OPTIONS_GRID_COLS,
            hgap=OPTIONS_GRID_GAP,
            vgap=OPTIONS_GRID_GAP,
        )
        assert self.options_sizer is not None

        self.section_label = wx.StaticText(
            self, label=_(self.config_section_definition.display_name)
        )
        self.section_label.SetFont(self.section_label.GetFont().Bold())
        if len(self.config_section_definition.requires) != 0:
            self.section_label.SetToolTip(
                _(TOOLTIP_DEPENDS_ON).format(
                    ", ".join(
                        [
                            _(req.display_name)
                            for req in self.config_section_definition.requires
                        ]
                    )
                )
            )

        image_size = wx.Size(DEFAULT_ICON_SIZE, DEFAULT_ICON_SIZE)
        image_reset_to_default = wx.ArtProvider.GetBitmapBundle(
            wx.ART_UNDO, client=wx.ART_TOOLBAR, size=image_size
        )
        image_test = wx.ArtProvider.GetBitmapBundle(wx.ART_TICK_MARK)
        image_select = wx.ArtProvider.GetBitmapBundle(
            wx.ART_FILE_OPEN, client=wx.ART_MENU, size=image_size
        )

        main_sizer.Add(self.section_label, 0, wx.ALL, UI_BORDER)

        for option_definition_name in self.config_section_definition.option_definitions:
            option_definition = self.config_section_definition.option_definitions[
                option_definition_name
            ]

            option_label = wx.StaticText(
                self,
                label=_(option_definition.display_name),
                name=self._label_name(option_definition.name),
            )
            description = _(option_definition.description)
            if option_definition.description_format_args:
                description = description.format(
                    **option_definition.description_format_args
                )
            option_label.SetToolTip(description)

            self.options_sizer.Add(option_label, 0, wx.ALL, UI_BORDER)

            validator = ConfigOptionValidator(
                option_definition, self.config_section_definition, self.config
            )

            valid_values = option_definition.get_valid_values()
            if ConfigSectionPanel._use_combo_box_for(valid_values):
                option_input = wx.ComboBox(
                    self,
                    validator=validator,
                    size=wx.DefaultSize,
                    choices=[str(val) for val in valid_values],
                    style=wx.CB_DROPDOWN | wx.CB_READONLY,
                    name=option_definition_name,
                )
                option_input.Bind(wx.EVT_COMBOBOX, self.on_combo_box_changed)
            else:
                text_ctrl_style = 0
                if (
                    option_definition.selector is not None
                    or ConfigSectionPanel._use_selector_for(valid_values)
                    or option_definition.read_only
                ):
                    text_ctrl_style |= wx.TE_READONLY
                if option_definition.value_type is str:
                    option_input = wx.TextCtrl(
                        self,
                        validator=validator,
                        name=option_definition_name,
                        style=text_ctrl_style,
                    )
                    option_input.Bind(wx.EVT_TEXT, self.on_text_ctrl_changed)
                elif option_definition.value_type is int:
                    option_input = wx.TextCtrl(
                        self,
                        validator=validator,
                        name=option_definition_name,
                        style=text_ctrl_style,
                    )
                    option_input.Bind(wx.EVT_TEXT, self.on_text_ctrl_changed)
                elif option_definition.value_type is float:
                    option_input = wx.TextCtrl(
                        self,
                        validator=validator,
                        name=option_definition_name,
                        style=text_ctrl_style,
                    )
                    option_input.Bind(wx.EVT_TEXT, self.on_text_ctrl_changed)
                elif option_definition.value_type is bool:
                    option_input = wx.CheckBox(
                        self, validator=validator, name=option_definition_name
                    )
                    option_input.Bind(wx.EVT_CHECKBOX, self.on_check_box_changed)
                elif option_definition.value_type is Path:
                    option_input = wx.TextCtrl(
                        self,
                        validator=validator,
                        name=option_definition_name,
                        style=text_ctrl_style,
                    )
                    option_input.Bind(wx.EVT_TEXT, self.on_text_ctrl_changed)
                else:
                    self.logger.error(
                        'Unknown value type "%s" for the configuration option %s.',
                        str(option_definition.value_type),
                        option_definition_name,
                    )
                    raise ValueError(
                        ERR_UNKNOWN_VALUE_TYPE.format(
                            str(option_definition.value_type), option_definition_name
                        )
                    )

            self.options_sizer.Add(option_input, 1, wx.ALL | wx.EXPAND, UI_BORDER)

            if isinstance(option_definition, RuntimeStateOptionDefinition):
                self._tracking_controls[option_definition_name] = option_input
                self._tracking_dirty[option_definition_name] = False

            if not option_definition.is_enabled(self.config_section):
                option_input.Disable()

            option_buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
            if option_definition.default_value is not None:
                option_default_button = wx.BitmapButton(
                    self,
                    bitmap=image_reset_to_default,
                    name=self._default_button_name(option_definition.name),
                )
                option_default_button.SetToolTip(_default_tooltip("default"))
                option_default_button.Bind(wx.EVT_BUTTON, self.on_button)

                option_buttons_sizer.Add(option_default_button)

                if not option_definition.is_enabled(self.config_section) or (
                    not isinstance(option_definition, RuntimeStateOptionDefinition)
                    and _has_default_value(option_definition, self.config_section)
                ):
                    option_default_button.Disable()
            if (
                option_definition.selector is not None
                or ConfigSectionPanel._use_selector_for(valid_values)
            ):
                option_select_button = wx.BitmapButton(
                    self,
                    bitmap=image_select,
                    name=self._select_button_name(option_definition.name),
                )
                option_select_button.SetToolTip(_default_tooltip("select"))
                option_select_button.Bind(wx.EVT_BUTTON, self.on_button)

                option_buttons_sizer.Add(option_select_button)

                if not option_definition.is_enabled(self.config_section):
                    option_select_button.Disable()
            if option_definition.verifier is not None:
                option_verify_button = wx.BitmapButton(
                    self,
                    bitmap=image_test,
                    name=self._verify_button_name(option_definition.name),
                )
                option_verify_button.SetToolTip(_default_tooltip("verify"))
                option_verify_button.Bind(wx.EVT_BUTTON, self.on_button)

                option_buttons_sizer.Add(option_verify_button)

                if not option_definition.is_enabled(self.config_section):
                    option_verify_button.Disable()

            self.options_sizer.Add(
                option_buttons_sizer, 0, wx.TOP | wx.BOTTOM, UI_BORDER
            )

        self.options_sizer.AddGrowableCol(0, 1)
        self.options_sizer.AddGrowableCol(1, 2)

        if len(self.GetChildren()) == 1:
            option_label = wx.StaticText(self, label=_(MSG_NO_OPTIONS_AVAILABLE))

            main_sizer.Add(option_label, 0, wx.ALL, UI_BORDER)
        else:
            main_sizer.Add(self.options_sizer, 0, wx.EXPAND)

        self.SetSizer(main_sizer)

        self.logger.debug(self)

    @staticmethod
    def _label_name(option_name: str) -> str:
        return LABEL_NAME_FMT.format(option_name)

    @staticmethod
    def _default_button_name(option_name: str) -> str:
        return DEFAULT_BUTTON_NAME_FMT.format(option_name)

    @staticmethod
    def _verify_button_name(option_name: str) -> str:
        return VERIFY_BUTTON_NAME_FMT.format(option_name)

    @staticmethod
    def _select_button_name(option_name: str) -> str:
        return SELECT_BUTTON_NAME_FMT.format(option_name)

    @staticmethod
    def _too_large_for_combo_box(valid_values: List[Any]) -> bool:
        return len(valid_values) > 20

    @staticmethod
    def _use_combo_box_for(valid_values: List[Any] | None) -> bool:
        return (
            valid_values is not None
            and not ConfigSectionPanel._too_large_for_combo_box(valid_values)
        )

    @staticmethod
    def _use_selector_for(valid_values: List[Any] | None) -> bool:
        return valid_values is not None and ConfigSectionPanel._too_large_for_combo_box(
            valid_values
        )

    def update(self, validate=True):
        self.update_visibility()
        if self._dialog is not None:
            self._dialog.update_visibility()
            if validate:
                self._dialog.Validate()

    def update_visibility(self) -> None:
        self.TransferDataFromWindow()

        for (
            config_option_definition_name
        ) in self.config_section_definition.option_definitions:
            config_option_definition = (
                self.config_section_definition.option_definitions[
                    config_option_definition_name
                ]
            )

            option_label = wx.FindWindowByName(
                self._label_name(config_option_definition_name), parent=self
            )
            if option_label is None:
                self.logger.error(
                    "Unable to find the %s label.", config_option_definition_name
                )
                raise ValueError(
                    ERR_LABEL_NOT_FOUND.format(config_option_definition_name)
                )

            option_input = wx.FindWindowByName(
                config_option_definition_name, parent=self
            )
            if option_input is None:
                self.logger.error(
                    "Unable to find the %s input.", config_option_definition_name
                )
                raise ValueError(
                    ERR_INPUT_NOT_FOUND.format(config_option_definition_name)
                )

            option_default_button = wx.FindWindowByName(
                self._default_button_name(config_option_definition_name), parent=self
            )

            option_verify_button = wx.FindWindowByName(
                self._verify_button_name(config_option_definition_name), parent=self
            )

            option_select_button = wx.FindWindowByName(
                self._select_button_name(config_option_definition_name), parent=self
            )

            if config_option_definition.is_enabled(self.config_section):
                option_input.Enable()
                if option_default_button is not None:
                    if isinstance(
                        config_option_definition, RuntimeStateOptionDefinition
                    ):
                        option_default_button.Enable()
                    elif _has_default_value(
                        config_option_definition, self.config_section
                    ):
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
        self.logger.debug("on_combo_box_changed: %s", event)
        self._mark_dirty_if_tracking(event)
        self.update()

    def on_list_box_changed(self, event: wx.CommandEvent):
        self.logger.debug("on_list_box_changed: %s", event)
        self._mark_dirty_if_tracking(event)
        self.update()

    def on_text_ctrl_changed(self, event: wx.CommandEvent):
        self.logger.debug("on_text_ctrl_changed: %s", event)
        self._mark_dirty_if_tracking(event)
        self.update(validate=False)

    def on_check_box_changed(self, event: wx.CommandEvent):
        self.logger.debug("on_check_box_changed: %s", event)
        self._mark_dirty_if_tracking(event)
        self.update()

    def on_button(self, event: wx.CommandEvent):
        if self._dialog is not None:
            self._dialog.TransferDataFromWindow()

        button = event.GetEventObject()
        if isinstance(button, wx.Button):
            (name, function) = button.GetName().split("_")[0:2]
            option_definition = self.config_section_definition.option_definitions[name]

            if function == "default":
                default_value = _default_value(option_definition)

                option_input = wx.FindWindowByName(name, parent=self)
                if option_input is None:
                    self.logger.error("Unable to find the %s input.", name)
                    raise ValueError(ERR_INPUT_NOT_FOUND.format(name))

                _set_value(option_input, default_value)
                if name in self._tracking_controls:
                    self._tracking_dirty[name] = True
                    for (
                        opt_def
                    ) in self.config_section_definition.option_definitions.values():
                        if isinstance(opt_def, RuntimeStateOptionDefinition):
                            ctrl = self._tracking_controls.get(opt_def.name)
                            if ctrl is not None:
                                _set_value(ctrl, _default_value(opt_def))
                                self._tracking_dirty[opt_def.name] = True
                option_input.SetFocus()

                self.update()

            elif function == "verify":
                if option_definition.verifier is None:
                    return
                if getattr(button, "_working", False):
                    return
                verifier = option_definition.verifier
                button._working = True  # type: ignore[attr-defined]
                button.SetCursor(wx.Cursor(wx.CURSOR_WAIT))
                button.SetBackgroundColour(wx.NullColour)
                button.SetToolTip(_(TOOLTIP_WORKING))
                button.Refresh()

                def _do_verify():
                    result = verifier.verify()
                    wx.CallAfter(self._on_verify_done, button, result)

                threading.Thread(target=_do_verify, daemon=True).start()

            elif function == "select":
                valid_values = option_definition.get_valid_values()
                if valid_values is None:
                    valid_values = []
                if option_definition.selector is not None:
                    if getattr(button, "_working", False):
                        return
                    selector = option_definition.selector
                    button._working = True  # type: ignore[attr-defined]
                    button.SetCursor(wx.Cursor(wx.CURSOR_WAIT))
                    button.SetBackgroundColour(wx.NullColour)
                    button.SetToolTip(_(TOOLTIP_WORKING))
                    button.Refresh()

                    def _do_select():
                        select_result = selector.select(parent=self.GetParent())
                        wx.CallAfter(
                            self._on_select_done,
                            button,
                            name,
                            option_definition,
                            select_result,
                        )

                    threading.Thread(target=_do_select, daemon=True).start()
                elif ConfigSectionPanel._use_selector_for(valid_values):
                    select_result = SelectionResult(
                        caption=_(DLG_VALID_VALUES_CAPTION),
                        message=_(DLG_SELECT_VALUE_LABEL),
                    )
                    for value in valid_values:
                        select_result.add_value(SelectionData(value, value))
                    self._handle_select_result(
                        button, name, option_definition, select_result
                    )
                else:
                    self.logger.error(ERR_UNKNOWN_SELECT_METHOD)
                    raise ValueError(ERR_UNKNOWN_SELECT_METHOD)

    def _on_verify_done(self, button: wx.Button, result) -> None:
        if not button:
            return
        button._working = False  # type: ignore[attr-defined]
        button.SetCursor(wx.NullCursor)
        self.update()

        if not result:
            button.SetBackgroundColour(wx.Colour("pink"))
            if isinstance(result, VerificationError):
                button.SetToolTip(_(result.message))
            else:
                button.SetToolTip(_(MSG_VERIFY_FAILED))
            button.SetFocus()
            button.Refresh()
        else:
            message = _(MSG_SUCCESS)
            if isinstance(result, VerificationResult):
                if result.message is not None:
                    message = _(MSG_SUCCESS_FMT).format(result.message)
            button.SetBackgroundColour(wx.GREEN)
            button.SetToolTip(message)
            button.Refresh()

    def _on_select_done(
        self, button: wx.Button, name: str, option_definition, select_result
    ) -> None:
        if not button:
            return
        button._working = False  # type: ignore[attr-defined]
        button.SetCursor(wx.NullCursor)
        self._handle_select_result(button, name, option_definition, select_result)

    def _handle_select_result(
        self, button: wx.Button, name: str, option_definition, select_result
    ) -> None:
        if select_result is None:
            button.SetToolTip(_(TOOLTIP_SELECT))
            return

        if isinstance(select_result, SelectionError):
            button.SetBackgroundColour(wx.Colour("pink"))
            button.SetToolTip(_(select_result.message))
            button.SetFocus()
            button.Refresh()

        elif isinstance(select_result, SelectionResult):
            option_input = wx.FindWindowByName(name, parent=self)
            if option_input is None:
                self.logger.error("Unable to find the %s input.", name)
                raise ValueError(ERR_INPUT_NOT_FOUND.format(name))

            selected = None

            if len(select_result.values) > 1:
                old_value = str(
                    option_definition.get_value(
                        self.config.get_section(self.config_section_definition.name)
                    )
                )
                new_values = [str(s.value) for s in select_result.values]

                value_dict = {str(r.display_name): r for r in select_result.values}
                value_list = list(value_dict.keys())

                if select_result.selection_type == SelectionType.SINGLE:
                    old_selected: int = 0
                    if old_value is not None and old_value in new_values:
                        old_selected = new_values.index(old_value)

                    with FilterableChoiceDialog(
                        self.GetParent(),
                        caption=_(DLG_VALUES),
                        message=_(DLG_SELECT_VALUE_LABEL),
                        choices=value_list,
                        initial_selection=old_selected,
                    ) as dialog:
                        if dialog.ShowModal() == wx.ID_OK:
                            self.logger.debug(
                                'You selected: "%s"',
                                dialog.GetStringSelection(),
                            )
                            selected = [value_dict[dialog.GetStringSelection()]]

                elif select_result.selection_type == SelectionType.MULTIPLE:
                    multi_old_selected: list[int] = []
                    if old_value is not None:
                        old_values = old_value.split()
                        for old_val in old_values:
                            if old_val in new_values:
                                multi_old_selected.append(new_values.index(old_val))

                    with wx.MultiChoiceDialog(
                        self.GetParent(),
                        _(DLG_SELECT_VALUES),
                        _(DLG_VALUES),
                        value_list,
                    ) as dialog:
                        dialog.SetSelections(multi_old_selected)

                        if dialog.ShowModal() == wx.ID_OK:
                            selections = dialog.GetSelections()
                            selected = [value_dict[value_list[x]] for x in selections]
                            self.logger.debug('You selected: "%s"', selected)

            elif len(select_result.values) == 1:
                selected = select_result.values

            if selected is not None:
                value = " ".join([str(s.value) for s in selected])

                _set_value(option_input, value)
                if name in self._tracking_controls:
                    self._tracking_dirty[name] = True

                self.update()

                button.SetBackgroundColour(wx.GREEN)
                button.SetToolTip(_(MSG_SUCCESS))
                button.Refresh()
            else:
                button.SetToolTip(_(TOOLTIP_SELECT))
                self.update()

    def Validate(self) -> bool:
        for child in self.GetChildren():
            if isinstance(child, wx.Button) and "_button_name" in child.GetName():
                (name, function) = child.GetName().split("_")[0:2]
                child.SetBackgroundColour(wx.NullColour)
                child.SetToolTip(_default_tooltip(function))
        return super(ConfigSectionPanel, self).Validate()


class ConfigDialog(wx.Dialog):
    def __repr__(self) -> str:
        return f"ConfigDialog({self.config})"

    def __str__(self) -> str:
        return repr(self)

    def __init__(
        self,
        config: Config,
        *args,
        state_providers: Dict[str, Any] | None = None,
        **kwargs,
    ):
        wx.Dialog.__init__(
            self, *args, **kwargs, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )

        self.logger = logging.getLogger(self.__class__.__name__)

        self.config = config
        self.state_providers = state_providers if state_providers is not None else {}

        self.sections_sizer = None
        self._panels: list[ConfigSectionPanel] = []

        self.SetMinSize(self.GetParent().GetMinSize())
        self.SetSize(self.GetParent().GetMinSize())

        icon = wx.Icon()
        icon.CopyFromBitmap(
            wx.ArtProvider.GetBitmap(
                wx.ART_EXECUTABLE_FILE,
                client=wx.ART_FRAME_ICON,
                size=wx.Size(DEFAULT_ICON_SIZE, DEFAULT_ICON_SIZE),
            )
        )
        self.SetIcon(icon)

        self._create_widgets()

        self.logger.debug(self)

    def _create_widgets(self) -> None:
        scroll_panel = wx.lib.scrolledpanel.ScrolledPanel(self)

        button_sizer = wx.StdDialogButtonSizer()
        self.sections_sizer = wx.BoxSizer(wx.VERTICAL)
        assert self.sections_sizer is not None
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        for config_section_definition_name in self.config.CONFIG_SECTION_DEFINITIONS:
            config_section_definition = self.config.CONFIG_SECTION_DEFINITIONS[
                config_section_definition_name
            ]

            state_provider = self.state_providers.get(config_section_definition_name)
            config_section_panel = ConfigSectionPanel(
                config_section_definition,
                self.config.get_section(config_section_definition_name),
                self.config,
                scroll_panel,
                state_provider=state_provider,
                dialog=self,
            )

            self.sections_sizer.Add(
                config_section_panel,
                proportion=0,
                flag=wx.EXPAND | wx.ALL,
                border=UI_BORDER,
            )
            self._panels.append(config_section_panel)

            if (
                not config_section_definition.is_enabled(self.config.config_sections)
                or len(config_section_panel.GetChildren()) == 1
            ):
                self.sections_sizer.Show(config_section_panel, False)

        self.button_ok = wx.Button(self, label=_("OK"))
        self.button_ok.Bind(wx.EVT_BUTTON, self.on_ok)
        button_sizer.Add(self.button_ok)

        self.button_save = wx.Button(self, label=_("Save"))
        self.button_save.Bind(wx.EVT_BUTTON, self.on_save)
        button_sizer.Add(self.button_save)

        self.button_cancel = wx.Button(self, label=_("Cancel"))
        self.button_cancel.Bind(wx.EVT_BUTTON, self.on_cancel)
        button_sizer.Add(self.button_cancel)
        button_sizer.Realize()

        scroll_panel.SetSizer(self.sections_sizer)
        scroll_panel.SetupScrolling()

        main_sizer.Add(scroll_panel, proportion=1, flag=wx.EXPAND)

        main_sizer.Add(
            button_sizer, proportion=0, flag=wx.ALL | wx.ALIGN_RIGHT, border=UI_BORDER
        )

        self.SetSizer(main_sizer)
        self.Fit()

    def update_visibility(self) -> None:
        assert self.sections_sizer is not None
        self.TransferDataFromWindow()

        for config_section_definition_name in self.config.CONFIG_SECTION_DEFINITIONS:
            config_section_definition = self.config.CONFIG_SECTION_DEFINITIONS[
                config_section_definition_name
            ]

            config_section_panel = wx.FindWindowByName(
                config_section_definition_name, parent=self
            )
            if config_section_panel is None:
                self.logger.error(
                    "Unable to find the %s panel.", config_section_definition_name
                )
                raise ValueError(
                    ERR_PANEL_NOT_FOUND.format(config_section_definition_name)
                )

            if (
                not config_section_definition.is_enabled(self.config.config_sections)
                or len(config_section_panel.GetChildren()) == 1
            ):
                self.sections_sizer.Show(config_section_panel, False)
            else:
                self.sections_sizer.Show(config_section_panel, True)

        self.Layout()
        self.Fit()

    def on_ok(self, e):
        self.logger.debug("on_ok: %s", e)

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
        self.logger.debug("on_save: %s", e)

        self.TransferDataFromWindow()

        if self.Validate():
            self.config.write()
            self._save_runtime_state()

    def _save_runtime_state(self):
        for panel in self._panels:
            panel._save_runtime_state()

    def on_cancel(self, e):
        self.logger.debug("on_cancel: %s", e)

        self.EndModal(wx.ID_CANCEL)
