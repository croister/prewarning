# -*- coding: utf-8 -*-

import webbrowser
from typing import List

import wx
import wx.html

from punchsources import PUNCH_SOURCES
from startlistsources import START_LIST_SOURCES
from utils.hotkey_bindings import HotKeyBindingDefinition
from utils.i18n import _


class HelpDialog(wx.Frame):
    def __init__(
        self,
        parent,
        app_version: str,
        hotkey_bindings: List[HotKeyBindingDefinition] | None = None,
    ):
        wx.Frame.__init__(
            self, parent, wx.ID_ANY, title=_("Help"), size=wx.Size(600, 800)
        )

        if hotkey_bindings is None:
            hotkey_bindings = []

        icon = wx.Icon()
        icon.CopyFromBitmap(
            wx.ArtProvider.GetBitmap(
                wx.ART_HELP, client=wx.ART_FRAME_ICON, size=wx.Size(16, 16)
            )
        )
        self.SetIcon(icon)

        html = WxHTML(self)

        contents = (
            "<h2>"
            + _("Help for PreWarning {app_version}").format(app_version=app_version)
            + "</h2>"
        )
        contents += (
            "<p>"
            + _(
                "The PreWarning application is intended to be used to perform pre-warning for an "
                "Orienteering Relay event."
            )
            + "<br>"
            + _(
                "It can be used with a display and a speaker to give both visual and audible pre-warnings. "
                "Either can be omitted to use only one of them."
            )
            + "<br>"
            + _(
                "When using a display it is best used in the portrait orientation, "
                "but both orientations are supported. A TV can be used to get a bigger screen."
            )
            + "</p>"
            "<p>"
            "<ol>"
            "<li>"
            + _(
                "The application fetches electronic punches from a <b>Punch Source</b>."
            )
            + "</li>"
            "<li>"
            + _(
                "Looks up the teams' bib number and which relay leg that punch belongs to from a"
                " <b>Start List Source</b>."
            )
            + "</li>"
            "<li>"
            + _(
                "Displays the punch time, bib number and relay leg on the display "
                "and reads out the bib number in the speakers."
            )
            + "</li>"
            "</ol>"
            "<p>"
            + _(
                "There are multiple choices for both Punch Sources and Start List Sources."
            )
            + "</p>"
            "<p>"
            + _(
                "The application can be controlled interactively or driven entirely from the "
                "configuration file."
            )
            + "<br>"
            + _("In the interactive mode the right click menu or hotkeys can be used.")
            + "</p>"
            "</p>"
        )

        contents += (
            "<h3>" + _("Punch Sources") + "</h3>"
            "<p>"
            + _(
                "One of these Punch Sources is selected to be used to fetch the electronic punches."
            )
            + "</p>"
        )

        for punch_source_name in PUNCH_SOURCES:
            punch_source = PUNCH_SOURCES[punch_source_name]
            contents += "<h4>{name}</h4><p>{description}</p>".format(
                name=_(str(punch_source.display_name)),
                description=_(str(punch_source.description)),
            )

        contents += (
            "<h3>" + _("Start List Sources") + "</h3>"
            "<p>"
            + _(
                "One of these Start List Sources is selected to be used to look up the "
                "bib number and relay leg for the punches."
            )
            + "</p>"
        )

        for start_list_source_name in START_LIST_SOURCES:
            start_list_source = START_LIST_SOURCES[start_list_source_name]
            contents += "<h4>{name}</h4><p>{description}</p>".format(
                name=_(str(start_list_source.display_name)),
                description=_(str(start_list_source.description)),
            )

        if len(hotkey_bindings):
            contents += (
                "<h3>" + _("Hotkeys") + "</h3>"
                '<table border="1">'
                "<tr><th>"
                + _("Hotkey (Alternate hotkeys)")
                + "</th><th>"
                + _("Description")
                + "</th></tr>"
            )

            for key_binding in hotkey_bindings:
                if key_binding.hidden:
                    continue

                contents += "<tr><td>{hotkey}".format(hotkey=key_binding.hotkey)
                if len(key_binding.alternate_hotkeys):
                    contents += " ({alternate_hotkeys})".format(
                        alternate_hotkeys=", ".join(
                            [str(ahk) for ahk in key_binding.alternate_hotkeys]
                        )
                    )
                contents += "</td><td>{description}</td></tr>".format(
                    description=key_binding.description
                )

            contents += "</table>"

        html.SetPage(contents)


class WxHTML(wx.html.HtmlWindow):
    def OnLinkClicked(self, link):
        webbrowser.open(link.GetHref())
