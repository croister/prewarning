# -*- coding: utf-8 -*-

import wx


def select_file(parent: wx.Window,
                message: str = 'Select a file',
                default_dir: str = None,
                wildcard: str = '') -> str or None:
    with wx.FileDialog(parent=parent, message=message, defaultDir=default_dir, wildcard=wildcard,
                       style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:

        if fileDialog.ShowModal() == wx.ID_CANCEL:
            return None

        pathname = fileDialog.GetPath()
        return pathname
