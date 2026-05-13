import pytest
import wx
from utils.singleton import _Singleton


@pytest.fixture(autouse=True)
def reset_singleton_instances():
    saved = dict(_Singleton._instances)
    _Singleton._instances.clear()
    yield
    _Singleton._instances.update(saved)


_APP = None


@pytest.fixture(scope="session")
def wx_app():
    global _APP
    if _APP is None:
        _APP = wx.App(redirect=False)
    return _APP
