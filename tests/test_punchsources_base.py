from unittest.mock import MagicMock, patch

import pytest

from punchsources._base import _NOT_OVERRIDDEN, PunchListener, _PunchSourceBase


class TestPunchListener:
    def test_abstract_class(self):
        with pytest.raises(TypeError):
            PunchListener()

    def test_str_repr(self):
        assert "PunchListener" in repr(PunchListener)
        assert "PunchListener" in str(PunchListener)

    def test_concrete_subclass(self):
        class MyListener(PunchListener):
            def __init__(self):
                super().__init__()

        listener = MyListener()
        assert listener.logger is not None

    def test_punch_received_default_noop(self):
        class MyListener(PunchListener):
            def __init__(self):
                super().__init__()

        listener = MyListener()
        result = listener.punch_received({"card_number": "123"})
        assert result is None


class TestPunchSourceBase:
    def test_abstract_class(self):
        with pytest.raises(TypeError):
            _PunchSourceBase()

    def test_class_attributes_defaults(self):
        assert _PunchSourceBase.name is _NOT_OVERRIDDEN
        assert _PunchSourceBase.display_name is _NOT_OVERRIDDEN
        assert _PunchSourceBase.description is _NOT_OVERRIDDEN

    def test_str_repr(self):
        assert "_PunchSourceBase" in repr(_PunchSourceBase)
        assert "_PunchSourceBase" in str(_PunchSourceBase)

    @patch("utils.config.Config.register_config_section_listener")
    def test_concrete_subclass(self, mock_register):
        with patch("wx.CallAfter"):

            class MySource(_PunchSourceBase):
                @classmethod
                def config_section_definition(cls):
                    from utils.config_definitions import ConfigSectionDefinition

                    return ConfigSectionDefinition("my_source", "My Source")

                def __init__(self):
                    super().__init__()

                def start(self):
                    pass

                def stop(self):
                    pass

                def is_running(self):
                    return False

            s = MySource()
            assert s.logger is not None
            assert s.punch_listeners == set()
            assert s._tracking_listeners == []

    @patch("utils.config.Config.register_config_section_listener")
    def test_register_punch_listener(self, mock_register):
        with patch("wx.CallAfter"):

            class MySource(_PunchSourceBase):
                @classmethod
                def config_section_definition(cls):
                    from utils.config_definitions import ConfigSectionDefinition

                    return ConfigSectionDefinition("ms", "MS")

                def __init__(self):
                    super().__init__()

                def start(self):
                    pass

                def stop(self):
                    pass

                def is_running(self):
                    return False

            s = MySource()
            listener = MagicMock()
            s.register_punch_listener(listener)
            assert listener in s.punch_listeners

    @patch("utils.config.Config.register_config_section_listener")
    def test_notify_punch_listeners(self, mock_register):
        with patch("wx.CallAfter"):

            class MySource(_PunchSourceBase):
                @classmethod
                def config_section_definition(cls):
                    from utils.config_definitions import ConfigSectionDefinition

                    return ConfigSectionDefinition("ms", "MS")

                def __init__(self):
                    super().__init__()

                def start(self):
                    pass

                def stop(self):
                    pass

                def is_running(self):
                    return False

            s = MySource()
            listener = MagicMock()
            s.register_punch_listener(listener)
            punch_data = {"card_number": "999", "time": "12:00"}
            s._notify_punch_listeners(punch_data)
            listener.punch_received.assert_called_once_with(punch_data)

    @patch("utils.config.Config.register_config_section_listener")
    def test_register_tracking_listener(self, mock_register):
        with patch("wx.CallAfter"):

            class MySource(_PunchSourceBase):
                @classmethod
                def config_section_definition(cls):
                    from utils.config_definitions import ConfigSectionDefinition

                    return ConfigSectionDefinition("ms", "MS")

                def __init__(self):
                    super().__init__()

                def start(self):
                    pass

                def stop(self):
                    pass

                def is_running(self):
                    return False

            s = MySource()
            callback = MagicMock()
            s.register_tracking_listener(callback)
            assert callback in s._tracking_listeners

    @patch("utils.config.Config.register_config_section_listener")
    def test_register_tracking_listener_no_duplicate(self, mock_register):
        with patch("wx.CallAfter"):

            class MySource(_PunchSourceBase):
                @classmethod
                def config_section_definition(cls):
                    from utils.config_definitions import ConfigSectionDefinition

                    return ConfigSectionDefinition("ms", "MS")

                def __init__(self):
                    super().__init__()

                def start(self):
                    pass

                def stop(self):
                    pass

                def is_running(self):
                    return False

            s = MySource()
            callback = MagicMock()
            s.register_tracking_listener(callback)
            s.register_tracking_listener(callback)
            assert len(s._tracking_listeners) == 1

    @patch("utils.config.Config.register_config_section_listener")
    def test_unregister_tracking_listener(self, mock_register):
        with patch("wx.CallAfter"):

            class MySource(_PunchSourceBase):
                @classmethod
                def config_section_definition(cls):
                    from utils.config_definitions import ConfigSectionDefinition

                    return ConfigSectionDefinition("ms", "MS")

                def __init__(self):
                    super().__init__()

                def start(self):
                    pass

                def stop(self):
                    pass

                def is_running(self):
                    return False

            s = MySource()
            callback = MagicMock()
            s.register_tracking_listener(callback)
            s.unregister_tracking_listener(callback)
            assert callback not in s._tracking_listeners

    @patch("utils.config.Config.register_config_section_listener")
    def test_unregister_nonexistent(self, mock_register):
        with patch("wx.CallAfter"):

            class MySource(_PunchSourceBase):
                @classmethod
                def config_section_definition(cls):
                    from utils.config_definitions import ConfigSectionDefinition

                    return ConfigSectionDefinition("ms", "MS")

                def __init__(self):
                    super().__init__()

                def start(self):
                    pass

                def stop(self):
                    pass

                def is_running(self):
                    return False

            s = MySource()
            s.unregister_tracking_listener(MagicMock())

    @patch("utils.config.Config.register_config_section_listener")
    def test_notify_tracking_listeners_no_listeners(self, mock_register):
        with patch("wx.CallAfter") as mock_callafter:

            class MySource(_PunchSourceBase):
                @classmethod
                def config_section_definition(cls):
                    from utils.config_definitions import ConfigSectionDefinition

                    return ConfigSectionDefinition("ms", "MS")

                def __init__(self):
                    super().__init__()

                def start(self):
                    pass

                def stop(self):
                    pass

                def is_running(self):
                    return False

            s = MySource()
            s._notify_tracking_listeners()
            mock_callafter.assert_not_called()

    @patch("utils.config.Config.register_config_section_listener")
    def test_notify_tracking_listeners_with_listeners(self, mock_register):
        with patch("wx.CallAfter") as mock_callafter:

            class MySource(_PunchSourceBase):
                @classmethod
                def config_section_definition(cls):
                    from utils.config_definitions import ConfigSectionDefinition

                    return ConfigSectionDefinition("ms", "MS")

                def __init__(self):
                    super().__init__()

                def start(self):
                    pass

                def stop(self):
                    pass

                def is_running(self):
                    return False

            s = MySource()
            callback = MagicMock()
            s.register_tracking_listener(callback)
            s._notify_tracking_listeners()
            mock_callafter.assert_called_once_with(callback, {})

    @patch("utils.config.Config.register_config_section_listener")
    def test_notify_tracking_listeners_with_state(self, mock_register):
        with patch("wx.CallAfter") as mock_callafter:

            class MySource(_PunchSourceBase):
                @classmethod
                def config_section_definition(cls):
                    from utils.config_definitions import ConfigSectionDefinition

                    return ConfigSectionDefinition("ms", "MS")

                def _get_tracking_state(self):
                    return {"opt1": "val1", "opt2": "val2"}

                def __init__(self):
                    super().__init__()

                def start(self):
                    pass

                def stop(self):
                    pass

                def is_running(self):
                    return False

            s = MySource()
            callback = MagicMock()
            s.register_tracking_listener(callback)
            s._notify_tracking_listeners()
            mock_callafter.assert_called_once_with(
                callback, {"opt1": "val1", "opt2": "val2"}
            )

    @patch("utils.config.Config.register_config_section_listener")
    def test_get_tracking_state_default(self, mock_register):
        with patch("wx.CallAfter"):

            class MySource(_PunchSourceBase):
                @classmethod
                def config_section_definition(cls):
                    from utils.config_definitions import ConfigSectionDefinition

                    return ConfigSectionDefinition("ms", "MS")

                def __init__(self):
                    super().__init__()

                def start(self):
                    pass

                def stop(self):
                    pass

                def is_running(self):
                    return False

            s = MySource()
            assert s._get_tracking_state() == {}

    @patch("utils.config.Config.register_config_section_listener")
    def test_runtime_value_defaults(self, mock_register):
        with patch("wx.CallAfter"):

            class MySource(_PunchSourceBase):
                @classmethod
                def config_section_definition(cls):
                    from utils.config_definitions import ConfigSectionDefinition

                    return ConfigSectionDefinition("ms", "MS")

                def __init__(self):
                    super().__init__()

                def start(self):
                    pass

                def stop(self):
                    pass

                def is_running(self):
                    return False

            from utils.config_definitions import ConfigOptionDefinition

            s = MySource()
            opt = ConfigOptionDefinition("test", "Test", str, "desc")
            assert s.get_runtime_value(opt) is None
            s.set_runtime_value(opt, "val")
            s.reset_tracking()

    @patch("utils.config.Config.register_config_section_listener")
    def test_is_running(self, mock_register):
        with patch("wx.CallAfter"):

            class MySource(_PunchSourceBase):
                @classmethod
                def config_section_definition(cls):
                    from utils.config_definitions import ConfigSectionDefinition

                    return ConfigSectionDefinition("ms", "MS")

                def __init__(self):
                    super().__init__()

                def start(self):
                    pass

                def stop(self):
                    pass

                def is_running(self):
                    return True

            s = MySource()
            assert s.is_running() is True
