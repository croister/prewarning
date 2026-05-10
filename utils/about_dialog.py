import importlib.metadata
import platform
from pathlib import Path

import wx
import wx.html


APP_ICON_PATH = str(Path(__file__).resolve().parent.parent / 'favicon.ico')


class AboutDialog(wx.Frame):

    def __init__(self, parent, app_version: str):
        wx.Frame.__init__(self, parent, wx.ID_ANY, title="About")

        app_icon = wx.Icon(APP_ICON_PATH, wx.BITMAP_TYPE_ICO)
        self.SetIcon(app_icon)
        self.SetBackgroundColour(wx.WHITE)

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        title_sizer = wx.BoxSizer(wx.HORIZONTAL)
        app_img = wx.Image(APP_ICON_PATH, wx.BITMAP_TYPE_ICO)
        app_img.Rescale(32, 32, wx.IMAGE_QUALITY_HIGH)
        app_bmp = wx.Bitmap(app_img)
        app_static_bmp = wx.StaticBitmap(self, bitmap=app_bmp)
        title_sizer.Add(app_static_bmp, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        title_text = wx.StaticText(self, label="PreWarning {app_version}".format(app_version=app_version))
        title_font = title_text.GetFont()
        title_font.SetPointSize(title_font.GetPointSize() + 4)
        title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        title_text.SetFont(title_font)
        title_sizer.Add(title_text, 0, wx.ALIGN_CENTER_VERTICAL)
        main_sizer.Add(title_sizer, 0, wx.ALL, 12)

        self._html = WxHTML(self)
        main_sizer.Add(self._html, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        self.SetSizer(main_sizer)

        contents = '<p><b>Author:</b> Christian Lindblom<br>' \
                    '<a href="mailto:croister@croister.se">croister@croister.se</a></p>'
        contents += '<p>PreWarning is intended to be used to perform pre-warning for an Orienteering Relay event.</p>'

        contents += '<h3>System</h3>'
        contents += '<p>Python {python_version}<br>{platform}</p>'.format(
            python_version=platform.python_version(),
            platform=platform.platform(),
        )

        contents += '<h3>Dependencies</h3><table>'
        try:
            requirements = importlib.metadata.requires('prewarning')
            if requirements:
                for req in requirements:
                    parts = req.split(';')
                    dist_name = parts[0].split('==')[0].split('>=')[0].split('~=')[0].split('!=')[0].strip()
                    try:
                        ver = importlib.metadata.version(dist_name)
                    except importlib.metadata.PackageNotFoundError:
                        ver = 'unknown'
                    contents += '<tr><td>{name}</td><td>{version}</td></tr>'.format(
                        name=dist_name, version=ver)
        except importlib.metadata.PackageNotFoundError:
            pass
        contents += '</table>'

        self._html.SetPage(contents)
        wx.CallAfter(self._fit_to_dialog)

    def _fit_to_dialog(self):
        w, h = self._html.GetVirtualSize()
        if w > 0 and h > 0:
            self._html.SetMinSize(wx.Size(w, h))
        self.Fit()
        self.SetMinSize(self.GetSize())


class WxHTML(wx.html.HtmlWindow):

    def OnLinkClicked(self, link):
        import webbrowser
        webbrowser.open(link.GetHref())
