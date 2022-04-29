# -*- coding: utf-8 -*-

import logging
from typing import List, Callable

import wx

KEY_CODE_LOOKUP = {
    335: 'Add',  # WXK_ADD
    307: 'Alt',  # WXK_ALT
    8: 'Back',  # WXK_BACK

    417: 'Browser Back',  # WXK_BROWSER_BACK
    422: 'Browser Favourites',  # WXK_BROWSER_FAVORITES
    418: 'Browser Forward',  # WXK_BROWSER_FORWARD
    423: 'Browser Home',  # WXK_BROWSER_HOME
    419: 'Browser Refresh',  # WXK_BROWSER_REFRESH
    421: 'Browser Search',  # WXK_BROWSER_SEARCH
    420: 'Browser Stop',  # WXK_BROWSER_STOP

    303: 'Cancel',  # WXK_CANCEL
    311: 'Cancel',  # WXK_CAPITAL

    305: 'Clear',  # WXK_CLEAR
    # 308: 'Command',  # WXK_COMMAND
    308: 'Control',  # WXK_CONTROL

    338: 'Decimal',  # WXK_DECIMAL
    127: 'Delete',  # WXK_DELETE
    339: 'Divide',  # WXK_DIVIDE
    317: 'Down',  # WXK_DOWN
    312: 'End',  # WXK_END
    27: 'Escape',  # WXK_ESCAPE
    320: 'Execute',  # WXK_EXECUTE
    340: 'F1',  # WXK_F1
    349: 'F10',  # WXK_F10
    350: 'F11',  # WXK_F11
    351: 'F12',  # WXK_F12
    352: 'F13',  # WXK_F13
    353: 'F14',  # WXK_F14
    354: 'F15',  # WXK_F15
    355: 'F16',  # WXK_F16
    356: 'F17',  # WXK_F17
    357: 'F18',  # WXK_F18
    358: 'F19',  # WXK_F19
    341: 'F2',  # WXK_F2
    359: 'F20',  # WXK_F20
    360: 'F21',  # WXK_F21
    361: 'F22',  # WXK_F22
    362: 'F23',  # WXK_F23
    363: 'F24',  # WXK_F24
    342: 'F3',  # WXK_F3
    343: 'F4',  # WXK_F4
    344: 'F5',  # WXK_F5
    345: 'F6',  # WXK_F6
    346: 'F7',  # WXK_F7
    347: 'F8',  # WXK_F8
    348: 'F9',  # WXK_F9
    323: 'Help',  # WXK_HELP
    313: 'Home',  # WXK_HOME
    322: 'Insert',  # WXK_INSERT

    432: 'Launch App 1',  # WXK_LAUNCH_APP1
    433: 'Launch App 2',  # WXK_LAUNCH_APP2
    431: 'Launch App Mail',  # WXK_LAUNCH_MAIL

    301: 'Left Button',  # WXK_LBUTTON
    314: 'Left',  # WXK_LEFT
    304: 'Middle Button',  # WXK_MBUTTON

    427: 'Media Next Track',  # WXK_MEDIA_NEXT_TRACK

    430: 'Media Play/Pause',  # WXK_MEDIA_PLAY_PAUSE

    428: 'Media Previous Track',  # WXK_MEDIA_PREV_TRACK

    429: 'Media Stop',  # WXK_MEDIA_STOP

    309: 'Menu',  # WXK_MENU
    334: 'Multiply',  # WXK_MULTIPLY
    0: 'None',  # WXK_NONE
    364: 'Num Lock',  # WXK_NUMLOCK
    324: 'Numpad 0',  # WXK_NUMPAD0
    325: 'Numpad 1',  # WXK_NUMPAD1
    326: 'Numpad 2',  # WXK_NUMPAD2
    327: 'Numpad 3',  # WXK_NUMPAD3
    328: 'Numpad 4',  # WXK_NUMPAD4
    329: 'Numpad 5',  # WXK_NUMPAD5
    330: 'Numpad 6',  # WXK_NUMPAD6
    331: 'Numpad 7',  # WXK_NUMPAD7
    332: 'Numpad 8',  # WXK_NUMPAD8
    333: 'Numpad 9',  # WXK_NUMPAD9

    388: 'Numpad Add',  # WXK_NUMPAD_ADD
    383: 'Numpad Begin',  # WXK_NUMPAD_BEGIN
    391: 'Numpad Decimal',  # WXK_NUMPAD_DECIMAL
    385: 'Numpad Delete',  # WXK_NUMPAD_DELETE
    392: 'Numpad Divide',  # WXK_NUMPAD_DIVIDE
    379: 'Numpad Down',  # WXK_NUMPAD_DOWN
    382: 'Numpad End',  # WXK_NUMPAD_END
    370: 'Numpad Enter',  # WXK_NUMPAD_ENTER
    386: 'Numpad Equal',  # WXK_NUMPAD_EQUAL
    371: 'Numpad F1',  # WXK_NUMPAD_F1
    372: 'Numpad F2',  # WXK_NUMPAD_F2
    373: 'Numpad F3',  # WXK_NUMPAD_F3
    374: 'Numpad F4',  # WXK_NUMPAD_F4
    375: 'Numpad Home',  # WXK_NUMPAD_HOME
    384: 'Numpad Insert',  # WXK_NUMPAD_INSERT
    376: 'Numpad Left',  # WXK_NUMPAD_LEFT
    387: 'Numpad Multiply',  # WXK_NUMPAD_MULTIPLY
    381: 'Numpad Page Down',  # WXK_NUMPAD_PAGEDOWN
    380: 'Numpad Page Up',  # WXK_NUMPAD_PAGEUP
    378: 'Numpad Right',  # WXK_NUMPAD_RIGHT
    389: 'Numpad Separator',  # WXK_NUMPAD_SEPARATOR
    368: 'Numpad Space',  # WXK_NUMPAD_SPACE
    390: 'Numpad Subtract',  # WXK_NUMPAD_SUBTRACT
    369: 'Numpad Tab',  # WXK_NUMPAD_TAB
    377: 'Numpad Up',  # WXK_NUMPAD_UP

    367: 'Page Down',  # WXK_PAGEDOWN
    366: 'Page Up',  # WXK_PAGEUP
    310: 'Pause',  # WXK_PAUSE
    319: 'Print',  # WXK_PRINT

    302: 'Right Button',  # WXK_RBUTTON
    13: 'Return',  # WXK_RETURN
    316: 'Right',  # WXK_RIGHT
    365: 'Scroll',  # WXK_SCROLL
    318: 'Select',  # WXK_SELECT
    336: 'Separator',  # WXK_SEPARATOR
    306: 'Shift',  # WXK_SHIFT
    321: 'Snapshot',  # WXK_SNAPSHOT
    32: 'Space',  # WXK_SPACE
    397: 'Special 1',  # WXK_SPECIAL1
    406: 'Special 10',  # WXK_SPECIAL10
    407: 'Special 11',  # WXK_SPECIAL11
    408: 'Special 12',  # WXK_SPECIAL12
    409: 'Special 13',  # WXK_SPECIAL13
    410: 'Special 14',  # WXK_SPECIAL14
    411: 'Special 15',  # WXK_SPECIAL15
    412: 'Special 16',  # WXK_SPECIAL16
    413: 'Special 17',  # WXK_SPECIAL17
    414: 'Special 18',  # WXK_SPECIAL18
    415: 'Special 19',  # WXK_SPECIAL19
    398: 'Special 2',  # WXK_SPECIAL2
    416: 'Special 20',  # WXK_SPECIAL20
    399: 'Special 3',  # WXK_SPECIAL3
    400: 'Special 4',  # WXK_SPECIAL4
    401: 'Special 5',  # WXK_SPECIAL5
    402: 'Special 6',  # WXK_SPECIAL6
    403: 'Special 7',  # WXK_SPECIAL7
    404: 'Special 8',  # WXK_SPECIAL8
    405: 'Special 9',  # WXK_SPECIAL9
    300: 'Start',  # WXK_START
    337: 'Subtract',  # WXK_SUBTRACT
    9: 'Tab',  # WXK_TAB
    315: 'Up',  # WXK_UP

    425: 'Volume Down',  # WXK_VOLUME_DOWN
    424: 'Volume Mute',  # WXK_VOLUME_MUTE
    426: 'Volume Up',  # WXK_VOLUME_UP

    393: 'Windows Left',  # WXK_WINDOWS_LEFT
    395: 'Windows Menu',  # WXK_WINDOWS_MENU
    394: 'Windows Right',  # WXK_WINDOWS_RIGHT
}


def keycode_to_str(key_code: int) -> str:
    if key_code in KEY_CODE_LOOKUP:
        return KEY_CODE_LOOKUP[key_code]
    return '"{key_code}"'.format(key_code=chr(key_code))


def modifiers_to_str(modifiers: int) -> str:
    value = ''
    if modifiers & wx.ACCEL_CTRL != 0:
        value += 'Ctrl + '
    if modifiers & wx.ACCEL_SHIFT != 0:
        value += 'Shift + '
    if modifiers & wx.ACCEL_ALT != 0:
        value += 'Alt + '
    return value


def key_event_to_str(key_event: wx.KeyEvent):
    key_code = key_event.GetKeyCode()
    if key_code == wx.WXK_NONE:
        key_code = key_event.GetUnicodeKey()
    modifiers = key_event.GetModifiers()
    return f'{modifiers_to_str(modifiers)}{keycode_to_str(key_code)}'


class HotKeyDefinition:
    """
    Defines a hotkey definition.
    """

    def __repr__(self) -> str:
        return f'{modifiers_to_str(self.modifiers)}{keycode_to_str(self.key_code)}'

    def __str__(self) -> str:
        return repr(self)

    def __init__(self,
                 key_code: int,
                 modifiers: int = 0):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)

        self.key_code = key_code

        self.modifiers = modifiers

        self.logger.debug(self)

    def with_alt(self) -> 'HotKeyDefinition':
        self.modifiers = self.modifiers | wx.ACCEL_ALT
        return self

    def with_ctrl(self) -> 'HotKeyDefinition':
        self.modifiers = self.modifiers | wx.ACCEL_CTRL
        return self

    def with_shift(self) -> 'HotKeyDefinition':
        self.modifiers = self.modifiers | wx.ACCEL_SHIFT
        return self

    def matches(self, key_event: wx.KeyEvent) -> bool:
        key_code = key_event.GetKeyCode()
        if key_code == wx.WXK_NONE:
            key_code = key_event.GetUnicodeKey()
        modifiers = key_event.GetModifiers()
        return self.key_code == key_code and self.modifiers == modifiers


class HotKeyBindingDefinition:
    """
    Defines a hotkey binding definition.
    """

    def __repr__(self) -> str:
        return f'HotKeyBindingDefinition(hotkey={self.hotkey},' \
               f' handler={self.handler},' \
               f' description={self.description},' \
               f' alternate_hotkeys={self.alternate_hotkeys})'

    def __str__(self) -> str:
        return repr(self)

    def __init__(self,
                 name: str,
                 hotkey: HotKeyDefinition,
                 handler: Callable,
                 description: str,
                 alternate_hotkeys: List[HotKeyDefinition] = None,
                 hidden: bool = False,
                 window_id: wx.WindowIDRef = None,
                 bitmap_name: str = None):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)

        if alternate_hotkeys is None:
            alternate_hotkeys = []
        if window_id is None:
            window_id = wx.NewIdRef()

        self.name = name
        self.hotkey = hotkey
        self.handler = handler
        self.description = description
        self.alternate_hotkeys = alternate_hotkeys
        self.hidden = hidden
        self.window_id = window_id
        self.bitmap_name = bitmap_name

        self.logger.debug(self)

    def matches(self, key_event: wx.KeyEvent) -> bool:
        if self.hotkey.matches(key_event):
            return True
        for hotkey in self.alternate_hotkeys:
            if hotkey.matches(key_event):
                return True
        return False
