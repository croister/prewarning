"""Control Window — secondary operator monitor on landscape display."""

import logging
from collections.abc import Callable

import wx

from utils.i18n import N_, _

# Column indices for recent pre-warnings
_COL_TIME = 0
_COL_TEAM = 1
_COL_LEG = 2

_MAX_RECENT_PREWARNINGS = 10

# Section border
_BORDER = 8
_INNER_BORDER = 4


class ControlWindow(wx.Frame):
    """Operator monitor window showing health, stats, and quick actions."""

    def __init__(
        self,
        parent: wx.Window,
        action_handlers: dict[str, Callable],
        update_callback: Callable[[], None] | None = None,
        key_handler: Callable[[wx.KeyEvent], None] | None = None,
    ):
        super().__init__(
            parent,
            title="PreWarning: " + _("Control"),
            style=wx.DEFAULT_FRAME_STYLE,
        )

        self.logger = logging.getLogger(self.__class__.__name__)
        self._action_handlers = action_handlers
        self._update_callback = update_callback

        self.SetMinSize(wx.Size(600, 400))
        self.SetSize(wx.Size(700, 600))

        # Set the app icon if available
        try:
            from utils.about_dialog import APP_ICON_PATH

            self.SetIcon(wx.Icon(APP_ICON_PATH, wx.BITMAP_TYPE_ICO))
        except Exception:  # noqa: BLE001, S110 - best-effort icon set, failure is non-critical
            pass

        self._build_ui()

        # Don't destroy on close, just hide
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_SHOW, self._on_show)

        # Hotkey support — forward key events to the main window's handler
        if key_handler:
            self.Bind(wx.EVT_CHAR_HOOK, key_handler)

        # Timer to periodically refresh data
        self._timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_timer, self._timer)
        self._timer.Start(10000)  # Catch-all update every 10 seconds

    def _on_close(self, event):
        """Hide instead of destroying."""
        self.Hide()

    def _on_show(self, event):
        """Ensure minimum width when the window becomes visible."""
        if event.IsShown():
            wx.CallAfter(self._ensure_min_width)
        event.Skip()

    def _on_timer(self, event):
        """Periodically refresh data from the main application."""
        if self._update_callback and self.IsShown():
            self._update_callback()

    def _build_ui(self):
        """Build the control window layout."""
        self._panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Health Status Section (top, full width) ---
        self._health_box = wx.StaticBoxSizer(
            wx.VERTICAL, self._panel, _("Health Status")
        )
        health_content_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self._health_panel = wx.Panel(self._health_box.GetStaticBox())
        self._health_sizer = wx.FlexGridSizer(cols=2, hgap=12, vgap=4)
        self._health_sizer.AddGrowableCol(1, 1)
        self._health_panel.SetSizer(self._health_sizer)
        health_content_sizer.Add(
            self._health_panel,
            proportion=1,
            flag=wx.EXPAND | wx.ALL,
            border=_INNER_BORDER,
        )

        # Big status dot
        self._status_dot = wx.StaticText(
            self._health_box.GetStaticBox(),
            label="\u2b24",
        )
        dot_font = self._status_dot.GetFont()
        dot_font.SetPointSize(48)
        self._status_dot.SetFont(dot_font)
        self._status_dot.SetMinSize(wx.Size(70, 80))
        self._status_dot.SetForegroundColour(wx.Colour(0, 180, 0))
        self._status_dot.Bind(wx.EVT_LEFT_DOWN, self._on_status_dot_click)
        health_content_sizer.Add(
            self._status_dot,
            flag=wx.ALIGN_TOP | wx.LEFT | wx.RIGHT,
            border=_BORDER,
        )

        self._health_box.Add(health_content_sizer, flag=wx.EXPAND)
        main_sizer.Add(self._health_box, flag=wx.EXPAND | wx.ALL, border=_BORDER)

        # --- Middle section: Statistics (left) and Recent Pre-Warnings (right) ---
        middle_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # --- Statistics Section ---
        self._stats_box = wx.StaticBoxSizer(wx.VERTICAL, self._panel, _("Statistics"))
        self._stats_panel = wx.Panel(self._stats_box.GetStaticBox())
        self._stats_sizer = wx.FlexGridSizer(cols=2, hgap=12, vgap=4)
        self._stats_sizer.AddGrowableCol(1, 1)
        self._stats_panel.SetSizer(self._stats_sizer)
        self._stats_box.Add(
            self._stats_panel, flag=wx.EXPAND | wx.ALL, border=_INNER_BORDER
        )
        middle_sizer.Add(
            self._stats_box, proportion=1, flag=wx.EXPAND | wx.ALL, border=_BORDER
        )

        # --- Recent Pre-Warnings Section ---
        self._recent_box = wx.StaticBoxSizer(
            wx.VERTICAL, self._panel, _("Recent Pre-Warnings")
        )
        self._recent_list = wx.ListCtrl(
            self._recent_box.GetStaticBox(),
            style=wx.LC_REPORT,
        )
        self._recent_list.AppendColumn(_("Time"), width=100)
        self._recent_list.AppendColumn(_("Team"), width=80)
        self._recent_list.AppendColumn(_("Leg"), width=60)
        self._recent_list.Bind(wx.EVT_SIZE, self._on_recent_list_resize)
        self._recent_box.Add(
            self._recent_list,
            proportion=1,
            flag=wx.EXPAND | wx.ALL,
            border=_INNER_BORDER,
        )
        middle_sizer.Add(
            self._recent_box, proportion=1, flag=wx.EXPAND | wx.ALL, border=_BORDER
        )

        main_sizer.Add(middle_sizer, proportion=1, flag=wx.EXPAND)

        # --- Quick Actions Section ---
        self._actions_box = wx.StaticBoxSizer(wx.HORIZONTAL, self._panel, _("Actions"))
        self._build_action_buttons(self._actions_box)
        main_sizer.Add(self._actions_box, flag=wx.EXPAND | wx.ALL, border=_BORDER)

        self._panel.SetSizer(main_sizer)

    def _build_action_buttons(self, sizer: wx.StaticBoxSizer):
        """Build quick-action buttons."""
        self._action_buttons: list[tuple[str, wx.Button]] = []
        buttons = [
            (N_("Settings"), "settings", wx.ART_EXECUTABLE_FILE),
            (N_("Voice Manager"), "voice_manager", wx.ART_CDROM),
            (N_("Clear Display"), "clear", wx.ART_DELETE),
            (N_("Fake Punch"), "fake_punch", wx.ART_GO_DOWN),
            (N_("Play Testing Sound"), "test_sound", wx.ART_QUESTION),
            (N_("Full Screen"), "full_screen", wx.ART_FIND),
            (N_("Exit"), "exit", wx.ART_QUIT),
        ]

        for label, action_key, art_id in buttons:
            btn = wx.Button(sizer.GetStaticBox(), label=_(label))
            btn.Bind(wx.EVT_BUTTON, lambda e, key=action_key: self._on_action(key))
            sizer.Add(btn, flag=wx.ALL, border=_INNER_BORDER)
            self._action_buttons.append((label, btn))

    def _on_action(self, action_key: str):
        """Handle a quick-action button click."""
        handler = self._action_handlers.get(action_key)
        if handler:
            handler()

    def _on_status_dot_click(self, event):
        """Handle click on the status dot — opens relevant dialog based on health issues."""
        handler = self._action_handlers.get("health_dot_click")
        if handler:
            handler()

    def update_status_dot(
        self, colour: wx.Colour, tooltip: str, actionable: bool = False
    ) -> None:
        """Update the status dot colour, tooltip, and cursor."""
        self._status_dot.SetForegroundColour(colour)
        self._status_dot.SetToolTip(tooltip)
        if actionable:
            self._status_dot.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        else:
            self._status_dot.SetCursor(wx.Cursor(wx.CURSOR_ARROW))
        self._status_dot.Refresh()

    def _on_recent_list_resize(self, event):
        """Resize the Time column to fill remaining space."""
        event.Skip()
        if getattr(self, "_updating_columns", False):
            return
        list_width = self._recent_list.GetClientSize().GetWidth()
        team_width = self._recent_list.GetColumnWidth(_COL_TEAM)
        leg_width = self._recent_list.GetColumnWidth(_COL_LEG)
        time_width = list_width - team_width - leg_width
        if time_width > 0:
            self._recent_list.SetColumnWidth(_COL_TIME, time_width)

    # --- Public update methods ---

    def update_health(
        self,
        items: list[tuple[str, str, wx.Colour | None, str]],
    ) -> None:
        """Update the health status display.

        Args:
            items: List of (label, value, colour, tooltip) tuples.
                   colour=None means use default text colour.
        """
        # Reuse existing controls or create/remove as needed
        existing_count = self._health_sizer.GetItemCount() // 2
        target_count = len(items)

        # Remove excess rows
        while existing_count > target_count:
            existing_count -= 1
            self._health_sizer.GetItem(existing_count * 2 + 1).GetWindow().Destroy()
            self._health_sizer.GetItem(existing_count * 2).GetWindow().Destroy()

        # Update existing rows
        for i, (label, value, colour, tooltip) in enumerate(items[:existing_count]):
            label_ctrl = self._health_sizer.GetItem(i * 2).GetWindow()
            label_ctrl.SetLabel(label)
            label_ctrl.SetToolTip(tooltip)
            value_ctrl = self._health_sizer.GetItem(i * 2 + 1).GetWindow()
            value_ctrl.SetLabel(value)
            value_ctrl.SetToolTip(tooltip)
            if colour is not None:
                value_ctrl.SetForegroundColour(colour)
            else:
                value_ctrl.SetForegroundColour(
                    wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT)
                )

        # Add new rows
        for i in range(existing_count, target_count):
            label, value, colour, tooltip = items[i]
            label_ctrl = wx.StaticText(self._health_panel, label=label)
            label_ctrl.SetFont(label_ctrl.GetFont().Bold())
            label_ctrl.SetToolTip(tooltip)
            self._health_sizer.Add(label_ctrl)

            value_ctrl = wx.StaticText(self._health_panel, label=value)
            if colour is not None:
                value_ctrl.SetForegroundColour(colour)
            value_ctrl.SetToolTip(tooltip)
            self._health_sizer.Add(value_ctrl)

        self._health_panel.Layout()
        self._panel.Layout()

    def update_stats(self, items: list[tuple[str, str, str]]) -> None:
        """Update the statistics display.

        Args:
            items: List of (label, value, tooltip) tuples.
        """
        # Reuse existing controls or create/remove as needed
        existing_count = self._stats_sizer.GetItemCount() // 2
        target_count = len(items)

        # Remove excess rows
        while existing_count > target_count:
            existing_count -= 1
            self._stats_sizer.GetItem(existing_count * 2 + 1).GetWindow().Destroy()
            self._stats_sizer.GetItem(existing_count * 2).GetWindow().Destroy()

        # Update existing rows
        for i, (label, value, tooltip) in enumerate(items[:existing_count]):
            label_ctrl = self._stats_sizer.GetItem(i * 2).GetWindow()
            label_ctrl.SetLabel(label)
            label_ctrl.SetToolTip(tooltip)
            value_ctrl = self._stats_sizer.GetItem(i * 2 + 1).GetWindow()
            value_ctrl.SetLabel(value)
            value_ctrl.SetToolTip(tooltip)

        # Add new rows
        for i in range(existing_count, target_count):
            label, value, tooltip = items[i]
            label_ctrl = wx.StaticText(self._stats_panel, label=label)
            label_ctrl.SetFont(label_ctrl.GetFont().Bold())
            label_ctrl.SetToolTip(tooltip)
            self._stats_sizer.Add(label_ctrl)

            value_ctrl = wx.StaticText(self._stats_panel, label=value)
            value_ctrl.SetToolTip(tooltip)
            self._stats_sizer.Add(value_ctrl)

        self._stats_panel.Layout()
        self._panel.Layout()

    def add_prewarning(self, time_str: str, team: str, leg: str) -> None:
        """Add a pre-warning to the recent list (newest at top)."""
        self._recent_list.InsertItem(0, time_str)
        self._recent_list.SetItem(0, _COL_TEAM, team)
        self._recent_list.SetItem(0, _COL_LEG, leg)

        # Trim to max
        while self._recent_list.GetItemCount() > _MAX_RECENT_PREWARNINGS:
            self._recent_list.DeleteItem(self._recent_list.GetItemCount() - 1)

    def clear_prewarnings(self) -> None:
        """Clear the recent pre-warnings list."""
        self._recent_list.DeleteAllItems()

    # --- Display positioning ---

    @staticmethod
    def find_landscape_display(
        exclude_display: wx.Display | None = None,
    ) -> wx.Display | None:
        """Find a landscape-oriented display, excluding the given one."""
        exclude_idx = -1
        if exclude_display is not None:
            for i in range(wx.Display.GetCount()):
                if wx.Display(i).GetGeometry() == exclude_display.GetGeometry():
                    exclude_idx = i
                    break

        for i in range(wx.Display.GetCount()):
            if i == exclude_idx:
                continue
            display = wx.Display(i)
            geo = display.GetGeometry()
            if geo.GetWidth() >= geo.GetHeight():
                return display
        return None

    def position_on_display(self, display: wx.Display) -> None:
        """Position and size the window on the given display."""
        area = display.GetClientArea()
        width = min(area.GetWidth() * 2 // 3, 750)
        height = min(area.GetHeight() // 2, 600)
        x = area.GetLeft() + (area.GetWidth() - width) // 2
        y = area.GetTop() + (area.GetHeight() - height) // 2
        self.SetPosition(wx.Point(x, y))
        self.SetSize(wx.Size(width, height))

    def _ensure_min_width(self):
        """Expand the window width if the content (buttons) needs more space."""
        self._panel.Layout()
        best_width = self._panel.GetBestSize().GetWidth() + 20
        current_size = self.GetSize()
        if best_width > current_size.GetWidth():
            self.SetSize(wx.Size(best_width, current_size.GetHeight()))

    def refresh_translations(self) -> None:
        """Update all translated labels without rebuilding the UI."""
        self.SetTitle("PreWarning: " + _("Control"))

        # Section headers
        self._health_box.GetStaticBox().SetLabel(_("Health Status"))
        self._stats_box.GetStaticBox().SetLabel(_("Statistics"))
        self._recent_box.GetStaticBox().SetLabel(_("Recent Pre-Warnings"))
        self._actions_box.GetStaticBox().SetLabel(_("Actions"))

        # Recent pre-warnings column headers
        col = self._recent_list.GetColumn(_COL_TIME)
        col.SetText(_("Time"))
        self._recent_list.SetColumn(_COL_TIME, col)
        col = self._recent_list.GetColumn(_COL_TEAM)
        col.SetText(_("Team"))
        self._recent_list.SetColumn(_COL_TEAM, col)
        col = self._recent_list.GetColumn(_COL_LEG)
        col.SetText(_("Leg"))
        self._recent_list.SetColumn(_COL_LEG, col)
        # Size Team and Leg to fit header text, then fix Time to fill rest
        self._updating_columns = True
        padding = 40  # Account for ListCtrl internal header margins and sort arrow
        team_width = max(
            self._recent_list.GetTextExtent(_("Team")).GetWidth() + padding, 80
        )
        leg_width = max(
            self._recent_list.GetTextExtent(_("Leg")).GetWidth() + padding, 60
        )
        self._recent_list.SetColumnWidth(_COL_TEAM, team_width)
        self._recent_list.SetColumnWidth(_COL_LEG, leg_width)
        list_width = self._recent_list.GetClientSize().GetWidth()
        time_width = list_width - team_width - leg_width
        if time_width > 0:
            self._recent_list.SetColumnWidth(_COL_TIME, time_width)
        self._updating_columns = False

        # Action buttons
        for label_key, btn in self._action_buttons:
            btn.SetLabel(_(label_key))

        self._panel.Layout()

        # Ensure window is wide enough for the new button labels
        self._ensure_min_width()
