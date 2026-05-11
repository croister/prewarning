import wx


class TestAboutDialog:
    def test_create(self, wx_app):
        from utils.about_dialog import AboutDialog
        dlg = AboutDialog(None, '2.2.0')
        assert dlg is not None
        assert dlg.GetTitle() == 'About'
        dlg.Destroy()

    def test_title_contains_version(self, wx_app):
        from utils.about_dialog import AboutDialog
        dlg = AboutDialog(None, '9.9.9')
        assert 'About' in dlg.GetTitle()
        dlg.Destroy()

    def test_has_html_window(self, wx_app):
        from utils.about_dialog import AboutDialog
        dlg = AboutDialog(None, '1.0.0')
        assert hasattr(dlg, '_html')
        dlg.Destroy()

    def test_html_page_contains_author(self, wx_app):
        from utils.about_dialog import AboutDialog
        dlg = AboutDialog(None, '1.0.0')
        html = dlg._html
        page_text = html.ToText()
        assert 'Christian Lindblom' in page_text
        dlg.Destroy()

    def test_title_contains_version_string(self, wx_app):
        from utils.about_dialog import AboutDialog
        dlg = AboutDialog(None, '3.4.5')
        assert dlg.GetTitle() == 'About'
        dlg.Destroy()

    def test_html_page_contains_system_info(self, wx_app):
        from utils.about_dialog import AboutDialog
        dlg = AboutDialog(None, '1.0.0')
        html = dlg._html
        page_text = html.ToText()
        assert 'Python' in page_text
        dlg.Destroy()

    def test_html_page_contains_dependencies(self, wx_app):
        from utils.about_dialog import AboutDialog
        dlg = AboutDialog(None, '1.0.0')
        html = dlg._html
        page_text = html.ToText()
        assert 'wxpython' in page_text.lower() or 'wx' in page_text.lower()
        dlg.Destroy()

    def test_parent_relationship(self, wx_app):
        from utils.about_dialog import AboutDialog
        parent = wx.Frame(None)
        dlg = AboutDialog(parent, '1.0.0')
        assert dlg.GetParent() is parent
        dlg.Destroy()
        parent.Destroy()

    def test_html_link_click_method_exists(self, wx_app):
        from utils.about_dialog import WxHTML
        parent = wx.Frame(None)
        html = WxHTML(parent)
        assert hasattr(html, 'OnLinkClicked')
        html.Destroy()
        parent.Destroy()

    def test_html_link_click_opens_browser(self, wx_app, monkeypatch):
        from utils.about_dialog import WxHTML
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
