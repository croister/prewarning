from unittest.mock import patch
import pytest

from startlistsources._base import _StartListSourceBase, _NOT_OVERRIDDEN


class TestStartListSourceBase:
    def test_abstract_class(self):
        with pytest.raises(TypeError):
            _StartListSourceBase()

    def test_class_attributes_defaults(self):
        assert _StartListSourceBase.name is _NOT_OVERRIDDEN
        assert _StartListSourceBase.display_name is _NOT_OVERRIDDEN
        assert _StartListSourceBase.description is _NOT_OVERRIDDEN

    def test_str_repr(self):
        assert '_StartListSourceBase' in repr(_StartListSourceBase)
        assert '_StartListSourceBase' in str(_StartListSourceBase)

    @patch('utils.config.Config.register_config_section_listener')
    def test_concrete_subclass(self, _mock_register):
        class MySource(_StartListSourceBase):
            @classmethod
            def config_section_definition(cls):
                from utils.config_definitions import ConfigSectionDefinition
                return ConfigSectionDefinition('my_source', 'My Source')

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
        assert hasattr(s, 'logger')

    @patch('utils.config.Config.register_config_section_listener')
    def test_lookup_from_card_number_default(self, _mock_register):
        class MySource(_StartListSourceBase):
            @classmethod
            def config_section_definition(cls):
                from utils.config_definitions import ConfigSectionDefinition
                return ConfigSectionDefinition('ms', 'MS')

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
        assert s.lookup_from_card_number('12345') == {}

    @patch('utils.config.Config.register_config_section_listener')
    def test_is_running(self, _mock_register):
        class MySource(_StartListSourceBase):
            @classmethod
            def config_section_definition(cls):
                from utils.config_definitions import ConfigSectionDefinition
                return ConfigSectionDefinition('ms', 'MS')

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

    @patch('utils.config.Config.register_config_section_listener')
    def test_start_stop(self, _mock_register):
        started = False
        stopped = False

        class MySource(_StartListSourceBase):
            @classmethod
            def config_section_definition(cls):
                from utils.config_definitions import ConfigSectionDefinition
                return ConfigSectionDefinition('ms', 'MS')

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
