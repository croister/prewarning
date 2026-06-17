import logging

import pytest
import wx
from utils.singleton import _Singleton


def pytest_collection_finish(session):
    """Remove file-based log handlers added by prewarning module import.
    The log file may still be created at import time but no further
    writes will occur during test execution."""
    for handler in logging.root.handlers[:]:
        if isinstance(handler, logging.FileHandler):
            logging.root.removeHandler(handler)
            handler.close()


@pytest.fixture(autouse=True)
def _isolate_filesystem(tmp_path, monkeypatch):
    """Redirect all file-writing paths to a temp directory so tests never
    leave artifacts in the project tree (config.ini, data/*.dat)."""
    from utils.config import Config

    monkeypatch.setattr("utils.constants.DATA_DIR", tmp_path)
    monkeypatch.setattr("utils.state_saver.DATA_DIR", tmp_path)
    monkeypatch.setattr(Config, "DEFAULT_CONFIG_FILE_LOCATION", tmp_path / "config.ini")


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
