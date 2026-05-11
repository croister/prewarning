import wx

from utils.hotkey_bindings import HotKeyBindingDefinition, HotKeyDefinition


class TestHelpDialog:
    def test_create(self, wx_app):
        from utils.help_dialog import HelpDialog
        dlg = HelpDialog(None, '1.0.0')
        assert dlg is not None
        assert dlg.GetTitle() == 'Help'
        dlg.Destroy()

    def test_has_html(self, wx_app):
        from utils.help_dialog import HelpDialog
        dlg = HelpDialog(None, '1.0.0')
        from wx.html import HtmlWindow
        html_windows = [c for c in dlg.GetChildren() if isinstance(c, HtmlWindow)]
        assert len(html_windows) > 0
        dlg.Destroy()

    def test_html_contains_help_title(self, wx_app):
        from utils.help_dialog import HelpDialog
        from wx.html import HtmlWindow
        dlg = HelpDialog(None, '2.0.0')
        html_windows = [c for c in dlg.GetChildren() if isinstance(c, HtmlWindow)]
        assert len(html_windows) > 0
        text = html_windows[0].ToText()
        assert 'PreWarning' in text
        dlg.Destroy()

    def _get_html(self, dlg):
        from wx.html import HtmlWindow
        for c in dlg.GetChildren():
            if isinstance(c, HtmlWindow):
                return c
        return None

    def test_html_contains_punch_sources(self, wx_app):
        from utils.help_dialog import HelpDialog
        dlg = HelpDialog(None, '1.0.0')
        html = self._get_html(dlg)
        assert html is not None
        text = html.ToText()
        assert 'Punch Sources' in text
        dlg.Destroy()

    def test_html_contains_start_list_sources(self, wx_app):
        from utils.help_dialog import HelpDialog
        dlg = HelpDialog(None, '1.0.0')
        html = self._get_html(dlg)
        assert html is not None
        text = html.ToText()
        assert 'Start List Sources' in text
        dlg.Destroy()

    def test_with_hotkey_bindings(self, wx_app):
        from utils.help_dialog import HelpDialog
        hotkey1 = HotKeyDefinition(ord('A'), wx.ACCEL_CTRL)
        hk1 = HotKeyBindingDefinition(name='test', hotkey=hotkey1, handler=lambda: None, description='Test action')
        bindings = [hk1]
        dlg = HelpDialog(None, '1.0.0', hotkey_bindings=bindings)
        html = self._get_html(dlg)
        assert html is not None
        text = html.ToText()
        assert 'Hotkeys' in text
        assert 'Test action' in text
        dlg.Destroy()

    def test_hotkey_with_alternates(self, wx_app):
        from utils.help_dialog import HelpDialog
        hk1 = HotKeyDefinition(ord('A'), wx.ACCEL_CTRL)
        alt1 = HotKeyDefinition(ord('A'), wx.ACCEL_CTRL | wx.ACCEL_SHIFT)
        hk_binding = HotKeyBindingDefinition(name='test', hotkey=hk1, handler=lambda: None,
                                             description='My action', alternate_hotkeys=[alt1])
        dlg = HelpDialog(None, '1.0.0', hotkey_bindings=[hk_binding])
        html = self._get_html(dlg)
        assert html is not None
        text = html.ToText()
        assert 'Ctrl' in text
        assert 'A' in text
        assert 'Shift' in text
        dlg.Destroy()

    def test_hidden_hotkeys_not_shown(self, wx_app):
        from utils.help_dialog import HelpDialog
        hk_visible = HotKeyDefinition(ord('V'), wx.ACCEL_CTRL)
        hk_hidden = HotKeyDefinition(ord('H'), wx.ACCEL_CTRL)
        binding_visible = HotKeyBindingDefinition(name='v', hotkey=hk_visible, handler=lambda: None, description='Visible')
        binding_hidden = HotKeyBindingDefinition(name='h', hotkey=hk_hidden, handler=lambda: None, description='Hidden', hidden=True)
        dlg = HelpDialog(None, '1.0.0', hotkey_bindings=[binding_visible, binding_hidden])
        html = self._get_html(dlg)
        assert html is not None
        text = html.ToText()
        assert 'Visible' in text
        assert 'Hidden' not in text
        dlg.Destroy()

    def test_no_hotkey_bindings_omits_section(self, wx_app):
        from utils.help_dialog import HelpDialog
        dlg = HelpDialog(None, '1.0.0', hotkey_bindings=None)
        html = self._get_html(dlg)
        assert html is not None
        text = html.ToText()
        assert 'Hotkeys' not in text
        dlg.Destroy()

    def test_empty_hotkey_bindings_omits_section(self, wx_app):
        from utils.help_dialog import HelpDialog
        dlg = HelpDialog(None, '1.0.0', hotkey_bindings=[])
        html = self._get_html(dlg)
        assert html is not None
        text = html.ToText()
        assert 'Hotkeys' not in text
        dlg.Destroy()

    def test_parent_relationship(self, wx_app):
        from utils.help_dialog import HelpDialog
        parent = wx.Frame(None)
        dlg = HelpDialog(parent, '1.0.0')
        assert dlg.GetParent() is parent
        dlg.Destroy()
        parent.Destroy()

    def test_wxhtml_link_click(self, wx_app, monkeypatch):
        from utils.help_dialog import WxHTML
        import webbrowser
        opened = []
        monkeypatch.setattr(webbrowser, 'open', lambda url: opened.append(url))
        parent = wx.Frame(None)
        html = WxHTML(parent)
        link = type('Link', (), {'GetHref': lambda self: 'https://example.com'})()
        html.OnLinkClicked(link)
        assert opened == ['https://example.com']
        html.Destroy()
        parent.Destroy()
