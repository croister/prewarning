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


class TestHealthListener:
    @patch("utils.config.Config.register_config_section_listener")
    def _make_source(self, _mock_register):
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

            return MySource()

    def test_register_health_listener(self):
        source = self._make_source()
        callback = MagicMock()
        source.register_health_listener(callback)
        assert callback in source._health_listeners

    def test_register_same_listener_twice_only_adds_once(self):
        source = self._make_source()
        callback = MagicMock()
        source.register_health_listener(callback)
        source.register_health_listener(callback)
        assert source._health_listeners.count(callback) == 1

    def test_unregister_health_listener(self):
        source = self._make_source()
        callback = MagicMock()
        source.register_health_listener(callback)
        source.unregister_health_listener(callback)
        assert callback not in source._health_listeners

    def test_unregister_nonexistent_listener_does_not_raise(self):
        source = self._make_source()
        callback = MagicMock()
        source.unregister_health_listener(callback)  # should not raise

    def test_notify_health_changed_calls_all_listeners(self):
        source = self._make_source()
        cb1 = MagicMock()
        cb2 = MagicMock()
        source.register_health_listener(cb1)
        source.register_health_listener(cb2)
        source._notify_health_changed()
        cb1.assert_called_once()
        cb2.assert_called_once()

    def test_notify_health_changed_continues_after_exception(self):
        source = self._make_source()
        cb1 = MagicMock(side_effect=RuntimeError("test"))
        cb2 = MagicMock()
        source.register_health_listener(cb1)
        source.register_health_listener(cb2)
        source._notify_health_changed()
        cb1.assert_called_once()
        cb2.assert_called_once()

    def test_set_health_status_notifies_listeners(self):
        from utils.health import HealthStatus

        source = self._make_source()
        callback = MagicMock()
        source.register_health_listener(callback)
        source._set_health_status(HealthStatus.ERROR, "test error")
        callback.assert_called_once()
        assert source.health_status == (HealthStatus.ERROR, "test error")

    def test_set_health_status_does_not_notify_if_unchanged(self):
        from utils.health import HealthStatus

        source = self._make_source()
        callback = MagicMock()
        source.register_health_listener(callback)
        # Initial status is OK, setting to OK again should not notify
        source._set_health_status(HealthStatus.OK)
        callback.assert_not_called()

    def test_set_health_status_notifies_on_message_change(self):
        from utils.health import HealthStatus

        source = self._make_source()
        callback = MagicMock()
        source._set_health_status(HealthStatus.ERROR, "first")
        source.register_health_listener(callback)
        source._set_health_status(HealthStatus.ERROR, "second")
        callback.assert_called_once()


class TestControlCodes:
    @patch("utils.config.Config.register_config_section_listener")
    def _make_source(self, _mock_register):
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

            return MySource()

    def test_get_control_codes_default_empty(self):
        source = self._make_source()
        assert source.get_control_codes() == []

    def test_verify_control_codes_default_none(self):
        source = self._make_source()
        assert source.verify_control_codes() is None
