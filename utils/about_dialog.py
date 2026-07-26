import importlib.metadata
import platform
from pathlib import Path

import wx
import wx.html

from utils.i18n import _

APP_ICON_PATH = str(Path(__file__).resolve().parent.parent / "favicon.ico")


class AboutDialog(wx.Frame):
    def __init__(self, parent, app_version: str):
        wx.Frame.__init__(self, parent, wx.ID_ANY, title=_("About"))

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
        title_text = wx.StaticText(self, label=f"PreWarning {app_version}")
        title_font = title_text.GetFont()
        title_font.SetPointSize(title_font.GetPointSize() + 4)
        title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        title_text.SetFont(title_font)
        title_sizer.Add(title_text, 0, wx.ALIGN_CENTER_VERTICAL)
        main_sizer.Add(title_sizer, 0, wx.ALL, 12)

        self._html = WxHTML(self)
        main_sizer.Add(self._html, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        self.SetSizer(main_sizer)

        contents = (
            "<p><b>" + _("Author:") + "</b> Christian Lindblom<br>"
            '<a href="mailto:croister@croister.se">croister@croister.se</a></p>'
        )
        contents += (
            "<p>"
            + _(
                "PreWarning is intended to be used to perform pre-warning for an Orienteering Relay event."
            )
            + "</p>"
        )

        contents += "<h3>" + _("System") + "</h3>"
        contents += (
            f"<p>Python {platform.python_version()}<br>{platform.platform()}</p>"
        )

        contents += "<h3>" + _("Dependencies") + "</h3><table>"
        try:
            requirements = importlib.metadata.requires("prewarning")
            if requirements:
                for req in requirements:
                    parts = req.split(";")
                    dist_name = (
                        parts[0]
                        .split("==")[0]
                        .split(">=")[0]
                        .split("~=")[0]
                        .split("!=")[0]
                        .strip()
                    )
                    try:
                        ver = importlib.metadata.version(dist_name)
                    except importlib.metadata.PackageNotFoundError:
                        ver = "unknown"
                    contents += f"<tr><td>{dist_name}</td><td>{ver}</td></tr>"
        except importlib.metadata.PackageNotFoundError:
            pass
        contents += "</table>"

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
