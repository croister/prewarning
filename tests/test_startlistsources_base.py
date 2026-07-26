from unittest.mock import MagicMock, patch

import pytest

from startlistsources._base import _NOT_OVERRIDDEN, _StartListSourceBase


class TestStartListSourceBase:
    def test_abstract_class(self):
        with pytest.raises(TypeError):
            _StartListSourceBase()

    def test_class_attributes_defaults(self):
        assert _StartListSourceBase.name is _NOT_OVERRIDDEN
        assert _StartListSourceBase.display_name is _NOT_OVERRIDDEN
        assert _StartListSourceBase.description is _NOT_OVERRIDDEN

    def test_str_repr(self):
        assert "_StartListSourceBase" in repr(_StartListSourceBase)
        assert "_StartListSourceBase" in str(_StartListSourceBase)

    @patch("utils.config.Config.register_config_section_listener")
    def test_concrete_subclass(self, _mock_register):
        class MySource(_StartListSourceBase):
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

            def lookup_from_card_number(self, card_number):
                return None

        s = MySource()
        assert s.logger is not None
        assert hasattr(s, "logger")

    @patch("utils.config.Config.register_config_section_listener")
    def test_lookup_from_card_number_default(self, _mock_register):
        class MySource(_StartListSourceBase):
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

            def lookup_from_card_number(self, card_number):
                return {}

        s = MySource()
        assert s.lookup_from_card_number("12345") == {}

    @patch("utils.config.Config.register_config_section_listener")
    def test_is_running(self, _mock_register):
        class MySource(_StartListSourceBase):
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

            def lookup_from_card_number(self, card_number):
                return None

        s = MySource()
        assert s.is_running() is True

    @patch("utils.config.Config.register_config_section_listener")
    def test_start_stop(self, _mock_register):
        started = False
        stopped = False

        class MySource(_StartListSourceBase):
            @classmethod
            def config_section_definition(cls):
                from utils.config_definitions import ConfigSectionDefinition

                return ConfigSectionDefinition("ms", "MS")

            def __init__(self):
                super().__init__()

            def start(self):
                nonlocal started
                started = True

            def stop(self):
                nonlocal stopped
                stopped = True

            def is_running(self):
                return started and not stopped

            def lookup_from_card_number(self, card_number):
                return None

        s = MySource()
        s.start()
        assert started is True
        s.stop()
        assert stopped is True


class TestDataListener:
    @patch("utils.config.Config.register_config_section_listener")
    def _make_source(self, _mock_register):
        class MySource(_StartListSourceBase):
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

            def lookup_from_card_number(self, card_number):
                return None

        return MySource()

    def test_register_data_listener(self):
        source = self._make_source()
        callback = MagicMock()
        source.register_data_listener(callback)
        assert callback in source._data_listeners

    def test_register_same_listener_twice_only_adds_once(self):
        source = self._make_source()
        callback = MagicMock()
        source.register_data_listener(callback)
        source.register_data_listener(callback)
        assert source._data_listeners.count(callback) == 1

    def test_unregister_data_listener(self):
        source = self._make_source()
        callback = MagicMock()
        source.register_data_listener(callback)
        source.unregister_data_listener(callback)
        assert callback not in source._data_listeners

    def test_unregister_nonexistent_listener_does_not_raise(self):
        source = self._make_source()
        callback = MagicMock()
        source.unregister_data_listener(callback)  # should not raise

    def test_notify_data_changed_calls_all_listeners(self):
        source = self._make_source()
        cb1 = MagicMock()
        cb2 = MagicMock()
        source.register_data_listener(cb1)
        source.register_data_listener(cb2)
        source._notify_data_changed()
        cb1.assert_called_once()
        cb2.assert_called_once()

    def test_notify_data_changed_continues_after_exception(self):
        source = self._make_source()
        cb1 = MagicMock(side_effect=RuntimeError("test"))
        cb2 = MagicMock()
        source.register_data_listener(cb1)
        source.register_data_listener(cb2)
        source._notify_data_changed()
        cb1.assert_called_once()
        cb2.assert_called_once()


class TestHealthListener:
    @patch("utils.config.Config.register_config_section_listener")
    def _make_source(self, _mock_register):
        class MySource(_StartListSourceBase):
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

            def lookup_from_card_number(self, card_number):
                return None

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
